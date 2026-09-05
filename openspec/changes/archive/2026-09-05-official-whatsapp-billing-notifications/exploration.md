## Exploration: Official WhatsApp Billing Notifications

### Current State

The application already has a deliberately sandbox-only WhatsApp seam. `BillingNotificationService` is invoked after regular and practice billing publication commits and by admin-selected resend endpoints. When WhatsApp is enabled it sends only the first representative recipient to the fixed Twilio Sandbox destination; otherwise it sends one Resend email per eligible teacher. `OutboundNotificationAttempt` provides a PII-free idempotency claim, but outbound work still executes synchronously in the API process, pending/ambiguous claims are never reconciled, and Twilio acceptance is treated as `sent` without delivery callbacks.

Billing data is suitable for immutable notification content: `BillingPublication.billing_snapshot` and its version identify the exact per-teacher financial snapshot, and portal billing reads the same snapshot rather than mutable live data. The existing email renderer already consumes these snapshot rows. There is no billing PDF service or secure media-link endpoint; current ReportLab PDFs are generated for other domains and returned through authenticated API routes or local files.

Teacher contact data is not production-ready for WhatsApp. `Teacher.phone` is optional, editable/importable, and only loosely validated; there is no canonical E.164 field, verification evidence, consent timestamp/source/version, or opt-out history. The current sandbox ignores it and uses one environment-configured test recipient.

The admin UI in `PlanillaPage.tsx` and `PracticaPlanillaContent.tsx` can select published-snapshot teachers and invoke direct `send-emails` mutations, but it has no recipient/channel preview, digest-bound confirmation, readiness view, or durable progress display. Publication itself also triggers outbound delivery automatically after commit. Existing teacher/designation imports demonstrate the safer preview plus digest-bound confirmation pattern.

Production deploys multiple Uvicorn workers but has no queue/worker dependency. The PostgreSQL database is therefore the only existing durable coordination boundary. There are no Twilio status/inbound webhooks, signature verifier, provider-readiness state, approved Content SID configuration, or public canonical-base-URL contract. Nginx forwards host/protocol headers to `/api/`, which matters because Twilio request signatures depend on the externally visible callback URL.

### Affected Areas

- `backend/app/services/billing_notification_service.py` — replace sandbox representative branching with consent-aware per-recipient orchestration and preserve safe fallback rules.
- `backend/app/services/whatsapp_service.py` — add official sender mode, approved Utility Content SID messages, canonical verified recipients, and strict readiness gates.
- `backend/app/services/twilio_whatsapp_transport.py` — support Content API parameters, status callback URLs, structured terminal/ambiguous outcomes, and provider lookup/reconciliation.
- `backend/app/models/outbound_notification_attempt.py` and `backend/alembic/versions/` — evolve the audit record and add durable batch/outbox, consent/preference, webhook-event, and expiring-media-token persistence.
- `backend/app/models/teacher.py`, `backend/app/schemas/teacher.py`, and `backend/app/routers/docente_portal.py` — expose explicit consent/opt-out state separately from the legacy editable `phone` field; never infer consent from a populated number.
- `backend/app/routers/billing_publication.py` — stop synchronous implicit production sends; add admin preview, digest-bound confirmation, batch status, and snapshot-scoped recipient selection for regular and practice billing.
- `backend/app/routers/` and `backend/app/main.py` — add public signed Twilio status/inbound webhook routes and the tokenized PDF media route.
- `backend/app/services/billing_email_template.py` and a new billing PDF service — reuse immutable publication rows for the email alternative and PDF without recalculating billing.
- `frontend/src/api/hooks/useBillingPublication.ts`, `frontend/src/pages/PlanillaPage.tsx`, and `frontend/src/pages/PracticaPlanillaContent.tsx` — replace direct “send email” actions with preview, explicit confirmation, readiness/fallback reasons, and durable delivery status.
- `backend/app/config.py`, `deploy/compose.production.yml`, `deploy/.env.production.example`, `deploy/nginx/app-nginx.conf`, and deployment documentation — add official sender, Content SIDs, public callback base URL, signature secret/Auth Token, private media storage, and a dedicated worker process.
- `backend/tests/services/test_billing_notification_service.py`, `backend/tests/services/test_whatsapp_service.py`, `backend/tests/services/test_twilio_whatsapp_transport.py`, router tests, migration tests, and frontend contract checks — extend coverage from sandbox acceptance to consent, preview/confirm, worker leases, callbacks, opt-out, media expiry, and fail-closed production readiness.
- `openspec/specs/email-notifications/spec.md` — later delta specs must preserve the existing best-effort email contract while narrowing fallback to no consent or definite terminal WhatsApp failure.

### Approaches

1. **Extend the current synchronous attempt service** — add production mode and loop through all recipients inside the API request.
   - Pros: Smallest initial diff; reuses the existing attempt table and service directly.
   - Cons: Request timeouts, multi-worker races, no durable retry/reconciliation, weak admin observability, and unsafe coupling between provider latency and API availability. It cannot satisfy the durable worker requirement cleanly.
   - Effort: Medium

