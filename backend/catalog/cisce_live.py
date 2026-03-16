import re
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from django.conf import settings

CISCE_DOWNLOADS_URL = 'https://cisceboard.org/downloads.html'

GRADE_RE = re.compile(r'\b(1[0-2]|[1-9])\b')

SUBJECT_KEYWORDS = {
    'mathematics': 'Mathematics',
    'maths': 'Mathematics',
    'science': 'Science',
    'physics': 'Physics',
    'chemistry': 'Chemistry',
    'biology': 'Biology',
    'english': 'English',
    'hindi': 'Hindi',
    'computer': 'Computer Science',
    'geography': 'Geography',
    'history': 'History',
    'economics': 'Economics',
}

DOC_TYPE_KEYWORDS = {
    'syllabus': 'Syllabus',
    'regulation': 'Regulations',
    'specimen': 'Specimen Papers',
    'question': 'Question Papers',
    'timetable': 'Time Table',
    'circular': 'Circular',
    'notification': 'Notification',
    'guidelines': 'Guidelines',
}


def _session_with_retries():
    retry = Retry(
        total=3,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _infer_doc_type(title):
    lowered = title.lower()
    for key, value in DOC_TYPE_KEYWORDS.items():
        if key in lowered:
            return value
    return 'Document'


def _infer_subject(title):
    lowered = title.lower()
    for key, value in SUBJECT_KEYWORDS.items():
        if key in lowered:
            return value
    return ''


def _infer_grade(title):
    match = GRADE_RE.search(title)
    if match:
        return match.group(1)
    return ''


def _infer_file_type(url):
    lowered = url.lower()
    if lowered.endswith('.pdf'):
        return 'pdf'
    if lowered.endswith('.zip'):
        return 'zip'
    if lowered.endswith('.doc') or lowered.endswith('.docx'):
        return 'doc'
    return 'link'


def fetch_cisce_downloads():
    session = _session_with_retries()
    response = session.get(
        CISCE_DOWNLOADS_URL,
        timeout=settings.API_TIMEOUT_SECONDS,
        headers={'User-Agent': settings.DEFAULT_USER_AGENT},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    links = []
    for a in soup.find_all('a'):
        href = a.get('href') or ''
        text = (a.get_text() or '').strip()
        if not href or not text:
            continue
        if 'download' not in href.lower() and 'pdf' not in href.lower():
            continue
        absolute = urljoin(CISCE_DOWNLOADS_URL, href)
        links.append({
            'title': text,
            'source_url': absolute,
            'file_type': _infer_file_type(absolute),
            'doc_type': _infer_doc_type(text),
            'subject': _infer_subject(text),
            'grade': _infer_grade(text),
        })
    return links


def list_cisce_resources(filters, page, page_size):
    try:
        links = fetch_cisce_downloads()
    except Exception:
        links = []

    grade = (filters.get('grade') or '').strip()
    subject = (filters.get('subject') or '').strip().lower()
    doc_type = (filters.get('doc_type') or '').strip().lower()

    def matches(item):
        if grade and item.get('grade') != grade:
            return False
        if subject and subject not in (item.get('subject') or '').lower():
            return False
        if doc_type and doc_type not in (item.get('doc_type') or '').lower():
            return False
        return True

    filtered = [link for link in links if matches(link)]

    results = []
    for idx, link in enumerate(filtered):
        results.append({
            'id': f'cisce-{idx}',
            'title': link['title'],
            'source_url': link['source_url'],
            'download_url': link['source_url'] if link.get('file_type') == 'pdf' else None,
            'file_type': link.get('file_type'),
            'doc_type': link.get('doc_type'),
            'subject': link.get('subject'),
            'grade': link.get('grade'),
            'board': 'ICSE',
            'syllabus': 'ICSE',
            'provider': 'cisce',
        })

    count = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    return results[start:end], count
