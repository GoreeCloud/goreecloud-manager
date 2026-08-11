# GoreeCloud Manager

GoreeCloud Manager is an original GoreeCloud application intended to become the central management and operational console for the GoreeCloud personal-cloud platform.

## Current Status

**v0.1 scaffold — development only.** The current code establishes the authenticated application shell, integration registry, health endpoint, Docker packaging, tests, and project documentation. Live infrastructure integrations are intentionally not enabled yet.

## Principles

- Private by default.
- Read-only integrations first.
- Least privilege.
- No reusable secrets in source control.
- No direct public backend exposure.
- No Docker socket mounted into the Manager container.
- Specialized services remain authoritative for their own operations.
- Backup and recovery are required before production dependency.

## Initial Stack

- Python 3.14
- Django 5.2 LTS
- Server-rendered Django templates
- SQLite for development / initial MVP
- Gunicorn
- WhiteNoise for containerized static-file serving
- Docker / Docker Compose
- GitHub Actions

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
export DJANGO_SECRET_KEY='development-only-secret'
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with the administrator account you created.

## Tests

```bash
python manage.py check
python manage.py test
```

## Docker

```bash
cp .env.example .env
# Set a unique DJANGO_SECRET_KEY in .env before starting.
docker compose up --build
```

The development Compose file binds Manager to loopback only. Production publication through GoreeCloud private DNS, NetBird, and Caddy is intentionally deferred until production-readiness validation.

## Documentation

See [`docs/project-specification.md`](docs/project-specification.md) for the v0.1 implementation blueprint.

## License

MIT. See [`LICENSE`](LICENSE).
