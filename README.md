# WOW Super App — Working MVP

A responsive multi-user web app with real account registration/login, marketplace listings, community posts, services, service inquiries, content ownership and admin moderation support.

## Start locally

Requires Python 3.10+.

```bash
cd wow-super-app
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 . API documentation: http://localhost:8000/api/docs

## Test the multi-user features

1. Create account A. Publish a product, a community post, and a service.
2. Log out and create account B. See account A's content and request account A's service.
3. Log back in as account A. Open **My Requests** to see account B's request.

## Architecture

Browser (responsive HTML/CSS/JS) → FastAPI REST API → SQLite (persistent `wow.db`). Authentication uses PBKDF2 password hashing, cryptographically random bearer tokens and database-backed sessions. Each post/listing/service is tied to a user. Server-side ownership checks protect deletions. Inputs are validated and output is HTML-escaped.

## IMPORTANT: Before public launch

This is a functional MVP, **not a production-ready platform for thousands of users**. It has no payment processing, private chat, image uploads, email verification, password recovery, rate limiting, spam protection, reporting workflow, privacy policy, or backups. The service-request message is visible to the requester and service provider. User data is stored on the server running the app, not synchronized between separate installations.

Recommended production upgrades:

- Replace SQLite with managed PostgreSQL and migrations; use connection pooling.
- Add email verification, password reset, token revocation/expiry housekeeping, abuse prevention, rate limiting, CAPTCHA and logging.
- Use HTTPS, domain, secure deployment, backups, monitoring, and privacy/terms pages compliant with applicable law.
- Add object storage for images, search indexes, pagination/caching, payment provider integration and moderation queues.
- Run multiple stateless API instances behind a load balancer with a shared database and session store.
- Set up an initial administrator using a trusted one-time database migration (never make all newly registered users admins).

No purchases or money transfers occur in this MVP. Prices are display-only. There is no real checkout. No live hosting/domain is included.

## AI Studio MVP extension
AI Studio includes per-user demo credit wallets (10 starter credits), server-side deductions,
generation history, a free caption template and a 2-credit description template.
Poster, logo, video, and website AI generators are visibly marked coming soon.
The preview pricing is **not** a payment checkout; no real payments or external AI models are connected.
Before accepting payments: integrate a payment processor using verified signed webhooks,
idempotent fulfillment, refund handling, admin reconciliation, and secure production auth.
For scale: migrate SQLite to PostgreSQL, add queues/rate limits, object storage and monitoring.
