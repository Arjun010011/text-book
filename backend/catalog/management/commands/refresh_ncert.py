import io
import re
import zipfile
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand
from catalog.ingest import ensure_provider, upsert_book, media_target_dir

NCERT_TEXTBOOK_URL = 'https://ncert.nic.in/textbook.php'
NCERT_PDF_BASE = 'https://ncert.nic.in/textbook/pdf'

CODE_RE = re.compile(r'textbook\.php\?([a-z]{4}\d)\b', re.IGNORECASE)

CLASS_MAP = {
    'a': '1', 'b': '2', 'c': '3', 'd': '4', 'e': '5',
    'f': '6', 'g': '7', 'h': '8', 'i': '9', 'j': '10',
    'k': '11', 'l': '12',
}

LANG_MAP = {
    'e': 'English',
    'h': 'Hindi',
    'u': 'Urdu',
}

SUBJECT_MAP = {
    'ma': 'Mathematics',
    'sc': 'Science',
    'ss': 'Social Science',
    'hi': 'Hindi',
    'en': 'English',
    'gu': 'Gujarati',
    'ta': 'Tamil',
    'te': 'Telugu',
    'ka': 'Kannada',
    'sa': 'Sanskrit',
    'ur': 'Urdu',
    'ph': 'Physics',
    'ch': 'Chemistry',
    'bi': 'Biology',
    'ec': 'Economics',
    'bs': 'Business Studies',
    'ac': 'Accountancy',
    'po': 'Political Science',
    'ge': 'Geography',
    'so': 'Sociology',
    'ps': 'Psychology',
    'ip': 'Informatics Practices',
}


def _session_with_retries():
    retry = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_ncert_page(url):
    session = _session_with_retries()
    response = session.get(
        url,
        timeout=settings.API_TIMEOUT_SECONDS,
        headers={
            'User-Agent': settings.DEFAULT_USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        },
    )
    response.raise_for_status()
    return response.text


def extract_codes(html):
    codes = set()
    soup = BeautifulSoup(html, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href') or ''
        match = CODE_RE.search(href)
        if match:
            codes.add(match.group(1).lower())
    for match in CODE_RE.finditer(html):
        codes.add(match.group(1).lower())
    return sorted(codes)


def infer_metadata(code):
    code = code.lower()
    grade = CLASS_MAP.get(code[0], '')
    language = LANG_MAP.get(code[1], '')
    subject = SUBJECT_MAP.get(code[2:4], '')
    return grade, language, subject


def download_zip(url):
    response = requests.get(
        url,
        timeout=settings.API_TIMEOUT_SECONDS,
        headers={'User-Agent': settings.DEFAULT_USER_AGENT},
        stream=True,
    )
    response.raise_for_status()
    return response.content


def download_zip_to_file(url, target_path):
    response = requests.get(
        url,
        timeout=settings.API_TIMEOUT_SECONDS,
        headers={'User-Agent': settings.DEFAULT_USER_AGENT},
        stream=True,
    )
    response.raise_for_status()
    with target_path.open('wb') as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                handle.write(chunk)
    return target_path


def extract_zip_pdfs(content, target_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    pdf_paths = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith('.pdf'):
                continue
            filename = Path(name).name
            target_path = target_dir / filename
            with target_path.open('wb') as handle:
                handle.write(zf.read(name))
            pdf_paths.append(target_path)
    return pdf_paths


def try_merge_pdfs(pdf_paths, output_path):
    try:
        from pypdf import PdfWriter
    except Exception:
        return False

    writer = PdfWriter()
    for pdf in pdf_paths:
        try:
            writer.append(str(pdf))
        except Exception:
            continue
    if not writer.pages:
        return False
    with output_path.open('wb') as handle:
        writer.write(handle)
    return True


def hash_file(path):
    import hashlib
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


class Command(BaseCommand):
    help = 'Refresh NCERT textbook index and optionally download PDFs.'

    def add_arguments(self, parser):
        parser.add_argument('--download', action='store_true', help='Download PDFs into local media storage.')
        parser.add_argument('--skip-existing', action='store_true', help='Skip downloading if local file exists.')
        parser.add_argument('--source-url', default=NCERT_TEXTBOOK_URL)
        parser.add_argument('--source-file', help='HTML file to parse instead of fetching.')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of books to process.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        source_file = options.get('source_file')
        source_url = options.get('source_url') or NCERT_TEXTBOOK_URL
        if source_file:
            html = Path(source_file).read_text(encoding='utf-8')
        else:
            html = fetch_ncert_page(source_url)
        codes = extract_codes(html)
        self.stdout.write(f'Found {len(codes)} book codes')

        provider = ensure_provider(
            key='ncert',
            name='NCERT',
            description='NCERT textbooks (CBSE syllabus).',
        )

        processed = 0
        for code in codes:
            if options['limit'] and processed >= options['limit']:
                break
            grade, language, subject = infer_metadata(code)
            source_url = f"{NCERT_TEXTBOOK_URL}?{code}=0-99"
            download_url = f"{NCERT_PDF_BASE}/{code}dd.zip"
            entry = {
                'id': f"ncert-{code}",
                'title': f"NCERT {subject or 'Textbook'} (Class {grade})",
                'grade': grade,
                'subject': subject,
                'language': language,
                'medium': language,
                'syllabus': 'CBSE',
                'board': 'CBSE',
                'download_url': download_url,
                'source_url': source_url,
            }

            if options['dry_run']:
                continue

            book = upsert_book(entry, provider)
            if not options['download']:
                continue
            if options['skip_existing'] and book.local_path:
                continue

            try:
                target_dir = media_target_dir(provider.key, book.board, book.grade)
                zip_path = target_dir / f"{code}.zip"
                download_zip_to_file(download_url, zip_path)
                with zip_path.open('rb') as handle:
                    zip_bytes = handle.read()
                pdf_paths = extract_zip_pdfs(zip_bytes, target_dir)
                zip_path.unlink(missing_ok=True)
                if not pdf_paths:
                    book.file_status = 'failed: no pdfs in zip'
                    book.save(update_fields=['file_status'])
                    continue

                merged_path = target_dir / f"{code}_full.pdf"
                merged = try_merge_pdfs(pdf_paths, merged_path)
                if merged:
                    size = merged_path.stat().st_size
                    checksum = hash_file(merged_path)
                    book.local_path = str(merged_path.relative_to(settings.MEDIA_ROOT))
                    book.file_size = size
                    book.checksum_sha256 = checksum
                    book.file_status = 'available'
                    book.save(update_fields=['local_path', 'file_size', 'checksum_sha256', 'file_status'])
                else:
                    book.local_path = str(pdf_paths[0].relative_to(settings.MEDIA_ROOT))
                    book.file_size = pdf_paths[0].stat().st_size
                    book.file_status = 'available'
                    book.save(update_fields=['local_path', 'file_size', 'file_status'])
            except Exception as exc:
                book.file_status = f'failed: {exc}'
                book.save(update_fields=['file_status'])
            processed += 1

        self.stdout.write('NCERT refresh complete')
