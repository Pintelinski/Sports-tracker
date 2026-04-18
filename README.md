# Sports Tracker

Sports Tracker is a Django application for planning and managing rowing training schedules.
It includes an agenda/calendar flow, crews, memberships, and profile management.

## Tech Stack

- Python 3.11
- Django 5
- Gunicorn
- Nginx
- Docker + Docker Compose
- GitHub Actions for CI/CD

## Local Development (without Docker)

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Dockerized Run (local)

1. Create a `.env` file in the project root (for now this can be minimal):

```env
DEBUG=False
SECRET_KEY=change-me
ALLOWED_HOSTS=*
```

2. Build and run containers:

```bash
docker compose up -d --build
```

3. Open:

```text
http://localhost
```

## CI/CD to EduCloud VM (GitHub Actions)

The workflow file is:

- `.github/workflows/deploy.yml`

It does:

1. CI step: install dependencies and run `python manage.py check`.
2. Deploy step: SSH into the EduCloud VM, pull latest code, run `docker compose up -d --build`.

### Required GitHub Repository Secrets

- `HOST` -> EduCloud VM hostname or IP
- `USERNAME` -> SSH user on VM
- `PORT` -> SSH port (usually `22`)
- `SSH_KEY` -> private SSH key (contents)

Optional:

- `APP_DIR` -> project path on VM. If missing, workflow uses `$HOME/apps/sports-tracker`.

### VM Preparation (one-time)

On the EduCloud VM:

1. Install Docker and Docker Compose plugin.
2. Clone this repository into your app directory.
3. Ensure your SSH key pair is configured so GitHub Actions can SSH to the VM.
4. Ensure `.env` exists in the VM app directory.

## Deploy Process

Push to `main`:

```bash
git add .
git commit -m "Update app"
git push origin main
```

Then GitHub Actions runs CI and deploy automatically.

You can also run deployment manually from GitHub Actions with `workflow_dispatch`.


