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

## October 2026 update — Rewards and featured businesses

Added:
- `/api/quran/daily` curated daily verse excerpt with Quran.com source link.
- `/api/rewards/wallet` referral code, verification progress, balances, terms.
- `/api/rewards/withdraw` GCash QR image claim (PNG/JPEG/WebP, <=350 KB), pending manual approval.
- `/api/rewards/claims` user claim history.
- `/api/admin/rewards` and `/api/admin/rewards/decision` for authenticated admins.
- Featured business links and pages `/static/wow-nina.html` and `/static/wow-web-studio.html`, including WOW SHOP Gumroad checkout links.

**NOT production-ready for cash rewards:** Claims are stored but no money is sent. All welcome bonuses and referrals start pending; admin must verify. The admin interface is API-only at `/api/docs`, with authenticated bearer token; there is no admin dashboard UI. Set an admin role securely in your own database after identity verification. Do not promote guaranteed rewards until policies, verification, and payout budget are ready. Current QR images are stored in SQLite and should be moved to private protected storage with deletion/retention rules before launch. Add rate limiting, stronger abuse detection, legal terms, and a privacy policy.

**CRITICAL Render database warning:** SQLite on Render ephemeral storage can lose data on redeploy/restart. Before live use, migrate user accounts, referrals and rewards to persistent Postgres/Supabase or mount a properly configured persistent disk, and back up existing data. This ZIP does NOT contain or migrate your live Render database. Do not overwrite live data.

**Logo assets:** The uploaded ZIP contained only WOW SUPER APP logo and hero image, not the original WOW NINA, WOW WEB STUDIO and WOW SHOP uploaded images. The featured pages therefore use text branding and verified user-supplied Facebook/Gumroad links. Add original logos after providing those files as part of a project bundle. Do not substitute image-search logos.

**Google Play:** This is a FastAPI web project, NOT an Android `.aab` build. A native Android shell (e.g. TWA/PWA with proper installability) and Play policy review, testing, store listing and signing remain required. Rewards and digital purchase rules must be reviewed before publishing.


## WOW JOBS
Any signed-in user can publish jobs at /jobs. Public listings are unverified; applicants can submit messages/contact details, owners can view applications and close posts, and users can report suspicious listings. API: GET/POST /api/jobs, GET /api/jobs/mine, DELETE /api/jobs/{id}, POST /api/jobs/{id}/apply, GET /api/jobs/{id}/applications, POST /api/jobs/{id}/report, GET /api/admin/jobs/reports.

**Deployment caution:** SQLite data on Render ephemeral storage can be lost on redeploy. Configure persistent database storage before accepting real accounts, jobs or applications. The Jobs page expects the same bearer token used by the main app, under localStorage key `wow_token` or `token`; if the frontend uses a different key, align it before launch. Test authorization and job flows in staging.


## Daily Quran + Messenger rewards
- Daily Qur’an: `/api/quran/daily` and homepage; rotates five curated excerpts at Philippine date boundary. Full Arabic verse available through Quran.com link, not stored locally.
- Rewards: registered users see verified balance and can request manual payout via Messenger; send GCash QR + claim ID + registered email to WOW WEB STUDIO official Facebook page.
- Admin review interface: `/static/rewards-admin.html`; paste an ADMIN session token. Admin must verify welcome eligibility, genuine referral accounts, and GCash details before approving. Messenger messages are NOT automatically integrated or verified.
- Existing in-app QR option remains.
- CRITICAL: SQLite database on Render may be ephemeral. Configure persistent storage and admin provisioning before cash rewards go live; no real payouts should be promised until fraud controls and budget are in place.


## Platform Admin Control Center
Visit `/admin` while logged in as an admin. Digital Shop products can be created, edited, and hidden; WOW NINA and Rewards link to their existing admin pages. Marketplace and Jobs are linked, not yet consolidated into a full moderation dashboard. Existing static Gumroad products remain hardcoded. Use DATABASE_PATH on persistent storage and UPLOAD_DIR on persistent storage for Render; otherwise data/uploads may disappear on redeploy. Do not enable real money rewards before security and payout review.


SUPER ADMIN: /admin shows member counts, signup activity, notifications, products, jobs, referrals. Notifications are in-app (not push/email). /api/news/daily reads BBC RSS at request time, requires outbound internet, and does not guarantee daily new articles. Keep a persistent database and media storage on Render before public launch.


## AI Services integration
See [AI_SERVICES_SETUP.md](AI_SERVICES_SETUP.md) for the updated AI text services, admin Marketing Studio, activation and verification limits. The earlier AI Studio demo description above describes the previous version.
