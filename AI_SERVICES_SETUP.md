# WOW AI Services integration

Changes prepared against GitHub commit c7bebf74c0ead0e746c1f1a65b1985a4702d718c.

## Included
- `/ai-services`: captions, product descriptions, business copy and video scripts in English, Tagalog or Bisaya. Requires login. Recent results are private to each user.
- `/admin/marketing`: existing admin-role checks, template captions, optional AI captions, promotional PNG posters, 12-second silent video cards, and approval/rejection saved in the database. Approval does not publish social posts. The video is a promotional card sequence, not an app UI recording.
- Admin dashboard navigation and homepage AI Studio navigation.
- Server-only OpenAI Responses API integration. No API key is included. Existing demo credits are used; no payment checkout is enabled. Failed requests roll back credit deductions. Text generations are limited to 20 per user per hour.
- Image/logo AI and generative video are explicitly unavailable. Poster/video card exports use local rendering rather than image/video AI.

## Install on the existing Render app
1. Upload/commit these updated files to `wowweb1991/wow-super-app`, preserving the current project and live database. This archive contains no database, uploads, credentials or user records.
2. In Render, open the existing service → Environment → add `OPENAI_API_KEY` as a secret and `OPENAI_TEXT_MODEL=gpt-4.1-mini` (or an enabled compatible text model). Save and redeploy. Do not put the key in HTML or GitHub. API use is billed separately by the provider.
3. Keep the existing service start command, typically `uvicorn main:app --host 0.0.0.0 --port $PORT`. Install dependencies from requirements.txt.
4. Ensure `DATABASE_PATH` points to the existing persistent database. Back up live data before redeploying if storage persistence is uncertain. This update uses additive CREATE TABLE IF NOT EXISTS statements for marketing drafts.
5. MP4 export requires ffmpeg and libx264 on the server. PNG export requires Pillow (already in requirements.txt). If ffmpeg is absent, the API returns 503; other tools continue to work.
6. Sign in on the homepage with an existing administrator account, then open `/admin/marketing`. Regular users open `/ai-services`. No account is automatically promoted to admin.
7. Try one AI caption to verify the actual provider connection. No real provider call was made during local tests because no key was available.

## Validation
Run `python -m pip install -r requirements.txt httpx` and `python -m unittest discover -s tests -v`.
Tests cover unauthorized/admin access, credit rollback, isolated generation history, mocked successful text generation, PNG and MP4 exports, approval states, and JavaScript syntax. Live provider behavior and deployment were not verified.

## Unified Admin & Super Admin update
`/admin`, `/super-admin` and `/admin/super` now open the same dashboard with the existing administrator role. This update does not grant administrator access to new accounts or introduce a separate super-admin privilege level.

The dashboard combines platform statistics and activity, AI Services and Marketing Studio navigation, WOW NINA, rewards, motivation and digital product management. Jobs & Hiring now includes searchable/paginated open and closed job posts, report review, application details on demand and an admin-only close-post action. Closing a post preserves the record and existing applications while preventing new applications. Existing job-posting and application pages remain included.

Upload the complete consolidated project from this ZIP rather than installing earlier update ZIPs separately. Live GitHub/Render deployment still requires authorized write access. AI text still requires the server-side provider key. Admin access must already be provisioned in the persistent database; this package contains no live user data.
