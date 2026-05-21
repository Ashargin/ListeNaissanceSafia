# Safia

Small Streamlit app for a birth wishlist. Content lives in `data/`; contributions are stored in **PostgreSQL** when configured, or in local `data/app.db` for development.

## Setup

Python 3.11+ recommended.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
```

Use this virtual environment when running the app (not a global Anaconda install with an older Streamlit).

Optional: copy `.env.example` to `.env` if your tooling loads it. See that file for `SAFIA_DEBUG`, `SAFIA_DATA_DIR`, `SAFIA_DATABASE_URL`, and optional SMTP variables.

## Run

From the repository root:

```bash
streamlit run safia/app.py
```

## Editing content

| File | Purpose |
|------|---------|
| `data/site.json` | Page title, hero title, cover image URL, intro text (Markdown) |
| `data/items.json` | Wishlist lines: name, description, price in euros, image URL |

## Database (contributions)

Gift totals and payment rows must survive redeploys on Streamlit Cloud. Use a hosted **PostgreSQL** database (e.g. [Neon](https://neon.tech), [Supabase](https://supabase.com), or Railway).

1. Create a project and copy the **connection string** (`postgresql://…`).
2. For SSL hosts, append `?sslmode=require` if it is not already in the URL.
3. Set the URL in secrets or env:

| Variable | Example |
|----------|---------|
| `SAFIA_DATABASE_URL` | `postgresql://user:pass@ep-….neon.tech/neondb?sslmode=require` |

On **Streamlit Community Cloud**, add to **App settings → Secrets**:

```toml
[database]
url = "postgresql://..."
```

If `SAFIA_DATABASE_URL` is **not** set, the app uses `data/app.db` (SQLite) — fine locally, **not** persistent on Cloud.

The table is created automatically on startup. To move an existing local SQLite file:

```bash
set SAFIA_DATABASE_URL=postgresql://...
python scripts/migrate_sqlite_to_postgres.py
```

## Payments (Stripe) and email

Payments use **Stripe Checkout**. Clicking **Pay** creates a checkout session and redirects you to Stripe in the **same tab**. After payment, Stripe sends you back to the wishlist with a thank-you message.

### Environment

| Variable | Example |
|----------|---------|
| `SAFIA_APP_URL` | `https://liste-naissance-safia.streamlit.app` |
| `STRIPE_SECRET_KEY` | `sk_test_…` from the [Stripe Dashboard](https://dashboard.stripe.com/test/apikeys) |

On **Streamlit Community Cloud**, set these in **App settings → Secrets** (see `.streamlit/secrets.toml.example`). Locally, use `.env` or export variables before `streamlit run`.

After payment, Stripe redirects back to your app. Safia verifies the session, confirms the gift in SQLite, updates the progress bar, and sends email:

- **Donor** — thank-you message to the email they entered on the form
- **You** — alert with donor name, item, amount, and their optional message

With `SAFIA_DEBUG=1`, **Simulate success / failure** links in the pending panel still work for testing without Stripe.

Email uses SMTP (`SMTP_*` in `.env.example`) or `[smtp]` in `.streamlit/secrets.toml`. Set **`SAFIA_NOTIFY_EMAIL`** (or `smtp.notify_email` in secrets) to your address for owner alerts.

## Keep the app awake (Streamlit Community Cloud)

Free Streamlit apps **sleep after about 12 hours** without real traffic. A simple HTTP ping (UptimeRobot, etc.) often returns **200** while the app is still asleep, so the monitor stays green but visitors see the sleep screen.

This repo includes a **GitHub Actions** workflow (`.github/workflows/keepalive.yml`) that every **4 hours** opens your app in **headless Chromium**, clicks **“Yes, get this app back up!”** if needed, and checks that the wishlist UI has loaded (intro text, **Contribuer** buttons, or the hero title inside Streamlit iframes).

### Setup (one time)

1. Push this repository to GitHub (same repo connected to Streamlit Cloud).
2. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**
3. Name: **`SAFIA_APP_URL`** — value: your public app URL, e.g. `https://liste-naissance-safia.streamlit.app` (no trailing slash).
4. **Actions** tab → run **“Keep Streamlit app awake”** once with **Run workflow** to test.
5. Optional: keep UptimeRobot as a backup alert, but rely on this workflow to prevent sleep.

Manual test locally:

```bash
pip install playwright
playwright install chromium
set SAFIA_APP_URL=https://your-app.streamlit.app
python scripts/keepalive.py
```

**Note:** Streamlit may change sleep rules over time; this is a common community workaround, not a guaranteed SLA. For always-on hosting, use a VPS or paid platform.

## Layout

| Path | Role |
|------|------|
| `safia/app.py` | Streamlit UI and contribution flow |
| `safia/ui.py` | Hero header, item cards, global CSS |
| `safia/content.py` | Load `data/site.json` and `data/items.json` |
| `safia/persistence.py` | PostgreSQL or SQLite totals and contribution rows |
| `safia/emailer.py` | Thank-you email |
| `safia/payments/stripe_checkout.py` | Stripe Checkout sessions |
| `safia/config.py` | Paths and flags from the environment |
| `data/` | Public JSON catalog; optional local `app.db` when PostgreSQL is not configured |
| `scripts/keepalive.py` | Browser wake-up for Streamlit Cloud (used by GitHub Actions) |
| `.github/workflows/keepalive.yml` | Scheduled keep-alive (every 4 hours) |
| `.streamlit/config.toml` | Streamlit defaults (non-secret) |
