import re
from functools import lru_cache
import json
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings

NCERT_TEXTBOOK_URLS = [
    'https://ncert.nic.in/textbook.php',
    'https://ncert.gov.in/textbook.php',
]
NCERT_PDF_BASES = [
    'https://ncert.nic.in/textbook/pdf',
    'https://ncert.gov.in/textbook/pdf',
]
NCERT_CACHE_PATH = Path(__file__).resolve().parent / 'data' / 'ncert_codes.json'

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
    'mh': 'Mathematics',
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
        total=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _fetch_textbook_page():
    session = _session_with_retries()
    last_error = None
    for url in NCERT_TEXTBOOK_URLS:
        try:
            response = session.get(
                url,
                timeout=settings.API_TIMEOUT_SECONDS,
                headers={'User-Agent': settings.DEFAULT_USER_AGENT},
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return ''


def _load_cached_codes():
    if NCERT_CACHE_PATH.exists():
        try:
            return json.loads(NCERT_CACHE_PATH.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


def _store_cached_codes(codes):
    try:
        NCERT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        NCERT_CACHE_PATH.write_text(json.dumps(codes, indent=2), encoding='utf-8')
    except Exception:
        pass


@lru_cache(maxsize=1)
def list_codes():
    cached = _load_cached_codes()
    try:
        html = _fetch_textbook_page()
        codes = sorted({m.group(1).lower() for m in CODE_RE.finditer(html)})
        if codes:
            _store_cached_codes(codes)
            return codes
    except Exception:
        pass
    return cached


def code_metadata(code):
    code = code.lower()
    grade = CLASS_MAP.get(code[0], '')
    language = LANG_MAP.get(code[1], '')
    subject = SUBJECT_MAP.get(code[2:4], '')
    return grade, language, subject


def build_book(code):
    grade, language, subject = code_metadata(code)
    return {
        'id': f'ncert-{code}',
        'code': code,
        'title': f'NCERT {subject or "Textbook"} (Class {grade})',
        'grade': grade,
        'subject': subject,
        'language': language,
        'board': 'CBSE',
        'syllabus': 'CBSE',
        'download_url': f"{NCERT_PDF_BASES[0]}/{code}dd.zip",
        'source_url': f"{NCERT_TEXTBOOK_URLS[0]}?{code}=0-99",
        'provider': 'ncert',
    }


def search_ncert(query, filters, page, page_size):
    grade = filters.get('grade')
    subject = filters.get('subject')
    language = filters.get('language')

    q = query.lower().strip()

    def matches(book):
        if grade and book.get('grade') != str(grade):
            return False
        if subject and subject.lower() not in (book.get('subject') or '').lower():
            return False
        if language and language.lower() not in (book.get('language') or '').lower():
            return False
        if q and q not in book['title'].lower():
            return False
        return True

    codes = list_codes()
    books = [build_book(code) for code in codes]
    filtered = [book for book in books if matches(book)]
    count = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return filtered[start:end], count
