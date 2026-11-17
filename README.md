# EduShare

EduShare is a responsive Flask + MySQL progressive web app for students to **buy, sell, exchange, donate and borrow** educational materials. It includes authentication, role-based administration, private messaging, notifications, search/filters, nearby discovery, and an installable PWA shell.

> **No database credentials or production secrets are included in this repository.** You must supply your own through environment variables. When `DATABASE_URL` is unset, the app falls back to a local SQLite file so it can be demonstrated without a MySQL server.

---

## Features

| Area | What works |
| --- | --- |
| Accounts | Register, log in, logout, remembered sessions, password validation, password reset (e-mail when SMTP is configured, on-screen link otherwise), suspended-account enforcement. |
| Home / dashboard | Recent listings, category shortcuts, donation/exchange/library highlights, personal request summaries, nearby items. |
| Marketplace | Create/edit/delete listings with multi-image upload validation, details, price/condition/level filters, sorting, purchase interest and seller contact. |
| Exchange | List books for exchange, send swap requests with an optional offered book, accept/reject/complete lifecycle with notifications. |
| Donation | Donate free books, request donated books, approve/reject/hand-over lifecycle. |
| Community library | Add books, borrow requests, approve/reject, confirm handover with due dates, return confirmation, overdue detection and reminders. |
| Search | Global search across materials and library books, with category, level, condition, price, location and availability filters. |
| Nearby | Browser geolocation (opt-in) or saved coordinates; Haversine distance ranking and `/api/nearby`. |
| Messaging | Two-person conversations scoped to participants, read state, server-rendered chat plus JSON polling endpoints. |
| Profile | Public/private profiles, edit details/avatar, change password, personal listing/request/loan history. |
| Notifications | In-app notification centre, mark-one/read-all, notification links, JSON API. |
| Admin | Protected overview, user suspension/role changes, listing removal, report resolution, category management, donation and borrowing monitoring. |
| PWA | Web manifest, icons, install prompt, offline page, service worker that caches **only public static assets**. |

---

## Tech stack

- Python 3, Flask 3, Flask-SQLAlchemy, SQLAlchemy ORM
- MySQL via `mysql+pymysql://...` (SQLite fallback for local demos)
- Flask-Login, Flask-WTF/WTForms, Flask-Limiter, Werkzeug password hashing
- Jinja templates, custom mobile-first CSS, local Bootstrap Icons
- Service worker, web manifest, PNG/maskable icons
- pytest for automated tests
- Gunicorn + Procfile / `render.yaml` for deployment

---

## Quick start (local SQLite)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your environment file
copy .env.example .env          # Windows
cp .env.example .env            # macOS/Linux
```

Edit `.env` and set a real `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Leave `DATABASE_URL=` empty to use `instance/edushare.sqlite3`.

```bash
# 4. Initialise tables and categories
flask --app app init-db

# 5. Optional: create development-only sample data
flask --app app seed-demo

# 6. Run the app
python run.py
```

Open <http://localhost:5000>.

### Demo accounts (development only)

`flask --app app seed-demo` creates these accounts with password **`Demo@1234`**:

| Email | Role |
| --- | --- |
| `demo.student@example.com` | Student |
| `demo.seller@example.com` | Student with listings |
| `demo.librarian@example.com` | Library book owner |
| `demo.admin@example.com` | Administrator |

Never use these accounts or password in production.

---

## Using MySQL

1. Create a database and a dedicated MySQL user yourself. Grant that user privileges on the EduShare database only.
2. Set `DATABASE_URL` in `.env` using the values provided by your host:

   ```text
   DATABASE_URL=mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST:3306/DB_NAME?charset=utf8mb4
   ```

