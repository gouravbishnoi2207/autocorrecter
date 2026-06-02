# AI-Powered Autocorrect Tool

Portfolio-grade Flask application for spell checking, grammar correction, context-aware rewriting, saved history, and admin analytics.

## Highlights

- Transformer-backed grammar correction with a local fallback path
- Real-time preview while typing, plus voice input in supported browsers
- Session-based authentication with `user` and `admin` roles
- Searchable correction history with TXT and PDF export
- Admin dashboard with usage charts, language mix, and recent activity
- SQLite persistence for users, corrections, and analytics summaries
- Responsive SaaS-style UI built with Bootstrap 5 and custom glassmorphism styling

## Stack

- Backend: Flask, SQLite, Werkzeug security helpers
- NLP: `pyspellchecker`, `TextBlob`, `NLTK`, optional Hugging Face `transformers`
- Frontend: Bootstrap 5, Chart.js, Bootstrap Icons, Google Fonts
- Testing: `pytest`, `pytest-cov`
- Deployment: Gunicorn and Docker

## Project Structure

```text
AI_Autocorrect/
├── app.py
├── Dockerfile
├── requirements.txt
├── README.md
├── templates/
├── static/
├── models/
├── services/
├── utils/
└── tests/
```

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Download the TextBlob corpora if your environment does not already include them:

```bash
python -m textblob.download_corpora
```

4. Start the app:

```bash
python app.py
```

5. ## Live Demo
https://autocorrecter.onrender.com

## Docker

Build and run the container:

```bash
docker build -t autocorrect-studio .
docker run -p 5000:5000 -e SECRET_KEY=change-me autocorrect-studio
```

## Authentication

- Register a new account from the UI.
- Sign in to save corrections and access the history center.
- Use the seeded admin account for the analytics dashboard.

Default demo admin credentials:

- Email: `admin@ai-autocorrect.local`
- Password: `Admin@12345!`

You can override them with the `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `ADMIN_NAME` environment variables.

## Key Routes

- `GET /` - Main workspace
- `GET /auth/register` - Register a user
- `GET /auth/login` - Sign in
- `GET /history` - Saved corrections for the active account
- `GET /admin/dashboard` - Admin analytics dashboard
- `POST /api/preview` - Live preview without saving
- `POST /api/correct` - Save a correction for the logged-in user
- `GET /api/history` - JSON list of saved corrections
- `GET /api/history/<id>` - Single correction detail
- `GET /api/analytics` - Admin analytics payload
- `GET /export/txt/<id>` - Download TXT report
- `GET /export/pdf/<id>` - Download PDF report
- `GET /health` - Health check

## Testing

Run the automated checks with:

```bash
pytest
```

## Notes

- The app initializes the SQLite schema on startup.
- If the Hugging Face model cannot load, the app falls back to the local correction path.
- NLTK corpora are downloaded on demand when missing.
