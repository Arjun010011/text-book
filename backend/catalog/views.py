import json
from pathlib import Path
from urllib.parse import quote_plus
import requests
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils.timezone import now
from catalog.ktbs_import import parse_ktbs_html, normalize_book, merge_unique
from catalog.ncert_live import search_ncert
from catalog.cisce_live import list_cisce_resources

KTBS_PORTAL_URL = 'https://textbooks.karnataka.gov.in/textbooks/en'

DATA_PATH = Path(__file__).resolve().parent / 'data' / 'ktbs_books.json'


def health(_request):
    return JsonResponse({
        'status': 'ok',
        'time': now().isoformat(),
    })


def providers(_request):
    return JsonResponse({
        'providers': [
            {
                'id': 'ktbs',
                'name': 'Karnataka Textbook Society',
                'description': 'Official Karnataka school textbooks (fetched live from the portal).',
                'notes': 'Links are parsed live from the state portal and may change.',
            },
            {
                'id': 'ncert',
                'name': 'NCERT (CBSE)',
                'description': 'NCERT textbooks fetched live from the official portal.',
                'notes': 'Downloads are provided as official zip files.',
            },
            {
                'id': 'cisce',
                'name': 'CISCE (ICSE)',
                'description': 'Official CISCE resources and syllabus links.',
                'notes': 'CISCE does not provide a unified free textbook API; this lists official resources only.',
            },
            {
                'id': 'openlibrary',
                'name': 'Open Library',
                'description': 'Public domain and borrowable books from Open Library.',
                'notes': 'Access varies by title; some are preview/borrow only.',
            },
            {
                'id': 'gutendex',
                'name': 'Project Gutenberg',
                'description': 'Public domain ebooks from Project Gutenberg via Gutendex API.',
                'notes': 'Multiple formats; PDF/EPUB/HTML availability varies.',
            },
        ]
    })


def search(request):
    query = request.GET.get('q', '').strip()
    provider = request.GET.get('provider', 'ktbs').strip().lower()
    page = _safe_int(request.GET.get('page'), default=1, min_value=1)
    page_size = _safe_int(request.GET.get('page_size'), default=24, min_value=1, max_value=100)

    if provider not in {'ktbs', 'ncert', 'cisce', 'openlibrary', 'gutendex'}:
        return HttpResponseBadRequest('Unknown provider')

    if provider in {'openlibrary', 'gutendex'} and not query:
        return HttpResponseBadRequest('Query required for this provider')

    if provider == 'ktbs':
        results, count = _search_ktbs_live(request, page, page_size)
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size})
    if provider == 'ncert':
        filters = {
            'grade': request.GET.get('grade'),
            'subject': request.GET.get('subject'),
            'language': request.GET.get('language'),
        }
        results, count = search_ncert(query, filters, page, page_size)
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size})
    if provider == 'cisce':
        filters = {
            'grade': request.GET.get('grade'),
            'subject': request.GET.get('subject'),
            'doc_type': request.GET.get('doc_type'),
        }
        results, count = list_cisce_resources(filters, page, page_size)
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size})
    if provider == 'openlibrary':
        results, count = _search_openlibrary(query, page, page_size)
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size})
    results, count = _search_gutendex(query, page, page_size)
    return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size})


def book_detail(request, provider, book_id):
    provider = provider.lower()
    if provider == 'ktbs':
        return JsonResponse(_ktbs_detail(book_id))
    if provider == 'openlibrary':
        return JsonResponse(_openlibrary_detail(book_id))
    if provider == 'gutendex':
        return JsonResponse(_gutendex_detail(book_id))
    return HttpResponseBadRequest('Unknown provider')


