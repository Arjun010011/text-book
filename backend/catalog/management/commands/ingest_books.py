import json
from pathlib import Path
from django.core.management.base import BaseCommand
from catalog.ingest import ensure_provider, upsert_book, download_and_attach, media_target_dir


class Command(BaseCommand):
    help = 'Ingest book metadata (and optionally download PDFs) from a JSON file.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, help='Path to JSON file with book entries.')
        parser.add_argument('--download', action='store_true', help='Download PDFs into local media storage.')
        parser.add_argument('--skip-existing', action='store_true', help='Skip downloading if local file exists.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        source = Path(options['source'])
        if not source.exists():
            self.stderr.write('Source file not found')
            return

        entries = json.loads(source.read_text(encoding='utf-8'))
        if not isinstance(entries, list):
            self.stderr.write('JSON must be a list of book entries')
            return

        for entry in entries:
            provider_key = entry.get('provider_key') or entry.get('provider')
            if not provider_key:
                self.stderr.write('Missing provider_key in entry')
                continue
            provider = ensure_provider(
                key=provider_key,
                name=entry.get('provider_name') or provider_key.upper(),
                description=entry.get('provider_description', ''),
            )
            if options['dry_run']:
                continue
            book = upsert_book(entry, provider)
            if options['download'] and book.download_url:
                if options['skip_existing'] and book.local_path:
                    continue
                target_dir = media_target_dir(provider.key, book.board, book.grade)
                try:
                    download_and_attach(book, book.download_url, target_dir)
                except Exception as exc:
                    book.file_status = f'failed: {exc}'
                    book.save(update_fields=['file_status'])

        self.stdout.write('Ingest complete')