3. Initialise the schema with either:

   ```bash
   flask --app app init-db
   ```

   or, if you prefer raw SQL:

   ```bash
   mysql -h DB_HOST -u DB_USER -p DB_NAME < database/init_mysql.sql
   mysql -h DB_HOST -u DB_USER -p DB_NAME < database/seed_categories.sql
   ```

   `database/init_mysql.sql` and `database/seed_categories.sql` both reference a database named `edushare`; change the `CREATE DATABASE`/`USE` lines in both files if your host assigned a different name.

`AUTO_CREATE_TABLES=1` (the default) lets Flask create missing tables at startup and seed categories automatically. Set it to `0` once you manage schema changes with migrations; the SQL files remain available as a reference schema generated from the models (`python tools/export_mysql_schema.py`).

---

## Environment variables

See `.env.example` for the full template.

| Variable | Purpose | Production notes |
| --- | --- | --- |
| `FLASK_CONFIG` | `development`, `testing`, `production`, or `default`. | Use `production`. |
| `SECRET_KEY` | Flask session/token signing key. | **Required** in production; generate a long random value. |
| `DATABASE_URL` | SQLAlchemy database URL. | **Required** in production; use MySQL, not SQLite. |
| `SESSION_COOKIE_SECURE` | Send session cookies only over HTTPS. | Set to `1`. |
| `RATELIMIT_ENABLED` | Enable Flask-Limiter. | Keep `1`. |
| `RATELIMIT_STORAGE_URI` | Shared rate-limit store. | Use Redis when running multiple workers. |
| `TRUST_PROXY` | Trust `X-Forwarded-*` headers from a reverse proxy. | Set to `1` on Render so rate limits use the real client IP. Leave `0` if exposed directly. |
| `AUTO_CREATE_TABLES` | Create missing tables on startup. | Keep `1` for simple deployments; disable with migrations. |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` | Optional SMTP password-reset delivery. | Without SMTP, production shows only a generic confirmation; development/testing may display a local reset link. |
| `FLASK_DEBUG` | Development debug mode. | Never enable in production. |

The app raises a clear startup error if production is selected without `SECRET_KEY` or `DATABASE_URL`.

---

## CLI commands

```bash
flask --app app init-db                 # create tables and seed categories
flask --app app seed-demo               # opt-in development sample data
flask --app app check-due               # mark overdue loans / create reminders (cron-friendly)
flask --app app set-admin user@example.com  # grant admin role to an existing account
flask --app app routes                  # list all routes
```

Schedule `flask --app app check-due` with cron or a scheduler (for example daily) to keep due-date notifications current. The home page and library page also call the check.

---

## Project structure

```text
EDUSHARE/
├── app/
│   ├── __init__.py          # app factory, security headers, error handlers, CLI commands
│   ├── extensions.py        # shared db, login manager, CSRF and limiter
│   ├── models.py            # all SQLAlchemy models
│   ├── forms.py             # all WTForms forms and validation
│   ├── utils.py             # auth helpers, uploads, notifications, search, distance, due dates
│   ├── seed.py              # category seeder + opt-in demo data
│   ├── admin/               # admin blueprint
│   ├── api/                 # JSON API blueprint
│   ├── auth/                # registration/login/password reset
│   ├── donation/            # donation listings and request workflow
│   ├── exchange/            # exchange listings and request workflow
│   ├── library/             # community library and borrowing workflow
│   ├── main/                # home, dashboard, search, location, PWA shell
│   ├── marketplace/         # listing CRUD, details, interest, reports
│   ├── messaging/           # conversations and messages
│   ├── notifications/       # notification centre
│   ├── profile/             # profiles and password change
│   ├── static/              # CSS, JS, manifest, service worker, icons, vendor icons
│   └── templates/           # Jinja templates (including admin and error pages)
├── database/
│   ├── init_mysql.sql       # generated MySQL schema
│   └── seed_categories.sql  # default categories
├── tools/
│   ├── export_mysql_schema.py
│   └── generate_icons.py
├── tests/                   # pytest suite
├── config.py                # environment-driven configuration
├── run.py                   # local development server entry point
├── Procfile                 # Gunicorn process for Heroku-style hosts
├── render.yaml              # Render blueprint (values filled in the dashboard)
├── requirements.txt
└── .env.example
```

---

## PWA and privacy

- `app/static/manifest.json` defines the installable app, icons, shortcuts and standalone display.
- `/service-worker.js` is served from the root for correct scope and uses `Service-Worker-Allowed: /`.
- The service worker precaches only public assets (`/offline`, CSS, JS, fonts, icons, manifest).
- Navigation requests are always fetched live; when offline they fall back to `/offline`.
- Private prefixes (`/auth/`, `/messages`, `/profile`, `/notifications`, `/admin/`, `/api/`, `/dashboard`, `/books/new`, `/location`, `/static/uploads/`) are never intercepted or cached.
- Private data is never stored in `localStorage`; uploaded listing images are served from `/static/uploads/` with realistic filenames hidden behind UUID storage names.

---

## Security notes

- Passwords use Werkzeug `scrypt` hashes; Flask-Login manages sessions.
- All forms use Flask-WTF CSRF protection in normal operation.
- Flask-Limiter adds global and per-route limits on sensitive endpoints.
- Uploads are validated by extension, MIME type, file size and magic-byte signature.
- Role checks protect admin routes; ownership checks protect listings, requests, conversations, library records and notifications.
- Security headers include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a `Content-Security-Policy` with `script-src 'self'`.
- Set `SESSION_COOKIE_SECURE=1` and serve HTTPS in production.

---

## Tests

```bash
python -m pytest -q
```

The suite covers authentication and validation, public/PWA assets, responsive shell assertions, marketplace CRUD/search/purchase interest/reporting, exchange lifecycle, donation lifecycle, library borrow/approve/handover/return/overdue flow, admin RBAC and moderation, messaging and API isolation, notifications, CLI commands, and demo seeding. Tests use an in-memory SQLite database with CSRF and rate limiting disabled.

---

## Deploying to Render

1. Create a new **Web Service** from this repository (or apply `render.yaml`).
2. Use Python runtime, `pip install -r requirements.txt` as the build command, and `gunicorn "app:create_app()"` as the start command (both are already in `render.yaml`/`Procfile`).
3. Add these environment variables in the Render dashboard (the blueprint marks secrets as `sync: false`, so nothing is invented in the repo):
   - `FLASK_CONFIG=production`
   - `SECRET_KEY` — generate your own random value
   - `DATABASE_URL` — your external MySQL connection string
   - `SESSION_COOKIE_SECURE=1`
   - `AUTO_CREATE_TABLES=1`
   - `RATELIMIT_STORAGE_URI` — a shared Redis URL if you use more than one instance
   - optional SMTP variables for password-reset e-mails
4. Deploy, then run `flask --app app init-db` once via Render Shell if you disabled automatic table creation.
5. Create your first administrator with `flask --app app set-admin your@email.com`.

Render does not provide managed MySQL; use any MySQL-compatible host and supply its credentials through `DATABASE_URL`. Do not commit `.env` or credentials.

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'app'`** when running a tool script directly: run scripts from the project root, or use the provided scripts which add the root to `sys.path`.
- **Password reset shows a link instead of sending mail:** SMTP is not configured. In development/testing the link is displayed locally; in production only a generic confirmation is shown, so configure the `MAIL_*` variables to deliver real reset links.
- **MySQL connection errors:** confirm the PyMySQL URL format, host port, database name, user privileges, and that the MySQL server allows connections from your host.
- **Uploads disappear after restart:** `app/static/uploads/` is local ephemeral storage on most platforms. For durable production uploads, replace `save_images()` with object storage such as S3/R2 and keep the same `MaterialImage.filename` contract.
- **Deprecation warnings from WTForms/Flask-Login:** these come from installed library versions and do not affect functionality.