def _load_ktbs_books_cached():
    cached = cache.get('ktbs_books')
    if cached:
        return cached

    try:
        response = requests.get(
            KTBS_PORTAL_URL,
            timeout=settings.API_TIMEOUT_SECONDS,
            headers={'User-Agent': settings.DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        links = parse_ktbs_html(response.text, base_url='https://textbooks.karnataka.gov.in')
        books = [normalize_book(link, source_url=KTBS_PORTAL_URL) for link in links]
        books = merge_unique(books)
    except Exception:
        if DATA_PATH.exists():
            with DATA_PATH.open('r', encoding='utf-8') as handle:
                books = json.load(handle)
        else:
            books = []

    cache.set('ktbs_books', books, settings.CACHE_TTL_SECONDS)
    return books


def _normalize_text(value):
    return (value or '').strip().lower()


def _search_ktbs_live(request, page, page_size):
    results = _load_ktbs_books_cached()
    syllabus = _normalize_text(request.GET.get('syllabus'))
    school_type = _normalize_text(request.GET.get('school_type'))
    grade = _normalize_text(request.GET.get('grade'))
    language = _normalize_text(request.GET.get('language'))
    subject = _normalize_text(request.GET.get('subject'))

    def matches(book):
        if syllabus and _normalize_text(book.get('syllabus')) != syllabus:
            return False
        if school_type and _normalize_text(book.get('school_type')) != school_type:
            return False
        book_grade = _normalize_text(book.get('grade'))
        title = _normalize_text(book.get('title'))
        if grade and book_grade != grade and grade not in title:
            return False
        book_language = _normalize_text(book.get('language'))
        if language and language not in book_language and language not in title:
            return False
        book_subject = _normalize_text(book.get('subject'))
        if subject and subject not in book_subject and subject not in title:
            return False
        return True

    filtered = [book for book in results if matches(book)]
    return _paginate_list(filtered, page, page_size)


def _ktbs_detail(book_id):
    for book in _load_ktbs_books_cached():
        if book.get('id') == book_id:
            return book
    return {'error': 'Not found'}


def _search_openlibrary(query, page, page_size):
    url = (
        f"{settings.OPENLIBRARY_BASE}/search.json?q={quote_plus(query)}"
        f"&has_fulltext=true&page={page}"
    )
    data = _get_cached_json(url)

    results = []
    docs = data.get('docs', [])
    count = data.get('numFound', len(docs))
    for item in docs[:page_size]:
        edition_keys = item.get('edition_key') or []
        work_key = item.get('key')
        cover_id = item.get('cover_i')
        results.append({
            'id': edition_keys[0] if edition_keys else (work_key or '').split('/')[-1],
            'title': item.get('title'),
            'authors': item.get('author_name', [])[:2],
            'language': (item.get('language') or [])[:3],
            'first_publish_year': item.get('first_publish_year'),
            'cover_url': f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None,
            'source_url': f"{settings.OPENLIBRARY_BASE}{work_key}" if work_key else None,
            'provider': 'openlibrary',
        })
    return results, count


def _openlibrary_detail(edition_or_work_id):
    edition_key = edition_or_work_id
    url = f"{settings.OPENLIBRARY_BASE}/api/books?bibkeys=OLID:{edition_key}&format=json&jscmd=data"
    payload = _get_cached_json(url)
    book = payload.get(f"OLID:{edition_key}")

    if not book:
        return {'error': 'Not found or unavailable'}

    ebooks = book.get('ebooks') or []
    access = None
    if ebooks:
        availability = ebooks[0].get('availability', {})
        access = {
            'status': availability.get('status'),
            'preview': availability.get('preview'),
            'preview_url': availability.get('preview_url'),
            'borrow_url': availability.get('borrow_url'),
        }

    return {
        'id': edition_key,
        'title': book.get('title'),
        'authors': [a.get('name') for a in book.get('authors', []) if a.get('name')],
        'publish_date': book.get('publish_date'),
        'cover_url': (book.get('cover') or {}).get('medium'),
        'source_url': book.get('url'),
        'access': access,
        'provider': 'openlibrary',
    }


def _search_gutendex(query, page, page_size):
    url = (
        f"{settings.GUTENDEX_BASE}/books/?search={quote_plus(query)}&page={page}"
    )
    data = _get_cached_json(url)

    results = []
    items = data.get('results', [])
    count = data.get('count', len(items))
    for item in items[:page_size]:
        results.append({
            'id': str(item.get('id')),
            'title': item.get('title'),
            'authors': [a.get('name') for a in item.get('authors', [])[:2]],
            'languages': item.get('languages', []),
            'download_url': _pick_gutendex_format(item.get('formats', {})),
            'cover_url': item.get('formats', {}).get('image/jpeg'),
            'source_url': item.get('formats', {}).get('text/html'),
            'provider': 'gutendex',
        })
    return results, count


def _gutendex_detail(book_id):
    url = f"{settings.GUTENDEX_BASE}/books/{book_id}/"
    item = _get_cached_json(url)
    return {
        'id': str(item.get('id')),
        'title': item.get('title'),
        'authors': [a.get('name') for a in item.get('authors', [])],
        'languages': item.get('languages', []),
        'download_url': _pick_gutendex_format(item.get('formats', {})),
        'cover_url': item.get('formats', {}).get('image/jpeg'),
        'source_url': item.get('formats', {}).get('text/html'),
        'provider': 'gutendex',
    }


def _pick_gutendex_format(formats):
    for key in (
        'application/pdf',
        'application/epub+zip',
        'text/html; charset=utf-8',
        'text/plain; charset=utf-8',
    ):
        if key in formats:
            return formats[key]
    return None


def _get_cached_json(url):
    cached = cache.get(url)
    if cached:
        return cached
    try:
        response = requests.get(
            url,
            timeout=settings.API_TIMEOUT_SECONDS,
            headers={'User-Agent': settings.DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        data = {}
    cache.set(url, data, settings.CACHE_TTL_SECONDS)
    return data


def _paginate_list(items, page, page_size):
    count = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], count


def _safe_int(value, default=1, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None:
        parsed = max(parsed, min_value)
    if max_value is not None:
        parsed = min(parsed, max_value)
    return parsed
