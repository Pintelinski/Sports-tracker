# Sports Tracker

A Django web app for rowing crews to plan and track their training. Each rower has a profile, joins one or more crews, sees the crew's weekly training schedule, marks their attendance, logs daily body stats from their watch, and can subscribe to their crews' calendar in Google Calendar / Apple Calendar / Outlook.

Built as an individual project for Fontys semester 4.

## Features

- **Crew agenda** — week view per crew with intensity-coloured training blocks. Click a block for full training info; click the small checkbox in the corner to cycle your attendance: pending → present → absent → pending. Updates over AJAX, no page refresh.
- **Crews & memberships** — one user can belong to many crews, each with a role (`athlete`, `coach`, `cox`). Only existing members can add new members.
- **Body stats** — log daily weight, resting heart rate, HRV and body battery. The page shows four trend charts (Chart.js) and an editable history table. A reminder banner appears on the agenda if today isn't logged yet. Body stats are private — only the owner can see or edit their rows.
- **Calendar sync** — every user gets a unique ICS feed URL. Paste it into Google Calendar via *Other calendars → From URL* to get all your crews' trainings auto-syncing. Per-crew feed URLs are also available from each crew's info page.
- **JWT API** — `/api/users/token/` mints access (5 min) and refresh (1 day) tokens. The browser also stores the JWT in the session, and a custom middleware logs the user out as soon as the token expires.
- **Profile pictures** — uploaded to a bind-mounted host folder, served by nginx.

## Tech stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11, Django 5.2, Django REST Framework, djangorestframework-simplejwt, icalendar |
| Database | PostgreSQL 16 (production), SQLite in-memory (tests) |
| Frontend | Server-rendered Django templates, vanilla JS, Chart.js (CDN) |
| Serving | Gunicorn behind nginx (Docker Compose) |
| CI/CD | GitHub Actions → EduCloud VM over SSH |

## Project layout

```
Sportstracker/
├── Sportstracker/         # Django project (settings, urls, wsgi)
│   ├── settings.py
│   ├── test_settings.py   # tests use this — SQLite + fast hashing
│   └── urls.py
├── agenda/                # trainings, attendance, bodystats, ICS feeds
├── api/                   # DRF endpoints + JWT obtain/refresh URLs
├── users/                 # Profiles, Crews, CrewMembership, JWT-session middleware
├── static/                # CSS, JS, default images (bind-mounted in prod)
├── templates/             # base layout + nav
├── manage.py
├── requirements.txt
├── dockerfile
├── docker-compose.yml
├── nginx.conf
└── .github/workflows/deploy.yml
```

A UML class diagram of the data model lives at [`../class_diagram.md`](../class_diagram.md).

## Running locally for development

### 1. Prerequisites

- Python 3.11
- PostgreSQL 14+ (locally installed, or run via Docker — see below)
- Git

### 2. Clone and create a virtualenv

```bash
git clone <your-fork>
cd Sportstracker
python -m venv env
# Windows
env\Scripts\activate
# macOS / Linux
source env/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Provide a Postgres database

Easiest option — run one in Docker:

```bash
docker run -d --name sportstracker-db \
  -e POSTGRES_DB=sportstracker \
  -e POSTGRES_USER=sportstracker \
  -e POSTGRES_PASSWORD=devpassword \
  -p 5432:5432 \
  postgres:16
```

(Or install Postgres locally and create the database/user yourself.)

### 4. Create a `.env` file in the project root

The same folder as `manage.py`. Django loads it via `python-dotenv`.

```env
SECRET_KEY=dev-only-not-a-real-secret
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=sportstracker
DB_USER=sportstracker
DB_PASSWORD=devpassword
DB_HOST=localhost
DB_PORT=5432
```

### 5. Apply migrations and start the dev server

```bash
python manage.py migrate
python manage.py createsuperuser   # optional but useful for /admin
python manage.py runserver
```

App runs at <http://127.0.0.1:8000>.

### 6. (Optional) Create test data

Log in once to create your profile (a Profile is auto-created via signal on first user save), then use `/agenda/create-crew/`, `/agenda/add-training/`, etc. The `/admin/` panel works for direct edits.

## Running the tests

The test suite uses an in-memory SQLite database so it doesn't need Postgres or a `CREATEDB` privilege.

```bash
python manage.py test --settings=Sportstracker.test_settings
```

39 tests covering profile signals, JWT-session middleware behaviour, the attendance state machine, body-stats privacy and boundaries, crew authorisation, ICS feed token validation, and the JWT API. Tests are organised around TMap design techniques (decision tables, equivalence partitioning, boundary value analysis, use case tests) — see the docstring at the top of each `tests.py` for the mapping.

## Running everything in Docker

The repo's compose file is configured for the production-style setup (gunicorn + nginx, no DB service — the DB lives on a separate VM). For a fully local container run you'd need to add a Postgres service to `docker-compose.yml`. For day-to-day development the venv flow above is faster.

If you want to test the production build locally:

```bash
docker compose up -d --build
```

This serves nginx on port 80, proxying to the gunicorn `web` container. Make sure `.env` points at a Postgres instance reachable from the containers (use `host.docker.internal` for Docker Desktop, or the LAN IP of your Postgres host).

## Deployment

A GitHub Actions workflow (`.github/workflows/deploy.yml`) deploys to an EduCloud VM on every push to `main`:

1. **CI**: install requirements, run `python manage.py check`.
2. **Deploy**: SSH to the VM, `git pull`, `docker compose up -d --build`.

### Required repository secrets

| Secret | Purpose |
|---|---|
| `HOST` | EduCloud VM hostname or IP |
| `USERNAME` | SSH user on the VM |
| `PORT` | SSH port (usually `22`) |
| `SSH_KEY` | Private SSH key contents |
| `APP_DIR` *(optional)* | App path on the VM (defaults to `$HOME/apps/sports-tracker`) |

### VM one-time setup

1. Install Docker + Docker Compose plugin.
2. Clone this repo into the app directory.
3. Place a production `.env` in the same directory (with the real `SECRET_KEY`, `ALLOWED_HOSTS`, and DB connection details).
4. Make sure the VM can reach the Postgres host on the configured `DB_HOST`/`DB_PORT`.

### Manual deploy

```bash
git push origin main
```

Or run the workflow from the GitHub Actions tab via *workflow_dispatch*.

## Notes for future contributors

- **Image uploads** land in `./static/images/profiles/` on the host (bind-mounted into the `web` container; mounted read-only into nginx). nginx serves `/images/*` directly from this folder.
- **Calendar tokens** (`Profiles.calendar_token`) are minted lazily — when a user first opens the agenda or a crew page, a UUID is saved. Treat it as a secret; if a user shares their feed URL, regenerate the column to revoke.
- **No `get_or_create`** is used in this codebase — the project style is explicit `try: … get / except DoesNotExist: create` (see `users/signals.py` for the pattern).
- **No inline CSS** in templates — every visual rule lives in `static/styles/app.css`. The global `form { ... }` rule applies to *every* form element by default; if you add a form that shouldn't get the white box / shadow, override the relevant properties on a more specific selector.
- **Time zone** is `Europe/Amsterdam` (DST-aware). Datetimes are stored as UTC in the DB; templates and the ICS feed convert correctly.