2. **Billing-scoped transactional outbox with a database worker** — persist a notification batch plus one immutable recipient job per publication version, then let a dedicated process claim jobs with leases and deliver through channel adapters.
   - Pros: Fits the existing PostgreSQL deployment without introducing Redis; supports per-recipient consent snapshots, digest-bound admin confirmation, retry/backoff, webhook reconciliation, cancellation on opt-out, and auditable fallback. It keeps billing scope explicit.
   - Cons: Requires migrations, a new worker service, operational monitoring, lease recovery, and careful PostgreSQL/SQLite test behavior.
   - Effort: High

3. **Build a generic multi-domain notification platform now** — general campaigns, arbitrary templates, and multiple event types/channels.
   - Pros: Maximum future reuse for general notices and Marketing messages.
   - Cons: Violates the confirmed billing-only scope, mixes Utility and Marketing policy, increases consent complexity, and delays the safe production path.
   - Effort: Very High

### Recommendation

Use approach 2 and keep it explicitly billing-scoped. Preserve `BillingPublication` plus version as the immutable content source, and introduce a preview digest over the publication identity, selected teacher IDs, consent/preference revisions, resolved channels, approved Content SID, and PDF artifact identity. Confirmation MUST re-evaluate readiness and reject a stale digest rather than silently changing recipients or channels.

Store WhatsApp preference separately from `Teacher.phone`: canonical E.164, verification evidence/time/source, explicit consent state/time/source/policy version, and opt-out time/source. Preview should mask phone numbers and classify every selected teacher as WhatsApp eligible, email alternative, blocked, or skipped. No phone value alone may imply consent.

Persist a batch and one outbox row per recipient. A dedicated container using the existing backend image should poll PostgreSQL and atomically lease work (PostgreSQL `FOR UPDATE SKIP LOCKED`; a deterministic test-safe path for SQLite). Keep provider dispatch separate from database transactions. A timeout or unknown post-dispatch outcome remains ambiguous and MUST NOT trigger email; reconcile by provider SID/status webhook or bounded lookup. Email is allowed only when WhatsApp consent is absent or when a classified, definite terminal WhatsApp failure is recorded. Opt-out cancels unsent WhatsApp jobs and blocks future ones.

Official sending must be fail-closed: production WhatsApp is unavailable unless the configured sender is explicitly `ONLINE`, each billing variant resolves to an approved Utility Content SID, credentials and canonical public URLs are present, and webhook signature verification is enabled. A readiness failure blocks WhatsApp confirmation rather than falling back silently. Sandbox and production configuration should remain distinct so an environment variable change cannot promote the representative sandbox behavior.

Status and inbound webhooks must validate Twilio signatures against the exact externally visible URL and raw form parameters before any mutation, be idempotent by provider event/message identity, and never log message bodies or phone numbers. Inbound STOP-like events should resolve the verified sender E.164, record opt-out history, and cancel pending WhatsApp jobs. Unknown senders receive no account linkage.

Generate each billing PDF from the immutable per-teacher publication snapshot before dispatch, store it privately, and expose only an opaque high-entropy token whose hash is stored with recipient/publication binding and expiry. The media endpoint should return `Cache-Control: no-store`, avoid PII in paths, tolerate the bounded repeat fetches Twilio may perform, and reject expired/revoked tokens. This needs a shared private billing-media volume for the API and worker, or database/object storage if operational research selects it.

Before proposal, run focused provider research against official Twilio documentation for Content template/media parameter contracts, sender `ONLINE` observability, signature validation behind proxies, callback retry semantics, inbound opt-out behavior, and message-status definitions. Those facts are externally controlled and should not be inferred from the sandbox implementation.

### Risks

- Twilio acceptance is not delivery; premature email fallback can duplicate a billing notice.
- Callback signature validation will fail or become bypassable if canonical public URL/proxy handling is inconsistent.
- Utility template category, variable layout, PDF media support, or approved Content SID lifecycle may differ by sender/account and requires official evidence.
- A verified number and explicit consent are distinct facts; conflating them creates compliance and trust risk.
- Expiring media that is too short-lived or single-use can fail when Twilio fetches more than once; overly long-lived links expose sensitive billing data.
- PostgreSQL leasing semantics differ from SQLite tests, so concurrency behavior needs PostgreSQL integration coverage in addition to unit tests.
- Publication unpublish/revision behavior must cancel or obsolete queued work without mutating already-delivered historical evidence.
- Existing automatic post-publication outbound sends must be removed or sandbox-isolated before official mode, otherwise admin confirmation can be bypassed.
- The change will likely exceed the 400-line review budget and should be planned as reviewable work units, potentially chained PR slices.

### Ready for Proposal

Yes, the repository architecture and recommended boundary are clear. The orchestrator should offer the focused Twilio research lane immediately; if selected, that research must complete before proposal. General notices and Marketing messages remain explicitly deferred.
