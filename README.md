# WOW SUPER APP — Flask / Supabase / Render

This is a functional MVP, **not a fully launched commercial platform**. Includes signup/login, product listings, community posts/comments/likes, service listings/inquiries, basic admin access, and an AI prompt helper. **No checkout, payment collection, actual AI API calls, file uploads, booking calendar, or full moderation system yet.**

## Deploy
1. Back up your existing GitHub `main.py` and `requirements.txt`. Upload these files to the repository root, keeping the filenames exact. Add `schema.sql` and this README.
2. In Supabase, open **SQL Editor**, paste `schema.sql`, and run it once. Enable Email auth under Authentication > Providers. If Confirm email is enabled, new users must verify first.
3. In Render, open your **Web Service** > **Environment**. Add `SUPABASE_URL` (Supabase Project URL), `SUPABASE_PUBLISHABLE_KEY` (publishable/anon key, not secret/service-role), and `FLASK_SECRET_KEY` (long randomly generated secret). Optionally `ADMIN_USER_IDS` (comma-separated Supabase auth user UUIDs).
4. **Never** put `sb_secret_*`, service-role keys, or passwords in GitHub or screenshots. Rotate any secrets already shared.
5. In Render Settings, set **Build Command** `pip install -r requirements.txt` and **Start Command** `gunicorn main:app --bind 0.0.0.0:$PORT`.
6. Deploy latest commit. Open `/signup`, `/login`, `/marketplace`, `/community`, `/services`, `/ai`, `/admin`.
7. Existing user accounts stay in the same Supabase Auth project, provided you keep its URL and key. Database tables are new; this package does not migrate any old app data.

## Notes
- Supabase RLS limits writes to the signed-in user and allows signed-in users to read public listings.
- Admin dashboard is only accessible to IDs in `ADMIN_USER_IDS`, but counts are subject to user RLS and 1,000-row limits. Use Supabase dashboard for real moderation.
- Product image field accepts a publicly hosted image URL, not uploads.
- Inquiry messages are stored in Supabase; there is not yet a seller inbox UI or notification delivery.
- For production add CSRF protection, rate limiting, abuse reporting/moderation, privacy policy, security testing, backups, and payment-provider integration before accepting money.
