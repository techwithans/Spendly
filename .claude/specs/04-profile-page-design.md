# Spec: Profile Page

## Overview

This feature replaces the `/profile` stub with a fully designed profile page showing static, hardcoded data. The goal is to establish the complete UI layout — user info card, transaction history table, summary stats, and category breakdown — before any real database queries are wired up in Step 5. Building the UI first lets the team validate the design in isolation and ensures the templates are ready for the backend-connection step.

**Addition — profile picture upload:** on top of the page built above, the signed-in user can set a profile picture (avatar image) the way Instagram or Facebook let you set one — upload a photo from the profile page, have it replace the initials avatar everywhere it's shown, and remove it later to fall back to initials again. This builds on the real, DB-backed profile page from Step 5 (`.claude/specs/05-profile-backend-routes.md`), not the hardcoded version above.

## Depends on

- Step 1: Database setup (schema must exist)
- Step 2: Registration (user accounts must be creatable)
- Step 3: Login + Logout (session must be set; `/profile` must be a protected route)
- Step 5: Profile Backend Routes (`.claude/specs/05-profile-backend-routes.md`) — real `_get_profile_user()` lookup this addition extends; `users.id` = `auth.users.id` (Supabase Auth)

## Routes

- GET /profile — render the profile page — logged-in only (redirect to /login if not authenticated)
- `POST /profile/picture` — upload/replace the signed-in user's profile picture — logged-in only
- `POST /profile/picture/remove` — delete the signed-in user's profile picture, reverting to the initials avatar — logged-in only

## Database changes

No database changes for the original hardcoded page — the existing `users` and `expenses` tables were sufficient.

**Addition — profile picture:**
- `users.avatar_url TEXT` (nullable) — new column, added in `init_db()` via `ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;` (a Postgres DDL statement, so it goes through `get_db()`/psycopg2 like the rest of `init_db()`, not the Supabase REST client). `NULL` means "no picture uploaded — show initials".
- New Supabase Storage bucket named `avatars`, public-read, created once in the Supabase dashboard (Storage isn't SQL DDL, so `init_db()` can't create it — document this as a manual one-time setup step in `.env.example`/README, the same way the `service_role` key is documented). Each user's picture is stored at a fixed path keyed by their id, e.g. `avatars/{user_id}.jpg`, so re-uploading overwrites in place rather than accumulating files.

## Templates

- Create: `templates/profile.html` — full profile page extending `base.html`; contains four sections:
  1. **User info card** — avatar initials, name, email, member-since date (all hardcoded)
  2. **Summary stats row** — total spent, number of transactions, top category (hardcoded)
  3. **Transaction history table** — list of recent expenses with date, description, category badge, amount (hardcoded rows)
  4. **Category breakdown** — per-category totals displayed as a simple list or progress-bar rows (hardcoded)

**Addition — profile picture:** Modify `templates/profile.html`'s `.profile-avatar`:
- When `user.avatar_url` is set, render `<img class="profile-avatar" src="{{ user.avatar_url }}" alt="{{ user.name }}'s profile picture">` in place of the initials `<div>`; when it's `None`, keep today's initials `<div>` exactly as-is — initials are the permanent fallback, not a placeholder to delete.
- Add a small circular "edit" affordance overlapping the bottom-right of the avatar (camera/pencil icon, Instagram/Facebook-style) that reveals a hidden `<input type="file" name="picture" accept="image/*">` inside a `<form method="post" action="{{ url_for('upload_profile_picture') }}" enctype="multipart/form-data">`. Clicking the icon triggers the hidden input (label-for or a tiny JS click-proxy in `static/js/main.js`); selecting a file auto-submits the form — no separate "upload" button, matching the one-tap Instagram/Facebook pattern.
- When a picture exists, also show a small text "Remove photo" link/button posting to `{{ url_for('remove_profile_picture') }}` (own small form, same `.txn-delete-form`-style POST-button pattern already used for deleting expenses), with a `confirm()` prompt like the existing expense-delete buttons.
- Surface upload errors (wrong file type, too large) via the same `{% if error %}` block convention used elsewhere on this page/site — no flash messages, no client-side validation library.

