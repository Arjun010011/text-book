import re
from pathlib import Path
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup

GRADE_RE = re.compile(r'\\b(1[0-2]|[1-9])\\b')
CLASS_RE = re.compile(r'(?:class|clas|cls|std|standard|grade)\\s*(\\d{1,2})', re.IGNORECASE)
ORDINAL_RE = re.compile(r'\\b(1[0-2]|[1-9])(st|nd|rd|th)\\b', re.IGNORECASE)


def parse_ktbs_html(html, base_url='https://textbooks.karnataka.gov.in'):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if not href:
            continue
        if '.pdf' not in href.lower():
            continue
        if href.startswith('/'):
            href = f"{base_url.rstrip('/')}{href}"
        links.append(href)
    return links


def infer_metadata_from_url(url):
    parsed = urlparse(url)
    path = unquote(parsed.path)
    parts = [p for p in path.split('/') if p]
    grade = ''
    language = ''
    subject = ''

    def extract_grade(text):
        match = CLASS_RE.search(text)
        if match:
            return match.group(1)
        match = ORDINAL_RE.search(text)
        if match:
            return match.group(1)
        match = GRADE_RE.search(text)
        if match:
            return match.group(1)
        return ''

    for part in parts:
        if not grade:
            grade = extract_grade(part)

    for part in parts:
        if 'standard' in part.lower():
            if not grade:
                grade = extract_grade(part)
        elif not language and part.lower() in {'kannada', 'english', 'urdu', 'telugu', 'tamil', 'marathi'}:
            language = part
        elif not subject and part.lower() not in {'storage', 'pdf_files'} and part.lower() != 'textbooks':
            subject = part.replace('-', ' ').title()

    filename = Path(path).stem.replace('_', ' ').replace('-', ' ').title()
    title = filename
    if not language:
        if 'Eng' in filename or 'English' in filename:
            language = 'English'
        elif 'Kan' in filename or 'Kannada' in filename:
            language = 'Kannada'
    if not subject:
        lowered = filename.lower()
        if 'math' in lowered:
            subject = 'Mathematics'
        elif 'science' in lowered:
            subject = 'Science'
        elif 'social' in lowered:
            subject = 'Social Science'

    if not grade:
        grade = extract_grade(filename)

    return {
        'title': title,
        'grade': grade,
        'language': language,
        'subject': subject,
    }


def normalize_book(url, syllabus='KSEEB', school_type='government', source_url='https://textbooks.karnataka.gov.in/'):
    meta = infer_metadata_from_url(url)
    external_id = f"ktbs-{Path(urlparse(url).path).stem.lower()}"
    return {
        'id': external_id,
        'title': meta['title'] or external_id,
        'grade': meta['grade'],
        'subject': meta['subject'],
        'language': meta['language'],
        'medium': meta['language'],
        'school_type': school_type,
        'syllabus': syllabus,
        'board': 'Karnataka State',
        'download_url': url,
        'source_url': source_url,
    }


def merge_unique(books):
    seen = set()
    unique = []
    for book in books:
        key = book.get('download_url') or book.get('id')
        if key in seen:
            continue
        seen.add(key)
        unique.append(book)
    return unique
