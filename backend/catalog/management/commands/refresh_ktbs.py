import json
from pathlib import Path
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from catalog.ktbs_import import parse_ktbs_html, normalize_book, merge_unique
from catalog.ingest import ensure_provider, upsert_book, download_and_attach, media_target_dir


class Command(BaseCommand):
    help = 'Refresh Karnataka Textbook Society PDF index.'

    def add_arguments(self, parser):
        parser.add_argument('--source-url', default='https://textbooks.karnataka.gov.in/')
        parser.add_argument('--source-file', help='HTML or JSON file to parse instead of fetching.')
        parser.add_argument('--output', default=str(Path(__file__).resolve().parents[2] / 'data' / 'ktbs_books.json'))
        parser.add_argument('--syllabus', default='KSEEB')
        parser.add_argument('--school-type', default='government')
        parser.add_argument('--write-db', action='store_true', help='Upsert results into the database.')
        parser.add_argument('--clear', action='store_true', help='Clear existing KTBS rows before insert.')
        parser.add_argument('--download', action='store_true', help='Download PDFs into local media storage.')
        parser.add_argument('--skip-existing', action='store_true', help='Skip downloading if local file exists.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        source_url = options['source_url']
        source_file = options['source_file']
        syllabus = options['syllabus']
        school_type = options['school_type']

        if source_file:
            path = Path(source_file)
            if not path.exists():
                self.stderr.write('Source file not found')
                return
            content = path.read_text(encoding='utf-8')
            if path.suffix.lower() == '.json':
                raw_books = json.loads(content)
                books = raw_books
            else:
                links = parse_ktbs_html(content)
                books = [normalize_book(link, syllabus, school_type, source_url) for link in links]
        else:
            response = requests.get(
                source_url,
                timeout=settings.API_TIMEOUT_SECONDS,
                headers={'User-Agent': settings.DEFAULT_USER_AGENT},
            )
            response.raise_for_status()
            links = parse_ktbs_html(response.text)
            books = [normalize_book(link, syllabus, school_type, source_url) for link in links]

        books = merge_unique(books)
        self.stdout.write(f'Collected {len(books)} books')

        if options['dry_run']:
            return

        output_path = Path(options['output'])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(books, indent=2), encoding='utf-8')
        self.stdout.write(f'Wrote {output_path}')

        if options['write_db']:
            provider = ensure_provider(
                key='ktbs',
                name='Karnataka Textbook Society',
                description='Official Karnataka school textbooks.',
            )
            if options['clear']:
                provider.book_set.all().delete()

            for entry in books:
                entry['board'] = entry.get('board') or 'Karnataka State'
                entry['provider_key'] = 'ktbs'
                book = upsert_book(entry, provider)
                if options['download'] and book.download_url:
                    target_dir = media_target_dir(provider.key, book.board, book.grade)
                    if options['skip_existing'] and book.local_path:
                        continue
                    try:
                        download_and_attach(book, book.download_url, target_dir)
                    except Exception as exc:
                        book.file_status = f'failed: {exc}'
                        book.save(update_fields=['file_status'])
            self.stdout.write('Database updated')
