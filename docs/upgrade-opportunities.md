# Upgrade Opportunities

This document lists significant upgrades that would improve Home Cloud Drive without changing the current application behavior. Treat it as a planning reference for future work, not an implementation checklist that has already been executed.

## High-impact upgrades

### 1. Object storage backend

Add an S3-compatible storage abstraction for file contents, thumbnails, and version blobs.

Expected impact:

- Makes deployments easier to scale beyond a single host disk.
- Reduces risk when moving containers or rebuilding hosts.
- Opens the door to lifecycle policies, cheaper cold storage, and provider-level durability.

Implementation notes:

- Keep the current local filesystem backend as the default.
- Introduce a storage provider interface behind the existing storage service.
- Start with AWS S3, Cloudflare R2, or MinIO-compatible APIs.

### 2. Abandoned upload cleanup

Add scheduled cleanup for stale directories under `storage/tmp/<user_id>/<upload_id>`.

Expected impact:

- Prevents incomplete resumable uploads from consuming disk indefinitely.
- Reduces operator maintenance for long-running deployments.
- Makes quota behavior easier to reason about.

Implementation notes:

- Track upload session creation and last activity timestamps.
- Delete sessions older than a configurable threshold.
- Emit activity or maintenance logs for cleanup runs.

### 3. Background job queue

Move slow or retryable work into a durable background worker.

Expected impact:

- Keeps upload and auth requests responsive.
- Enables retry policies for email, thumbnail generation, search indexing, and maintenance jobs.
- Makes long-running tasks observable and easier to recover.

Implementation notes:

- Start with a lightweight queue such as Redis + RQ, Dramatiq, or Celery.
- Keep synchronous fallbacks for simple local deployments if practical.
- Add job status and failure counters before expanding worker responsibilities.

### 4. Richer search indexing

Expand content indexing beyond plain text and source-like files.

Expected impact:

- Makes PDFs, Office documents, and images discoverable by content.
- Improves usefulness for real personal document archives.
- Enables richer snippets and filtering.

Implementation notes:

- Add extractors for PDF and Office formats.
- Consider optional OCR for images and scanned PDFs.
- For larger deployments, evaluate Meilisearch, Typesense, or PostgreSQL full-text search instead of SQLite `LIKE` queries.

### 5. Database scalability option

Add first-class PostgreSQL support while keeping SQLite for simple deployments.

Expected impact:

- Improves concurrent write behavior for multi-user installs.
- Enables stronger migration tooling and operational visibility.
- Reduces risk as metadata volume grows.

Implementation notes:

- Audit SQLite-specific SQL and migrations.
- Add Alembic migrations for both fresh installs and upgrades.
- Run the test suite against SQLite and PostgreSQL in CI.

### 6. Automated backup and restore workflow

Document and automate backup for the SQLite database, uploaded files, versions, thumbnails, and configuration.

Expected impact:

- Gives operators a reliable recovery path.
- Reduces risk from disk corruption, accidental deletion, and failed upgrades.
- Makes production usage more trustworthy.

Implementation notes:

- Provide a backup script with quiesce or snapshot guidance.
- Include restore verification steps.
- Document which paths must be backed up together to avoid metadata/file drift.

## Operational upgrades

### 7. Observability dashboard

Add structured logs, metrics, and dashboard examples for common deployment health signals.

Useful signals:

- Request latency and status rates.
- Rate-limit hits.
- Upload completion and failure rates.
- Thumbnail and email failures.
- Search backfill duration.
- Storage and database volume utilization.

### 8. Admin audit trail

Expand activity logging into a dedicated audit log for sensitive actions.

Useful events:

- User role and quota changes.
- Password resets and forced password changes.
- Share link creation, access, revocation, and expiry.
- Shared-folder invites, role changes, removals, and writes by collaborators.
- Session revocation.
- Permanent delete operations.

### 9. Retention policies

Add configurable retention for old file versions and trash.

Expected impact:

- Gives users more control over storage growth.
- Supports "keep last N versions" or "delete versions older than N days" policies.
- Complements the existing startup trash cleanup.

### 10. End-to-end tests

Add browser-based tests for the most important workflows.

Suggested coverage:

- Login and 2FA challenge.
- Upload, preview, rename, move, and delete.
- Resumable upload resume and completion.
- Share-link creation and public download.
- Password reset route handling.

## User-experience upgrades

### 11. Bulk operations

Add multi-select actions for move, copy, trash, restore, download, and share management.

### 12. Offline-friendly upload queue

Persist selected upload state in the browser so interrupted uploads can resume more naturally after reloads or network loss.

### 13. Share analytics

Expose per-link access history, download counts, and last-access details in the share management UI.

### 14. Collaboration notifications

Add notifications for shared-folder invites, access changes, and important collaborator actions.

Expected impact:

- Makes collaboration visible without requiring users to poll the shared-folder list.
- Helps owners notice role changes and unexpected shared-folder activity.
- Complements the existing login alert email path with collaboration-focused account email.

### 15. Mobile file actions polish

Review touch-first interactions for context menus, drag-and-drop, preview controls, and upload progress.
