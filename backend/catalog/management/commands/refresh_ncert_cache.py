from pathlib import Path
from django.core.management.base import BaseCommand
from catalog.ncert_live import _store_cached_codes, CODE_RE
import requests
from django.conf import settings

NCERT_TEXTBOOK_URL = 'https://ncert.nic.in/textbook.php'


class Command(BaseCommand):
    help = 'Refresh NCERT code cache (online-only mode).'

    def add_arguments(self, parser):
        parser.add_argument('--source-file', help='HTML file to parse instead of fetching')

    def handle(self, *args, **options):
        source_file = options.get('source_file')
        if source_file:
            html = Path(source_file).read_text(encoding='utf-8')
        else:
            response = requests.get(
                NCERT_TEXTBOOK_URL,
                timeout=settings.API_TIMEOUT_SECONDS,
                headers={'User-Agent': settings.DEFAULT_USER_AGENT},
            )
            response.raise_for_status()
            html = response.text

        codes = sorted({m.group(1).lower() for m in CODE_RE.finditer(html)})
        _store_cached_codes(codes)
        self.stdout.write(f'Cached {len(codes)} NCERT codes')
