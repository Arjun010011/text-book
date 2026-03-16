# Karnataka eBook Library (Online-Only Mode)

This repo contains a Django backend and a React frontend that fetch ebooks directly from online sources.
Nothing is stored locally; all downloads are streamed from the official source APIs/portals.

Supported sources:

- Karnataka Textbook Society (state syllabus, fetched live from the official portal)
- NCERT (CBSE syllabus, fetched live from the NCERT portal)
- CISCE (ICSE syllabus resources — official links only)
- Open Library (public domain / borrowable ebooks)
- Project Gutenberg via Gutendex

## Quick start

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
python backend/manage.py runserver 0.0.0.0:8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## API endpoints

- `GET /api/health`
- `GET /api/providers`
- `GET /api/search?provider=ktbs&grade=10&subject=Mathematics`
- `GET /api/search?provider=ncert&grade=10&subject=Mathematics&language=English&q=maths`
- `GET /api/search?provider=cisce`
- `GET /api/search?provider=openlibrary&q=chemistry&page=1&page_size=24`
- `GET /api/search?provider=gutendex&q=india&page=1&page_size=24`
- `GET /api/book/openlibrary/<edition_id>`
- `GET /api/book/gutendex/<book_id>`
- `GET /api/book/ktbs/<id>`

## Notes

- KTBS links are parsed live from the official portal. If it changes, parsing may need updates.
- NCERT links point to official zip downloads hosted by NCERT.
- CISCE does not provide a unified free textbook download API; only official resources are listed.
