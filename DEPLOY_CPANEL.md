# Deploying on cPanel shared hosting (e.g. WhoGoHost)

This covers what's different from a normal VPS deployment when you're on
shared hosting via cPanel's **Setup Python App** (Passenger) — no root
shell, no systemd, no control over the Apache config.

## 1. Create the Python App

cPanel → **Setup Python App** → create a new app:
- Python version: the highest 3.x cPanel offers (this project targets 3.11+)
- Application root: e.g. `sems` (a folder in your home directory)
- Application URL: your domain or subdomain

cPanel generates a `passenger_wsgi.py` in the app root with a virtualenv
shim at the top — leave that shim alone. The `passenger_wsgi.py` already
in this repo has the three lines that need to go *underneath* it (it also
works as-is if cPanel didn't pre-generate anything).

## 2. Upload the project

Upload/git-clone the repo contents into the application root cPanel created.

## 3. Install dependencies

cPanel's Python App page has a "pip install" field, or SSH into the venv
it created and run:
```
pip install -r requirements.txt
```
Notice there's no Redis or boto3 in the base `requirements.txt` — you
almost certainly don't need either on this tier (see §7). Only run
`pip install -r requirements-optional.txt` if you specifically set up S3
backups later.

## 4. Database — cPanel gives you MySQL, not Postgres

Create the database and a database user under cPanel → **MySQL Databases**,
and note the full db name/username (cPanel prefixes both with your
account username, e.g. `username_sems`).

In your environment variables (see §5), set:
```
DB_ENGINE=mysql
DB_HOST=localhost
DB_NAME=username_sems
DB_USER=username_semsuser
DB_PASSWORD=<the password you set>
DB_PORT=3306
```
This project uses PyMySQL (pure Python) rather than mysqlclient
specifically so it installs without a C compiler — already wired up in
`config/__init__.py`, nothing else to do here.

## 5. Environment variables

Set these on the Python App's **Environment Variables** section in cPanel
(not a committed `.env` file). At minimum:
```
SECRET_KEY=<generate one — see .env.example>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
SEMS_SITE_URL=https://yourdomain.com
DB_ENGINE=mysql
DB_HOST=localhost
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
SERVE_MEDIA_VIA_DJANGO=True
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<Gmail App Password>
HCAPTCHA_SITE_KEY=...
HCAPTCHA_SECRET_KEY=...
```
See `.env.example` in the repo for the full list with explanations.

## 6. Static files and media — no separate web server to configure

You can't edit Apache's config on shared hosting, so this project serves
both itself:
- **Static files** (CSS/JS): served by WhiteNoise, already wired into
  `MIDDLEWARE`/`STATICFILES_STORAGE`. After every deploy, run:
  ```
  python manage.py collectstatic --noinput
  ```
- **Media files** (passport photos, church logo): set
  `SERVE_MEDIA_VIA_DJANGO=True` in your environment variables (§5) —
  without it, Django only serves `/media/` when `DEBUG=True`, which you
  don't want in production.

## 7. Redis / rate-limiting cache

Skip it. `REDIS_URL` isn't set → the app falls back to Django's in-memory
cache automatically. That fallback's usual downside (each worker process
keeps separate counters) doesn't really bite here, since a cPanel Python
App is effectively a single long-running process anyway — not a fleet of
independent workers like a typical VPS deployment.

## 8. Migrations

Via SSH into the app's virtualenv, or a terminal cPanel provides:
```
python manage.py migrate
python manage.py createsuperuser   # first Super Administrator
```

## 9. Cron (scheduled backups)

cPanel → **Cron Jobs**. You need the *venv's* Python interpreter, not a
bare `python` — find the exact path on the Python App's page (cPanel shows
an "activate" command like `source /home/USERNAME/virtualenv/APPNAME/3.11/bin/activate`;
the interpreter sits at `.../3.11/bin/python`). Example cron command:
```
/home/USERNAME/virtualenv/APPNAME/3.11/bin/python /home/USERNAME/APPNAME/manage.py backup_db
```
`mysqldump` is usually available on cPanel without any extra setup: if it
turns out not to be, `backup_db` automatically falls back to Django's own
`dumpdata` — no action needed either way, just check Activity Logs in the
dashboard afterward to see which path it took.

## 10. HTTPS

Use cPanel's **AutoSSL** (free, usually already on). Apache generally
handles the HTTPS redirect itself at that layer, before Passenger ever
sees the request. Since `settings.py` defaults `SECURE_SSL_REDIRECT=True`
whenever `DEBUG=False`, having *both* Apache and Django try to force the
redirect — combined with Passenger not necessarily forwarding the
`X-Forwarded-Proto` header — can cause a redirect loop. On cPanel,
explicitly set in your environment variables:
```
SECURE_SSL_REDIRECT=False
BEHIND_PROXY=True
```
`BEHIND_PROXY=True` tells Django to trust `X-Forwarded-Proto` for
everything *other* than the redirect itself (secure cookies, and the
`https://` shown correctly in the public registration links on the
Settings page) without Django also trying to issue its own redirect.
If the registration links still show `http://` after this, Passenger
likely isn't forwarding that header at all on your specific plan — in
that case leave `BEHIND_PROXY=False` and rely on AutoSSL/Apache alone;
it's a cosmetic issue in the dashboard, not a security one, since the
actual connection is still HTTPS end-to-end.
