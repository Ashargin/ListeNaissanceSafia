# Safia

Small Streamlit app for a birth wishlist. Content lives in `data/`; contributions are stored locally in `data/app.db`.

## Setup

Python 3.11+ recommended.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
```

Use this virtual environment when running the app (not a global Anaconda install with an older Streamlit).

Optional: copy `.env.example` to `.env` if your tooling loads it. See that file for `SAFIA_DEBUG`, `SAFIA_DATA_DIR`, and optional SMTP variables.

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

## Layout

| Path | Role |
|------|------|
| `safia/app.py` | Streamlit UI and contribution flow |
| `safia/ui.py` | Hero header, item cards, global CSS |
| `safia/content.py` | Load `data/site.json` and `data/items.json` |
| `safia/persistence.py` | SQLite totals and contribution rows |
| `safia/emailer.py` | Thank-you email |
| `safia/payments/stripe_checkout.py` | Stripe Checkout sessions |
| `safia/config.py` | Paths and flags from the environment |
| `data/` | Public JSON catalog + generated `app.db` (gitignored) |
| `.streamlit/config.toml` | Streamlit defaults (non-secret) |
