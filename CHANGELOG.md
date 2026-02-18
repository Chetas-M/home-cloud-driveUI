# Home Cloud Drive — Development Report
**Period:** Feb 15–17, 2026 · **Commits:** 6 · **Lines Added:** ~900+

---

## Features Shipped

### 1. Backend Authentication & Deployment Infrastructure
> Commit `98e08c1` · Feb 15

- JWT-based auth system (login, register, token refresh) with bcrypt password hashing
- `OAuth2PasswordBearer` flow with configurable token expiry (default 24h)
- Full deployment stack: `docker-compose.yml` (backend + nginx frontend), `Dockerfile`s, `nginx.conf` with security headers (CSP, X-Frame-Options, XSS filter), `deploy.sh`
- Async SQLAlchemy database layer with auto-creation of tables on startup
- `LocalStorage` service for file persistence on disk
- Frontend `AuthPage.jsx` with login/register forms and token persistence

---

### 2. Admin Panel + Secure File Sharing
> Commit `c71f388` · Feb 16

**Admin Panel:**
- `routers/admin.py` — list all users, get/update/delete user, system-wide stats, toggle admin role
- `get_admin_user` dependency enforcing admin-only access
- `AdminPanel.jsx` — dashboard with user table (quotas, storage, admin toggle), system stats cards
- Schemas: `AdminUserResponse`, `AdminUserUpdate`, `SystemStats`

**File Sharing:**
- `ShareLink` model — unique token, optional password (bcrypt), expiry, download limits
- `routers/sharing.py` — create link, access shared file (public), download shared file, list user's links, revoke link
- `ShareModal.jsx` — create links with password/expiry/download-limit options; copy URL; manage existing links
- Context menu "Share" option added

**Database Migrations:**
- Auto-migration system in `main.py` for adding new columns (`is_admin`, `content_index`, `thumbnail_path`) to existing SQLite tables without data loss

---

### 3. Server-Side Thumbnail Generation
> Commit `ce63d0d` · Feb 16

- `thumbnails.py` — Pillow-based generator supporting JPG, PNG, GIF, BMP, TIFF, WebP
- Resizes to 300×300 max (LANCZOS), converts RGBA/P → RGB, saves as optimized JPEG (quality 85)
- Thumbnails auto-generated on file upload, stored in per-user `thumbnails/` directory
- `GET /api/files/{id}/thumbnail` endpoint with query-param token auth
- `FileCard.jsx` updated to display server thumbnails
- Thumbnails cleaned up on file deletion
- `Dockerfile` updated with `libjpeg-dev`, `zlib1g-dev` system dependencies

---

### 4. Real-Time Upload Progress
> Commit `df409c7` · Feb 17

- `uploadFileWithProgress()` in `api.js` using `XMLHttpRequest` with native `upload.onprogress` events
- Rolling 5-sample speed average recalculated every 300ms with ETA computation
- Sequential per-file uploads with individual state tracking (`waiting` → `uploading` → `done` / `error`)
- `abort()` support for cancelling mid-upload
- `UploadProgress.jsx` complete rewrite: header with live speed badge (e.g. "⚡ 2.5 MB/s"), overall progress bar with shimmer animation, per-file list with status icons and ETA

---

### 5. Mobile Responsiveness Polish
> Commit `df409c7` · Feb 17

- **768px breakpoint:** Admin stats grid → 2 columns, admin table in horizontal scroll wrapper, share modal full-width, upload progress full-width
- **480px breakpoint:** Admin stats → single column, email column hidden in admin table, upload progress edge-to-edge

---

### 6. Sidebar Scroll Fix
> Commit `cbf50e1` · Feb 16

- Added `overflow-y: auto` to sidebar navigation for long nav lists

---

## Bugs Fixed

### 🐛 Thumbnail Endpoint Crash (FastAPI)
> Commit `a64e9fa` · Feb 16

**Problem:** The thumbnail endpoint used `Depends(get_current_user)` which requires a Bearer token in the `Authorization` header. But `<img src="...">` tags in the browser **cannot send custom headers** — they only make plain GET requests. This caused every thumbnail request to fail with a 401, and FastAPI raised internal errors.

**Fix:** Removed the `Depends(get_current_user)` dependency from the thumbnail endpoint. Replaced it with manual JWT decode from a `?token=` query parameter. The frontend constructs the thumbnail URL as `/api/files/{id}/thumbnail?token=<jwt>`, which works in `<img src>` tags.

---

### 🐛 Fake Upload Progress
> Fixed in commit `df409c7`

**Problem:** Upload progress was entirely simulated — a `setInterval` incremented progress by 10% every 100ms until 90%, then jumped to 100% when `fetch()` completed. Users had no idea of actual upload speed, remaining time, or whether a large file was stalling.

**Fix:** Replaced `fetch()` with `XMLHttpRequest` which provides real `upload.onprogress` events with `loaded`/`total` byte counts. Speed calculated via rolling average, ETA derived from remaining bytes ÷ speed.

---

### 🐛 Sidebar Overflow
> Fixed in commit `cbf50e1`

**Problem:** When navigation items exceeded the sidebar height (after adding Admin Panel, Shared Links, etc.), items were clipped and inaccessible.

**Fix:** Added `overflow-y: auto` to the sidebar nav container.

---

### 🐛 Admin & Share Components Not Mobile-Friendly
> Fixed in commit `df409c7`

**Problem:** `AdminPanel` and `ShareModal` were built with fixed-width layouts that broke on phones/tablets — tables overflowed, stats cards were too wide, modals were cut off.

**Fix:** Added responsive breakpoints at 768px and 480px with grid adjustments, horizontal scroll wrappers, hidden columns, and full-width modals.

---

## Files Changed Summary

| File | Action | Lines |
|---|---|---|
| `backend/app/thumbnails.py` | NEW | +52 |
| `backend/app/routers/admin.py` | NEW | ~200 |
| `backend/app/routers/sharing.py` | NEW | ~240 |
| `src/components/AdminPanel.jsx` | NEW | ~380 |
| `src/components/ShareModal.jsx` | NEW | ~280 |
| `src/components/AuthPage.jsx` | NEW | ~160 |
| `backend/app/routers/files.py` | MODIFIED | +66 |
| `backend/app/models.py` | MODIFIED | +30 |
| `backend/app/schemas.py` | MODIFIED | +65 |
| `backend/app/main.py` | MODIFIED | +25 |
| `backend/app/auth.py` | MODIFIED | +8 |
| `backend/Dockerfile` | MODIFIED | +2 |
| `backend/requirements.txt` | MODIFIED | +1 |
| `src/api.js` | MODIFIED | +81 |
| `src/App.jsx` | MODIFIED | +99 |
| `src/components/UploadProgress.jsx` | MODIFIED | +121 |
| `src/components/FileCard.jsx` | MODIFIED | +9 |
| `src/index.css` | MODIFIED | +275 |

**Build verification:** `vite build` — 0 errors, 1596 modules · CSS: 47.66 KB (8.48 KB gzip) · JS: 216.35 KB (64.99 KB gzip)
