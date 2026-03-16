import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlparse
import requests
from django.conf import settings
from django.utils.text import slugify
from catalog.models import Provider, Book

SAFE_FILENAME_RE = re.compile(r'[^a-zA-Z0-9._-]')


def ensure_provider(key, name=None, description=''):
    provider, _ = Provider.objects.get_or_create(
        key=key,
        defaults={
            'name': name or key.upper(),
            'description': description,
        },
    )
    return provider


def normalize_external_id(data):
    external_id = data.get('id') or data.get('external_id')
    if external_id:
        return str(external_id)
    base = f"{data.get('title', 'book')}-{data.get('grade', '')}-{data.get('subject', '')}"
    return slugify(base)[:100] or slugify(data.get('download_url', 'book'))[:100]


def safe_filename(name):
    return SAFE_FILENAME_RE.sub('_', name)[:180]


def download_pdf(url, target_path):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        url,
        timeout=settings.API_TIMEOUT_SECONDS,
        headers={'User-Agent': settings.DEFAULT_USER_AGENT},
        stream=True,
    )
    response.raise_for_status()

    content_type = response.headers.get('Content-Type', '').lower()
    if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
        raise ValueError(f'Not a PDF ({content_type})')

    hasher = hashlib.sha256()
    size = 0
    with target_path.open('wb') as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            handle.write(chunk)
            hasher.update(chunk)
            size += len(chunk)
    return size, hasher.hexdigest()


def infer_filename(data, url):
    title = data.get('title') or 'book'
    grade = data.get('grade') or ''
    subject = data.get('subject') or ''
    parsed = urlparse(url)
    filename = Path(parsed.path).name
    if not filename:
        filename = f"{title}-{grade}-{subject}.pdf"
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    return safe_filename(filename)


def upsert_book(data, provider):
    external_id = normalize_external_id(data)
    download_url = data.get('download_url', '')
    file_status = data.get('file_status')
    if not file_status:
        file_status = 'pending' if download_url else 'missing'
    defaults = {
        'title': data.get('title', ''),
        'authors': data.get('authors', ''),
        'language': data.get('language', ''),
        'medium': data.get('medium', ''),
        'grade': data.get('grade', ''),
        'subject': data.get('subject', ''),
        'school_type': data.get('school_type', ''),
        'syllabus': data.get('syllabus', ''),
        'board': data.get('board', ''),
        'download_url': download_url,
        'source_url': data.get('source_url', ''),
        'cover_url': data.get('cover_url', ''),
        'file_status': file_status,
        'metadata': data.get('metadata', {}),
    }
    book, _ = Book.objects.update_or_create(
        provider=provider,
        external_id=external_id,
        defaults=defaults,
    )
    return book


def download_and_attach(book, url, target_dir):
    filename = infer_filename({
        'title': book.title,
        'grade': book.grade,
        'subject': book.subject,
    }, url)
    target_path = target_dir / filename
    size, checksum = download_pdf(url, target_path)
    book.local_path = str(target_path.relative_to(settings.MEDIA_ROOT))
    book.file_size = size
    book.checksum_sha256 = checksum
    book.file_status = 'available'
    book.save(update_fields=['local_path', 'file_size', 'checksum_sha256', 'file_status'])
    return book


def media_target_dir(provider_key, board, grade):
    parts = ['ebooks', provider_key]
    if board:
        parts.append(safe_filename(board))
    if grade:
        parts.append(f"grade-{safe_filename(str(grade))}")
    return Path(settings.MEDIA_ROOT).joinpath(*parts)