## Files to change

- `app.py` — replace the `/profile` stub with a real view function that:
  - Redirects unauthenticated users to `/login`
  - Passes hardcoded context variables to `profile.html`

**Addition — profile picture:**
- `app.py` — add `upload_profile_picture()` (`POST /profile/picture`) and `remove_profile_picture()` (`POST /profile/picture/remove`); extend `_get_profile_user()` to also select and return `avatar_url`
- `database/db.py` — `init_db()`: add the `avatar_url` column (see Database changes)
- `static/css/style.css` — new `.avatar-edit-btn`/`.avatar-wrap` rules for the overlay icon, using existing CSS variables only (no new hex values)
- `static/js/main.js` — small script: clicking the overlay icon opens the hidden file input; selecting a file submits its form (progressive enhancement, vanilla JS only — no frameworks)
- `.env.example` / README — note the one-time manual step of creating the public `avatars` Storage bucket in Supabase

## Files to create

- None — this extends the existing `templates/profile.html` and `app.py` in place; no new template or route file.

## New dependencies

No new dependencies for the original hardcoded page.

**Addition — profile picture:** `Pillow` (add to `requirements.txt`) — used server-side to actually decode and re-verify the uploaded file is a real image (never trust the browser-supplied `Content-Type` or filename extension) and to resize/re-encode it to a fixed max dimension before it's uploaded to Supabase Storage.

## Rules for implementation

- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()` if any DB call is ever needed
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Authentication guard: check `session.get("user_id")`; if absent, `redirect(url_for("login"))`
- All data passed to the template must be hardcoded Python dicts/lists in `app.py` — no DB queries in this step
- Category badges must use a CSS class, not inline colour styles

**Addition — profile picture:**
- Never trust the browser-supplied `Content-Type` or filename — open the upload with `Pillow` and call `.verify()` before accepting it as a real image
- Allow-list JPEG/PNG/WEBP only; reject anything else with an inline `{% if error %}` message, never a crash or a raw 500
- Enforce a max upload size (e.g. 5 MB, checked before or during read — don't buffer unbounded input) and a max stored dimension (e.g. 512×512), resizing server-side with Pillow before upload
- Store at a path keyed by the session's own `user_id` (e.g. `avatars/{user_id}.jpg`) — never accept a client-supplied user id or path for where the file is written
- `upload_profile_picture()` and `remove_profile_picture()` both start with the same `if not session.get("user_id"): return redirect(url_for("login"))` guard as `profile()`
- Removing a picture must both clear `users.avatar_url` and delete the stored object in the `avatars` bucket — never leave the two out of sync (a cleared column pointing at nothing is fine; a deleted object still referenced by `avatar_url` is not)
- Re-uploading overwrites the same storage path rather than creating a new object each time, so no orphaned files accumulate per user
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles

## Definition of done

- [ ] Visiting `/profile` without being logged in redirects to `/login`
- [ ] Visiting `/profile` while logged in returns HTTP 200
- [ ] The page displays a user info card with a name and email
- [ ] The page displays at least three summary stat values (e.g. total spent, transaction count, top category)
- [ ] The page displays a transaction history table with at least three hardcoded rows
- [ ] The page displays a category breakdown section with at least three categories
- [ ] The navbar shows the logged-in state (username + logout link)
- [ ] No hex colour values appear in `profile.html` — only CSS variables.

**Addition — profile picture:**
- [ ] A signed-in user can upload a JPEG/PNG/WEBP image from `/profile` and it replaces the initials avatar immediately after upload
- [ ] Uploading a non-image file (e.g. a `.txt`, or an `.exe` renamed to `.png`) is rejected with a clear inline error, not a crash
- [ ] Uploading a file over the size limit is rejected with a clear inline error
- [ ] A user can remove their profile picture; the avatar reverts to their initials and the stored file is deleted from the `avatars` bucket
- [ ] Re-uploading a new picture replaces the old one in place — no orphaned files accumulate in Storage
- [ ] There is no way, via the form or a crafted request, for a signed-in user to change another user's picture
- [ ] The upload/remove controls are keyboard accessible and have appropriate `alt`/`aria-label` text
