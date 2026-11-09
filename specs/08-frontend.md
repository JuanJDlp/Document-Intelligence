# 08 — Frontend (web portal)

Implementation: `app/frontend/`. Static files only: HTML, CSS, and vanilla JavaScript (ES2020+). No framework, no bundler, no build step (`ADR-022`). The site is served by CloudFront from S3 (`INF-CDN-*`).

## 1. Pages

| File | Route purpose | Auth |
|---|---|---|
| `index.html` | Landing + login and registration forms | public |
| `dashboard.html` | Upload form and processing history table | authenticated |
| `document.html?id=<document_id>` | Document metadata, processing status, extraction result | authenticated |

- **FE-PAGE-01** (active) Page titles are in English. UI copy is in English (`AGENTS.md` section 13).
- **FE-PAGE-02** (active) Unauthenticated access to `dashboard.html` or `document.html` redirects to `index.html`.
- **FE-PAGE-03** (active) Logout is available on every authenticated page and calls `POST /api/v1/auth/logout`, then clears local state.

## 2. Configuration

- **FE-CFG-01** (active) The API base path is the constant `/api/v1` (relative). The frontend is same-origin with the API through CloudFront (`INF-CDN-05`, `ADR-030`), so no host name is configured in the frontend code and no `config.js` is needed.
- **FE-CFG-02** (active) `scripts/deploy_frontend.sh` uploads `app/frontend/` to the frontend bucket and sets `Cache-Control: no-cache` on HTML and `assets/*` files, then creates a CloudFront invalidation for `/*`.

## 3. Behavior

### 3.1 Authentication
- **FE-AUTH-01** (active) Login stores the bearer token and `expires_at` in `sessionStorage` (per-tab convenience only, `FE-AUTH-04`).
- **FE-AUTH-02** (active) Every API call sends `Authorization: Bearer <token>`. A `401` response clears the token and redirects to `index.html` with a message.
- **FE-AUTH-03** (active) Registration validates the same rules as the API (`API-AUTH-02`, `API-AUTH-03`) client-side for better feedback. The server remains authoritative.
- **FE-AUTH-04** (active) Tokens are not stored in `localStorage`. Storage access is wrapped in try/catch and the app works (with login required each time) when storage is unavailable.

### 3.2 Upload
- **FE-UP-01** (active) Upload form accepts one file, with `accept="application/pdf,image/png,image/jpeg"`.
- **FE-UP-02** (active) Client-side check of size ≤ 5 MiB and type before sending. Server validation is authoritative.
- **FE-UP-03** (active) On `202`, the page shows the new document in the history list with status `PENDING` and offers a link to its detail page.
- **FE-UP-04** (active) Errors show the API `error.message` text. No stack traces, no raw JSON.

### 3.3 History
- **FE-HIST-01** (active) The history table shows: filename, uploaded time, status badge, total amount with currency (when `result` present). Newest first.
- **FE-HIST-02** (active) "Load more" uses `next_cursor`.
- **FE-HIST-03** (active) The list refreshes every 10 seconds while any visible item is `PENDING` or `RUNNING`, and stops when all are terminal.

### 3.4 Document detail
- **FE-DET-01** (active) Shows processing status, attempts, last error (if any), and the full extraction result: fields, line items, confidence, warnings.
- **FE-DET-02** (active) Polls `GET /api/v1/documents/{id}` every 5 seconds while `RUNNING` or `PENDING`, up to 5 minutes, then shows "Still processing. Refresh later."
- **FE-DET-03** (active) Null fields are displayed as "Not found" (not blank, not "0").
- **FE-DET-04** (active) Money is displayed with the currency code and the string value exactly as returned (no float conversion in JavaScript).

## 4. Accessibility and layout

- **FE-UX-01** (active) Responsive layout works at 360 px width without horizontal scrolling.
- **FE-UX-02** (active) Forms have associated `<label>` elements, visible focus styles, and error messages linked with `aria-describedby`.
- **FE-UX-03** (active) Status is never conveyed by color alone; badges include text.
- **FE-UX-04** (active) No external fonts, scripts, or trackers. Everything is served from the same CloudFront origin or inline.

## 5. Security

- **FE-SEC-01** (active) All dynamic text is inserted with `textContent`, never `innerHTML`, to prevent XSS from filenames or extracted values.
- **FE-SEC-02** (active) A Content Security Policy meta tag is set on every page: `default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'`.

## 6. Module layout

```
app/frontend/
  index.html
  dashboard.html
  document.html
  assets/
    app.css
    api.js          # fetch wrapper, token handling, error mapping
    auth.js         # login, register, logout, guard
    dashboard.js    # upload, history
    document.js     # detail, polling
    format.js       # date and money display helpers (no float math)
```

## 7. Acceptance

- **FE-ACC-01** (active) Manual checklist in `docs/` covers: register, login, upload each supported type, reject unsupported type, reject oversize file, history refresh, detail polling, logout, expired token redirect.
- **FE-ACC-02** (active) A static check (`scripts/check_frontend.sh`) fails if `innerHTML` appears in `app/frontend/assets/`, or if a `<script src>` points to an external host (`TST-LINT-02`).

CloudFront also sends frame-ancestors 'none' in the CSP response header (ADR-037). Browsers ignore that directive in meta tags.
