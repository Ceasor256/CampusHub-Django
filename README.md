# CampusHub (Django)

Uganda-first campus marketplace: students buy and sell, post and complete gigs, and claim deals from businesses near their university. Multi-campus from day one.

This is the **Django version** of CampusHub. It has the same product, design and business rules as the Next.js version in the parent folder, built the Django way: server-rendered templates, Django forms, Django auth and sessions.

**Status: Phase 1 MVP.** Marketplace, gigs, business deals, messaging, notifications, reporting and moderation, the staff dashboard and analytics are implemented and database-backed. Payments are an integration boundary with a test provider only (see `../docs/PAYMENTS.md`; the same plan applies here, with `payments/providers.py` as the boundary).

## Stack

| Layer | Choice |
| --- | --- |
| Framework | Django 6.1, Python 3.12+ (tested on 3.14) |
| Database | SQLite for local dev; PostgreSQL in production via `DATABASE_URL` |
| UI | Django templates + Tailwind CSS 4 (precompiled to `static/css/app.css`), ~2 KB vanilla JS |
| Auth | Django auth (custom email-login `User`), DB sessions, built-in password hashing and reset tokens |
| Security | CSRF, Django 6 Content-Security-Policy middleware (no inline scripts), HSTS/secure cookies in production |
| Images | Pillow: verified, resized to 1600 px, re-encoded as WebP, EXIF/GPS stripped |
| Static files | WhiteNoise |

## Run it locally (Windows PowerShell)

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

```powershell
.\.venv\Scripts\python.exe manage.py seed
```

```powershell
.\.venv\Scripts\python.exe manage.py runserver 8010
```

Open http://localhost:8010. On macOS/Linux use `.venv/bin/python` instead.

> On this machine the venv lives at `C:\Users\pc\.venvs\campushub-django` because the session folder's path is too long for pip. Use that `python.exe` in the commands above.

`seed` loads reference data (7 Ugandan universities, campuses, categories) plus **sample content** flagged `is_sample` (badged "Sample" and excluded from analytics). The development logins (admin, moderator, student) are listed in `core/seed.py` → `DEV_ACCOUNTS`. In production use `manage.py seed --reference-only`. Sample data is refused when `DJANGO_DEBUG` is off.

Verification and password-reset emails are not sent in development. They appear at http://localhost:8010/dev/outbox/.

## Commands

| Command | Purpose |
| --- | --- |
| `manage.py test tests` | Run the 22 tests (business rules + HTTP flows + permissions) |
| `manage.py makemigrations` / `migrate` | Schema changes |
| `manage.py seed [--reference-only]` | Reference data (+ sample data in dev) |
| `manage.py make_admin you@example.com` | Grant the CampusHub admin role to an existing account |
| `manage.py createsuperuser` | Access to `/django-admin/` (technical back office); also grants the admin role |
| `npm install && npm run css` | Rebuild `static/css/app.css` after changing templates or `assets/app.css` (Node only needed for styling work) |

## Configuration

Copy `.env.example` to `.env` (it's read automatically) or set real environment variables. Key settings: `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `EMAIL_*`, `REDIS_URL`, `PAYMENT_PROVIDER`, `PAYMENT_WEBHOOK_SECRET`.

## Deploying

1. Provision PostgreSQL (Supabase, Neon, Railway, Render) and set `DATABASE_URL`.
2. Set `DJANGO_DEBUG=false`, a strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain` and `APP_URL`.
3. `pip install -r requirements-prod.txt`
4. `python manage.py migrate && python manage.py seed --reference-only && python manage.py collectstatic --noinput`
5. Run with `gunicorn config.wsgi --workers 3` behind HTTPS.
6. Uploaded photos: set Django's `STORAGES["default"]` to S3-compatible storage (`django-storages`) so they survive redeploys.
7. Email: set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and the SMTP settings (or a provider).
8. Multiple workers: set `REDIS_URL` so rate limits are shared.
9. Work through `../docs/LAUNCH_CHECKLIST.md` (legal, privacy, tax, payments) before going public.

## Layout

```
config/        settings, URLs
core/          campuses, categories, reports, reviews, notifications, audit log, settings store,
               utils (money, phone, permissions, rate limiting), image processing, template tags, icons, seed
accounts/      User (email login) + StaffRole, registration, verification, reset, profile, account deletion
marketplace/   listings, photos, favourites, mark-as-sold
gigs/          gigs, applications, completion, disputes, reviews
deals/         businesses, verification requests, deals, claims, redemption
messaging/     conversations and messages
payments/      transactions, payments, webhook boundary (test provider)
staff/         dashboard, moderation, analytics (all actions via staff/services.py)
templates/     all HTML; templates/includes holds shared components
tests/         test_utils.py, test_services.py, test_views.py
```

Every rule lives in an app's `services.py` and re-checks permissions there (`core.utils.assert_*`), so hiding a button is never the only protection.
