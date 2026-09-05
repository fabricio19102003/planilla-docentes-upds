# Apply Progress: Official WhatsApp Billing Notifications

## Status
All slices **A–H** are complete: **16/16** tasks. Final independent `sdd-verify` is ready; no apply/deploy work remains.

## Completed Tasks
- [x] A.1 RED tests: verified E.164, evidenced consent, and revision/opt-out evidence.
- [x] A.2 Added `WhatsAppPreference`, model/schema exports, and additive Alembic migration.
- [x] B.1 RED tests: durable batch/job/event/media persistence contracts and `SM|MM` provider SID shapes.
- [x] B.2 Added official billing outbox models, schemas/exports, indexes/constraints, and additive Alembic migration.
- [x] C.1 RED tests: canonical SHA-256 plan binding, consent snapshots, and fail-closed channel policy.
- [x] C.2 Added digest/policy primitives and default-off official WhatsApp flags.
- [x] D.1 RED router tests: masked preview, digest, stale rejection/no jobs, and capacity forecast behavior.
- [x] D.2 Added preview/replan/confirm routes and durable intent creation behind fail-closed readiness/capacity checks.

## Completed Slice A — Consent/E.164 preference

### Preserved environment history
- Initial focused runner: `cd backend && pytest tests/services/test_billing_notification_service.py` exited 127 because `pytest` was unavailable.
- Retry virtual environment used Python 3.14 and could not install repository-pinned dependencies within the runner limit; `.venv-whatsapp-pr1/bin/python -m pytest backend/tests/services/test_billing_notification_service.py` reported `No module named pytest`.
- Supported-image RED evidence (Python 3.12.8 / pytest 8.3.3): 9 tests collected; exactly 2 expected import failures for the not-yet-created `app.models.whatsapp_preference` module.
- GREEN was captured twice after implementation: 9 passed. Latest focused proof below is authoritative.

### Migration correction
The initial migration parent was `d9e4a1b6c2f0`, which created a second Alembic head beside `a1b2c3d4e5f6`. It was corrected to `a1b2c3d4e5f6`; `alembic heads` is now singular and the isolated migration can reach `head`.

## Work Unit Evidence
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_billing_notification_service.py` → Python 3.12.8, pytest 8.3.3, 9 collected, **9 passed**, 5 warnings, 0.19s. |
| Runtime harness | Disposable SQLite migration smoke in `whatsapp-pr1-test:latest` (image `sha256:28cf42111921c81f1bd01012bbaa3d2526328414dd7923a15369810c7843dbf7`): seed prior `teachers(ci VARCHAR(20) PRIMARY KEY)`, `alembic stamp a1b2c3d4e5f6`, `alembic upgrade head`; asserted `aa1b2c3d4e5f` at head; table, exact columns/types/nullability, PK, teacher FK `ON DELETE CASCADE`, and unchanged pre-existing table. Passed. |
| Rollback boundary | Revert only A.1/A.2 files: `backend/tests/services/test_billing_notification_service.py`, `backend/app/models/whatsapp_preference.py`, `backend/app/models/__init__.py`, `backend/app/schemas/billing_notification.py`, `backend/app/schemas/__init__.py`, and `backend/alembic/versions/aa1b2c3d4e5f_add_whatsapp_preferences.py`; downgrade drops only `whatsapp_preferences`. |

## Exact Latest Proof
```text
alembic_revision=head: aa1b2c3d4e5f
table_exists: whatsapp_preferences
columns: [('teacher_ci', 'VARCHAR(20)', True, True), ('phone_e164', 'VARCHAR(16)', True, False), ('is_verified', 'BOOLEAN', True, False), ('consent_evidence', 'TEXT', False, False), ('consent_revision', 'INTEGER', True, False), ('opt_out_evidence', 'TEXT', False, False), ('opted_out_at', 'DATETIME', False, False)]
primary_key: teacher_ci
teacher_fk: teachers.ci ON DELETE CASCADE
destructive_changes: none; pre-existing teachers table unchanged

9 passed, 5 warnings in 0.19s
```

## Slice B — Batch/job/event/media persistence

### Exact Slice B Source Delta
- **288 changed lines**: 100 tracked additions/deletions + 101-line new model + 87-line new migration.

### RED and GREEN evidence
- Supported-image RED: Python 3.12.8 / pytest 8.3.3 collected 11 tests; the 9 existing tests passed and exactly the two B tests failed with `ModuleNotFoundError: No module named 'app.models.billing_notification'`.
- GREEN: `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_billing_notification_service.py` → **11 passed**, 5 warnings, 0.22s.

### PostgreSQL runtime smoke
A disposable `postgres:16-alpine` database received a full `alembic upgrade head` through `bb2c3d4e5f6a`. The smoke asserted all B tables plus `whatsapp_preferences`, unique batch digest/job intent/event dedupe/media token constraints, claim and provider-SID indexes, batch/teacher cascade foreign keys, inserted a persisted `SM` SID, and proved duplicate durable intent rejection. The container was stopped and removed afterwards. A second disposable PostgreSQL run upgraded to B then downgraded to `aa1b2c3d4e5f`, proving only the four B tables were removed while `teachers`, `billing_publications`, and `whatsapp_preferences` remained.

## Work Unit Evidence — B
| Evidence | Result |
|---|---|
| Focused test command | Supported Docker image command above → Python 3.12.8 / pytest 8.3.3; **11 passed**, 5 warnings, 0.22s. |
| Runtime harness | Disposable PostgreSQL 16 full migration + schema/constraint/runtime insertion smoke → passed at head `bb2c3d4e5f6a`; no SIPAD database was accessed. |
| Rollback boundary | Revert B files: `backend/app/models/billing_notification.py`, B additions to model/schema exports and `billing_notification.py`, B tests, and `backend/alembic/versions/bb2c3d4e5f6a_add_billing_notification_persistence.py`; Alembic downgrade drops only the four B tables and their indexes. |

## Exact B Runtime Proof
```text
alembic_revision=head: bb2c3d4e5f6a
tables: billing_media_tokens,billing_notification_batches,billing_notification_jobs,whatsapp_events
unique_constraints: batch_digest, job_intent, event_dedupe, media_token
job_indexes: claim(status, lease_expires_at), provider_sid
job_fks: batch CASCADE, teacher CASCADE
sid_shapes: SM/MM accepted by model RED/GREEN contract; persisted SM value inserted
safe_downgrade_boundary: only B tables are created by bb2c3d4e5f6a
downgrade_revision: aa1b2c3d4e5f
removed_only: billing_notification_batches,billing_notification_jobs,whatsapp_events,billing_media_tokens
preserved: teachers,billing_publications,whatsapp_preferences

11 passed, 5 warnings in 0.22s
```

## Gate Correction Evidence
| Runtime harness | N/A — metadata-only routing correction; no source or runtime behavior changed. |

## Slice C — Digest, policy, and flags

### RED and GREEN evidence
- RED: supported Python 3.12.8 image collected 13 tests; 11 existing tests passed and exactly 2 new C tests failed with `ModuleNotFoundError: app.services.billing_notification_policy`.
- GREEN: supported image collected **14 tests; 14 passed**, 5 warnings, 0.30s. The added flag-default test confirms both official dispatch gates are false.

### Work Unit Evidence — C
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_billing_notification_service.py` → Python 3.12.8 / pytest 8.3.3; **14 passed**, 5 warnings, 0.30s. |
| Runtime harness | Disposable supported-image SQLite fixture (`DATABASE_URL=sqlite:////tmp/policy-fixture.db`) created metadata and evaluated consented/no-consent/ambiguous/verified-terminal decisions plus a 64-character digest: passed; no provider I/O or production database access. |
| Rollback boundary | Revert C additions only: `backend/app/services/billing_notification_policy.py`, C flag additions in `backend/app/config.py`, and C tests in `backend/tests/services/test_billing_notification_service.py`; no migrations, persisted data, routes, worker, or legacy Sandbox behavior changed. |

## Completed Slice C — Digest and policy
- [x] C.1 RED tests: canonical SHA-256 plan binding, consent snapshot, and fail-closed email policy.
- [x] C.2 Added pure digest/policy planner and separate default-off official WhatsApp/dispatch flags.

## Historical routing note
This C-era route is superseded by the current Status and the Slice D correction record below; no pending D route remains.



## Slice D — Preview and confirmation

### RED and GREEN evidence
- RED: supported Python 3.12.8 image collected 14 tests; 12 existing tests passed and the two new D router tests failed with HTTP 404 because the preview and confirm endpoints did not exist.
- GREEN: supported image collected **15 tests; 15 passed**, 34 warnings, 11.37s. The additional D.2 proof creates one durable queued intent only from a readiness-injected local plan.

### Work Unit Evidence — D
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/routers/test_billing_publication_email.py -q` → Python 3.12.8; **15 passed**, 34 warnings, 11.37s. |
| Runtime harness | The focused TestClient + disposable SQLite fixture exercised `/api/billing/notifications/preview` and `/confirm` with zero provider, Twilio, Resend, or production I/O. It verified a masked E.164 preview, SHA-256 digest, fail-closed unavailable readiness, stale-confirmation 409, and zero persisted batch/job rows. A local readiness-injected service fixture created exactly one queued durable intent. Passed. |
| Rollback boundary | Revert D additions only: `backend/app/services/billing_notification_preview.py`, D route/schema additions in `backend/app/routers/billing_publication.py`, and D tests in `backend/tests/routers/test_billing_publication_email.py`. This removes preview/confirmation APIs while preserving A-C models, migrations, digest/policy primitives, and all persisted data. |

## Completed Slice D — Preview and confirmation
- [x] D.1 RED router tests for masked preview, capacity forecast, digest, and stale rejection/no jobs.
- [x] D.2 Added deterministic preview/replan/confirm service and admin endpoints. The router is deliberately fail-closed until E supplies live readiness; no external provider call is possible here.

## Historical routing note
Superseded routing notes are retained as historical context; the canonical next step appears below.


## Slice D Correction — Capacity forecast and routing (`slice-d-capacity-forecast-and-routing-correction`)

### Correction scope
- Added an explicit cohort-versus-capacity forecast: `available`, `requested`, `remaining`, and `exceeded`. Unavailable capacity remains fail-closed; confirmation rejects unavailable or exceeded forecasts before creating jobs.
- Corrected this artifact's status and routing to show A-D complete with the remaining apply work pending.
- The original completed native objective retains its historical ledger label; this correction is separately bound to `slice-d-capacity-forecast-and-routing-correction` and does not rewrite that history.

### RED and GREEN evidence
- RED: supported Python 3.12.8 image collected 18 tests; the 15 prior tests passed and the three new capacity forecast cases failed because `requested`/`exceeded` were absent and unavailable capacity had no explicit representation.
- GREEN: supported image collected **18 tests; 18 passed**, 34 warnings, 13.29s.

### Work Unit Evidence — D correction
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/routers/test_billing_publication_email.py -q` → Python 3.12.8; **18 passed**, 34 warnings, 13.29s. |
| Runtime harness | Disposable TestClient/SQLite fixture: no provider/network/production I/O; proved masked preview, stale no-job confirmation, and deterministic capacity available/exceeded/unavailable forecasts. Passed. |
| Rollback boundary | Revert the D service, D router additions, and D tests; this removes preview/confirmation and capacity forecasting without changing A-C persistence/policy artifacts. |

## Historical routing note
The final canonical route is recorded after the E-a settlement evidence.


## Slice E-a — Readiness and Content transport
- RED: 6 focused tests collected; 4 legacy tests passed and 2 new imports failed before implementation.
- GREEN: Python 3.12.8 offline MockTransport suite: 6 passed, 4 warnings, 0.06s.
| Runtime harness | Offline httpx MockTransport and pure readiness facts: exact ContentSid/ContentVariables/StatusCallback payload; no Body/MediaUrl and unavailable capacity fails closed; no network/provider I/O. |
| Rollback boundary | Revert E-a config fields, `twilio_content_transport.py`, `twilio_readiness_adapter.py`, and focused tests. |

### Native settlement metadata
- Work-unit: `slice-ea-readiness-content-transport`
- Native state: `complete`
- Evidence revision: `sha256:4c3183b7f05cbe27216786b89bfbec71d9253df99066ed5d447a052177627d84`
- Local commit: `bd6329a feat(whatsapp): add official content transport`

## Historical routing note
E-b completion is recorded below.


## Slice E-b — Worker leasing, retries, and persistent capacity (corrected)
- [x] E.1 RED coverage now proves due-time eligibility, committed-lease observation, crash-lease reclamation, readiness drift/no transport, ambiguity terminality, deterministic retry backoff, and persistent capacity exhaustion.
- [x] E.2 Rebuilt the worker around three committed boundaries: transactional PostgreSQL `FOR UPDATE SKIP LOCKED` / SQLite CAS claim, readiness/capacity reservation outside that claim transaction, and an atomic `sending` finalization. A job becomes `sending` immediately before create so a process crash at the provider boundary is ambiguous, never retryable.

### Work Unit Evidence — E-b corrected rewrite
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_billing_notification_worker.py tests/services/test_twilio_whatsapp_transport.py -q` → Python 3.12.8 / pytest 8.3.3; **13 passed**, 4 warnings, 1.24s. |
| Runtime harness | Disposable PostgreSQL 16 two-worker end-to-end harness: first worker committed a `leased` row before its blocked readiness callback; a concurrent worker used `FOR UPDATE SKIP LOCKED` and returned no job; release permitted exactly one fake transport call and one durable capacity reservation. **Passed**. Container and Docker network were removed in `trap` cleanup. |
| Rollback boundary | Revert only E-b worker/model export/model retry-capacity fields/migration/test changes: `backend/app/workers/billing_notification_worker.py`, `backend/app/models/{billing_notification.py,__init__.py}`, `backend/alembic/versions/cc3d4e5f6a7b_add_worker_retry_capacity.py`, and `backend/tests/services/test_billing_notification_worker.py`. Downgrade removes retry/capacity schema only; A–E-a persistence and transport remain. |

### Corrected contract details
- Claim predicates require `queued` jobs to have `next_attempt_at IS NULL OR <= worker clock`; future retries cannot be sent early. Expired `leased` pre-create jobs remain reclaimable.
- PostgreSQL locks only the claim/reservation transaction and commits it before readiness and transport. SQLite uses conditional CAS update for the same eligibility predicate.
- Readiness drift and exhausted/malformed capacity fail closed into the deterministic 30-second retry backoff, with no email path in the worker.
- Capacity uses a locked singleton window plus a durable unique-per-job reservation; concurrent workers cannot pass a moving-recipient limit independently.
- `sending` is committed immediately before provider invocation; ambiguous provider results are terminal and later claims exclude them, preventing duplicate create attempts.

### Native settlement metadata
- Work-unit: `slice-eb-worker-transaction-capacity-rewrite`
- Native token: `sha256:d4a4b7d3b47dabd0787e874a2c956550b654f840a075b00a927d2eb8159e52d3`
- Evidence revision: `sha256:7778b0fb27b9c0a8fe4d0055b34c83d7bfa57bdc856ba8e9a1c4be1044a711ef`
- Delivery: `exception-ok`; explicit maintainer `size:exception` accepted.
- Authored implementation lines: 457 (229 worker + 155 focused tests + 42 migration + 31 model/export), within the authorized 650-line cohesive rewrite boundary.
- Correction routing is recorded only in the canonical Next Step below.

## Slice E-b Gate Correction — Capacity and throttle
- Added deterministic 10%-margin media-MPS scheduling through an injected sleeper; dispatch timestamps are persisted in the singleton capacity window.
- Capacity now counts `DISTINCT recipient_key` within the moving window, so separate jobs for the same recipient consume one recipient slot.
- The E-b migration seeds singleton window `id=1` before workers run, making PostgreSQL `FOR UPDATE` serialization race-free; downgrade removes only E-b retry/capacity objects.

### Work Unit Evidence — E-b gate correction
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_billing_notification_worker.py tests/services/test_twilio_whatsapp_transport.py -q` → Python 3.12.8 / pytest 8.3.3; **15 passed**, 4 warnings, 1.40s. |
| Runtime harness | Disposable PostgreSQL 16 harness passed: one locked queued row proved `SKIP LOCKED` and committed lease visibility before readiness/provider I/O; two independently leased recipients concurrently contended on the pre-seeded capacity row with cap 1, yielding exactly one `accepted`, one `backoff`, one reservation, and one fake create. Container/network cleaned by trap. |
| Rollback boundary | Revert E-b worker, worker tests, capacity-window model field, and `cc3d4e5f6a7b` migration. This removes MPS/capacity scheduling while preserving A–E-a and leaves F/G/H untouched. |

### Native settlement metadata
- Work-unit: `slice-eb-capacity-throttle-gate-correction`
- Native token: `sha256:ae6ccad9034f71aed1503dea9438bc8e16683705047b4db7472fd12824179067`
- Evidence revision: `sha256:156306b339b11570f2b028c848dbaf7c27d99e53c32b5635c1a0ad795a546b34`
- Delivery: `exception-ok`; maintainer size exception remains authorized.
- Authored E-b implementation/test/migration/model lines: 523, within the 650-line exception.

## Historical routing note
The former F.1/F.2 route is completed; the canonical current route is recorded below.

## Slice F — Status webhooks, reconciliation, and inbound STOP
- [x] F.1 RED tests: canonical configured HTTPS callback URL plus raw form fields, invalid signatures, duplicate/out-of-order delivery, unknown sender/SID, signed STOP cancellation, and bounded known-SID reconciliation.
- [x] F.2 Added public Twilio status/inbound routes and a durable webhook projection service. Signature verification is HMAC-SHA1 with constant-time comparison over the configured canonical HTTPS URL, actual query, and sorted raw form pairs; Host/forwarded headers are never trusted. Events deduplicate before mutation; terminal/out-of-order states do not regress; `SM`/`MM` SIDs are preserved; STOP records opt-out and cancels queued, leased, or sending WhatsApp jobs before the final provider boundary. No email service is called by callbacks, reconciliation, or STOP handling.

### RED and GREEN evidence
- RED: supported Docker Python 3.12.8 / pytest 8.3.3 collected 3 tests; all 3 failed with `ModuleNotFoundError: app.services.whatsapp_webhook_service` before the implementation existed.
- GREEN: `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_whatsapp_webhook_service.py tests/services/test_billing_notification_worker.py tests/services/test_twilio_whatsapp_transport.py -q` → **19 passed**, 10 warnings, 1.81s.

### Work Unit Evidence — F
| Evidence | Result |
|---|---|
| Focused test command | Command above → Python 3.12.8 / pytest 8.3.3; **19 passed**, 10 warnings, 1.81s. |
| Runtime harness | Disposable SQLite/TestClient harness in Docker used local fake signatures and form bytes only: valid status callback 204, replay 204, invalid signature 403; one durable event and `accepted → delivered` projection. No Twilio, network, VPS, or production database I/O. |
| Rollback boundary | Revert F-only webhook/service/router/config/test changes plus `backend/app/workers/billing_notification_worker.py` and `backend/tests/services/test_billing_notification_worker.py` only where F adds fresh STOP state at the provider boundary. This removes F callback/STOP behavior without reverting E leasing, capacity, retry, or ambiguous post-create semantics, and leaves legacy Sandbox/Resend isolated. |

### Native settlement metadata
- Work-unit: `slice-f-status-webhook-and-inbound-stop`
- Native token: `sha256:b4cfa1f2c35e467370d06abc913414da2b9257074a2045b86260d10b14d98da4`
- Historical measurement (superseded): 334 authored lines was an earlier partial F measurement; it is not the final cumulative total.

## Historical Next Step
G.1/G.2 is complete; this historical route is superseded.


## Slice F Gate Correction
- Router TestClient proof uses non-empty `trace=abc` query, hostile Host/forwarded headers, configured HTTPS canonical URL, raw form fields, replay/invalid/malformed rejection before mutation.
- STOP final-boundary test proves a signed durable opt-out cancels `sending` before transport and prevents retry; terminal transition table permits accepted/sent to failed/undelivered without regressions.
- Focused Docker Python 3.12.8 suite: 16 passed, 13 warnings, 3.26s.
- F cumulative accounting: **471 changed lines (465 additions + 6 deletions)**. The user explicitly authorized a `size:exception` at this exact 471-line ceiling because authenticated canonical-query validation, durable monotonic event projection, bounded reconciliation, and cross-session STOP/provider-boundary suppression form one inseparable security behavior.

### Slice F separate-session race correction
- Worker expires identity-map state at the final provider boundary; a signed STOP committed from a distinct webhook session is freshly observed before transport.
- Distinct-session SQLite harness passed with no provider I/O; transport was never called and cancelled jobs cannot retry.

## Slice G — Secure billing PDF media
- [x] G.1 RED coverage proves token binding, deterministic artifact identity, expiry, revocation, 15,000,000-byte cap, safe inline filename/MIME, `Cache-Control: no-store`, and repeated `HEAD`/`GET` behavior.
- [x] G.2 Added deterministic snapshot-derived PDF storage, SHA-256 artifact and opaque token binding, and a fail-closed public media route. The route discloses no distinction among missing, expired, revoked, unbound, tampered, or oversized artifacts; it has no email, Resend, Sandbox, provider, or network path.

### Work Unit Evidence — G
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/routers/test_billing_media.py tests/services/test_billing_notification_worker.py tests/services/test_twilio_whatsapp_transport.py -q` → Python 3.12.8 / pytest 8.3.3; **18 passed**, 5 warnings, 3.78s. |
| Runtime harness | Disposable FastAPI TestClient + SQLite scenario in `whatsapp-pr1-test:latest`: one durable token received repeated `HEAD`/`GET` responses with `application/pdf`, exact length, `no-store`, inline safe filename, and identical bytes; expired, revoked, unknown, and oversized/tampered artifacts returned only 404. No provider, network, VPS, or production I/O. Passed. |
| Rollback boundary | Revert G-only files `backend/app/services/billing_pdf_service.py`, `backend/app/routers/billing_media.py`, `backend/tests/routers/test_billing_media.py`, plus the billing-media config/router registration lines in `backend/app/config.py`, `backend/app/routers/__init__.py`, and `backend/app/main.py`. This removes public PDF token delivery without changing A–F outbox, worker, webhook, Sandbox, or email behavior. |

### Native settlement metadata
- Work-unit: `slice-g-secure-pdf-media`
- Native token: `sha256:838c01875b228168adfa298288e965dc5a64b6951849b4ec3eabd0ba7d38fafc`
- Evidence revision: `sha256:5c4cd56c72dbee0e8da11ffc0fe82ea3e30a981cc0f6247bec4d449c221600b3`.
- Native settlement state: `complete` (request `slice-g-settle-20260902-04`; selected the complete existing untracked inventory required by the ledger, including predecessor F/OpenSpec files, with inventory `sha256:d5c2b76b641e6a9db8122caa50d2a8abaed86eb9337e6331a5f07f0067ffa329`).
- Authored implementation/test lines: **257** (135 service + 28 router + 89 focused tests + 5 integration/config lines), within Slice G's 400-line native budget.
- Delivery: `exception-ok` applies only to previously authorized cohesive units; G authored changes are within its native 400-line budget.

## Slice G Gate Correction — Production job binding
- Confirmation now derives each WhatsApp PDF solely from the confirmed publication's immutable teacher snapshot, creates the exact job first, and records the token/artifact identity on that job.
- `BillingMediaToken.job_id` is a durable foreign-key binding. Resolution requires the token, job, batch, teacher, token id, artifact SHA-256, and byte size to agree; any mismatch returns generic 404.

### Correction Evidence
| Evidence | Result |
|---|---|
| Focused test command | `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/routers/test_billing_media.py tests/routers/test_billing_publication_email.py -q` → Python 3.12.8 / pytest 8.3.3; **22 passed**, 37 warnings, 13.06s. |
| Runtime harness | Disposable FastAPI TestClient + SQLite confirmation created the token from the immutable teacher snapshot; repeated public fetches and a durable valid token with mismatched job artifact identity were exercised locally. No provider, network, VPS, or production I/O. Passed. |
| Rollback boundary | Revert the G correction changes in `backend/app/services/billing_pdf_service.py`, `backend/app/services/billing_notification_preview.py`, `backend/app/models/billing_notification.py`, `backend/alembic/versions/dd4e5f6a7b8c_bind_billing_media_tokens_to_jobs.py`, and `backend/tests/routers/test_billing_media.py`. |

### Native correction settlement
- Work-unit: `slice-g-production-binding-correction`
- Native token: `sha256:30c6c80155a9ee08173aa9af6730ab03b135f4cac8c9a819da3907bb34ca1cd3`
- Maintainer reset authorization: exact 149-line correction boundary approved; preserved correction bytes unchanged.
- Evidence revision: `sha256:1c457d7c98e6fb99fe16f40c94a5d5f55f9c31a3fd0d90f7feb22e8acf7cca16`.
- Proof work-unit: `slice-g-production-binding-proof`; token `sha256:d1e38f757b35a3b17d09646cf0c287d8fb059a96ad96e1a5addf85fea6a37f62`; settlement state: `complete`.
- Proof result: Docker Python 3.12.8 focused pytest 22 passed; disposable SQLite Alembic upgrade to `dd4e5f6a7b8c` and downgrade to `cc3d4e5f6a7b` passed.
- Correction accounting: **149/149** native changed lines; retained evidence revision was settled without modifying production behavior.

### Historical Next Step (superseded)
Apply H.1/H.2 through the native SDD dispatcher.

## Slice H.1 — Admin WhatsApp readiness, preview, confirmation, and durable status
- [x] H.1 Added admin-facing readiness, masked preview, digest-bound explicit confirmation, and polling durable-batch status hooks/UI for regular billing publications.
- The UI never renders full E.164 numbers, provider credentials, provider SIDs, or raw provider payloads; it uses the masked number contract and channel/status summaries only.
- Readiness, capacity, and stale-digest failures fail closed in the UI. The read route intentionally reports unavailable until H.2 wires live production configuration, with no provider/network call.

### RED and GREEN evidence
- RED: `node frontend/scripts/check-whatsapp-billing-notifications-ui.mjs` failed before H.1 hooks/UI existed because the readiness endpoint contract was absent.
- GREEN: `node frontend/scripts/check-whatsapp-billing-notifications-ui.mjs` passed after H.1 implementation.

### Work Unit Evidence — H.1
| Evidence | Result |
|---|---|
| Focused test command | `cd frontend && node scripts/check-whatsapp-billing-notifications-ui.mjs` → passed. Existing closest regression `npm run test:planilla-detail` → passed. |
| Lint | `cd frontend && npm run lint` → passed after `npm ci` restored only lockfile-declared local dependencies; no manifest or lockfile change. |
| TypeScript/production build | `cd frontend && npm run build` → passed (`tsc -b` and Vite production bundle). Vite emitted only native-config and chunk-size warnings. |
| Runtime/UI harness | N/A — no isolated browser fixture or live provider boundary exists. Structural UI proof, lint, and production build completed without provider, VPS, production, Resend, Sandbox, or network API interaction. |
| Rollback boundary | Revert H.1 only: `frontend/src/api/hooks/useBillingPublication.ts`, `frontend/src/pages/PlanillaPage.tsx`, `frontend/scripts/check-whatsapp-billing-notifications-ui.mjs`, and H.1 read-route additions in `backend/app/routers/billing_publication.py`. This preserves A–G records and dispatch behavior. |

### Native settlement metadata
- Work-unit: `slice-h1-dependency-verification`
- Native token: `sha256:2ea1eb9249fe77938952c9a5baf1882ddbc745417a53b183266dd7c490d29d3f`
- Remediates evidence revision: `sha256:9c23709b51d0918b6c12c23c58f20c8b08bd58a17d25310d64343a914b22ec0f`
- Authored H.1 changes: 225 lines (223 additions + 2 deletions), including the 21-line structural test; within the 400-line budget.
- Dependency recovery: `npm ci` installed declared local dependencies only. It made no tracked source, manifest, or lockfile changes and left no retained process.

### Historical Next Step (superseded)
Only H.2 remains: worker/secrets/Nginx URL/rollback runbook and its scoped backend/frontend proof. Do not run final SDD verification until H.2 is complete.

## Slice H.1 Correction — Durable per-job status display
- Added grouped `channel: status` counts from the already sanitized `jobs[]` payload, so administrators see durable delivery outcomes instead of the batch's queued aggregate alone.
- Extended the structural UI proof to require `jobs.reduce` and `job.status` consumption/rendering.

### Correction Evidence
| Evidence | Result |
|---|---|
| RED | Structural UI check failed before the grouped `jobs.reduce` projection existed. |
| GREEN | `cd frontend && node scripts/check-whatsapp-billing-notifications-ui.mjs` → passed. |
| Regression/lint/build | `npm run test:planilla-detail`, `npm run lint`, and `npm run build` → passed. |
| Runtime/UI harness | N/A — grouped presentation of already-sanitized local API data; no provider or browser fixture exists. |
| Rollback boundary | Revert only the H.1 correction block in `frontend/src/pages/PlanillaPage.tsx` and its two assertions in `frontend/scripts/check-whatsapp-billing-notifications-ui.mjs`; original H.1 preview/readiness/status behavior remains. |

### Native correction metadata
- Work-unit: `slice-h1-durable-status-display-correction`
- Native token: `sha256:fd8d4530d824754552d169e6ea8fde0ef2d32bfeb606f91204b280f8cb1e2248`
- Correction delta: 14 lines (12 UI additions + 2 structural assertions); combined H.1 is 239/400 changed lines.

### Historical Next Step (superseded)
Only H.2 remains. Final verification stays blocked until H.2 completes.


## Slice H.2 — Runtime operations and rollback
- [x] H.2 Added a separately restarted `official_whatsapp_worker`, live fail-closed sender/Utility-template readiness, ephemeral opaque-media URLs, private production configuration/preflight validation, explicit callback/media Nginx routes, and the rollback runbook. Missing, malformed, or unreachable provider facts keep dispatch unavailable; secrets are neither committed nor logged.

### Work Unit Evidence — H.2
| Evidence | Result |
|---|---|
| Focused backend tests | Docker Python 3.12.8 `pytest` for runtime, worker, transport, webhook, media, and publication routes: **46 passed**. |
| Runtime harness | Disposable Compose preflight with synthetic private env passed; packaged Nginx `nginx -t` passed with local `backend` host mapping. No Twilio, provider, VPS, production DB, email, or message I/O. |
| Frontend proof | WhatsApp structural check, planilla-detail regression, lint, and production build all passed. |
| Rollback boundary | Set both official flags false, stop `official_whatsapp_worker`, cancel unleased jobs/revoke media tokens through the approved procedure, retain audit rows; additive migrations remain subject to the existing schema/restore boundary and never trigger email fallback. |

### Native settlement metadata
- Work-unit: `slice-h2-runtime-operations`
- Evidence revision: `sha256:8004ac9ad64a0572b81a28db2b4af69f25d0d94612862f0c92b3d5487067ab3c` (native settlement complete).
- Superseded measurement: **381 lines**; corrected initial candidate: **363 lines** (**341** implementation/operations + **22** tasks/progress).

### Historical Status (superseded)
All **16/16** tasks were complete at this checkpoint; canonical live routing is at the top and final heading of this artifact.


## Slice H.2 Gate Correction — Deployment hardening
- Added the private shared media directory to the backend image with `sipad` ownership; a disposable named-volume harness proved both API and worker UID `10001` can read/write it.
- Replaced the inherited HTTP healthcheck with bounded PID-1 worker-command plus `SELECT 1` database liveness proof.
- Preflight now requires Twilio account/API credentials, positive capacity inputs, and exact same-origin canonical callback paths; runtime parses scheme/hostname/effective port and rejects hostname-prefix, query, and path confusion.

### Exact corrected proof
The following setup and commands were run from the repository root. It contains only synthetic values and creates no production environment file:
```bash
envf=$(mktemp)
chmod 600 "$envf"
cat > "$envf" <<'EOF'
IMAGE_TAG=test-release
APP_HOST_PORT=18080
POSTGRES_DB=sipad
POSTGRES_USER=sipad
POSTGRES_PASSWORD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
CORS_ORIGINS=["https://sipad.example"]
JWT_SECRET=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
DOCENTE_DEFAULT_PASSWORD=StrongTemporaryPass1
APP_ENV=production
AUTO_SCHEMA_BOOTSTRAP=false
OFFICIAL_WHATSAPP_ENABLED=true
WHATSAPP_DISPATCH_ENABLED=true
TWILIO_ACCOUNT_SID=ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
TWILIO_API_KEY_SID=SKbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
TWILIO_API_KEY_SECRET=private-test-only
BILLING_MEDIA_PUBLIC_BASE_URL=https://sipad.example
TWILIO_OFFICIAL_FROM=+14155550123
TWILIO_OFFICIAL_SENDER_SID=XEcccccccccccccccccccccccccccccccc
TWILIO_OFFICIAL_CONTENT_SID=HXdddddddddddddddddddddddddddddddd
TWILIO_STATUS_CALLBACK_URL=https://sipad.example/api/twilio/whatsapp/status
TWILIO_INBOUND_CALLBACK_URL=https://sipad.example/api/twilio/whatsapp/inbound
TWILIO_AUTH_TOKEN=private-test-only
TWILIO_OFFICIAL_MEDIA_MPS=2.5
TWILIO_OFFICIAL_MOVING_RECIPIENT_LIMIT=20
EOF
```

| Exact command | Exit/result | Bounded output SHA-256 |
|---|---|---|
| `docker run --rm -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_official_whatsapp_runner.py tests/services/test_billing_notification_worker.py tests/services/test_twilio_whatsapp_transport.py tests/services/test_whatsapp_webhook_service.py tests/routers/test_billing_media.py tests/routers/test_billing_publication_email.py -q` | 0; 46 passed | `e93acc30704be2e19494698132fa5565f37ea586e43c77e8316c5b23c0790cc5` |
| `docker build -f deploy/backend.Dockerfile -t sipad-h2-ownership-test:local .` | 0 | `6f6ea0891ed828565755197d34ddcedfe36a3a0cda0b8969e3b5c9238c5f358d` |
| `docker volume create sipad_h2_media_ownership_196468 >/dev/null && docker run --rm --user 10001:10001 --read-only --tmpfs /tmp:size=16m -v sipad_h2_media_ownership_196468:/app/backend/data/billing-media sipad-h2-ownership-test:local sh -c 'test -d /app/backend/data/billing-media && test -w /app/backend/data/billing-media && touch /app/backend/data/billing-media/.ownership-check && test -f /app/backend/data/billing-media/.ownership-check'` | 0; API UID access passed | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `docker run --rm --user 10001:10001 --read-only --tmpfs /tmp:size=16m -v sipad_h2_media_ownership_196468:/app/backend/data/billing-media sipad-h2-ownership-test:local python -c "from pathlib import Path; assert Path('/app/backend/data/billing-media/.ownership-check').exists()"` | 0; worker UID access passed | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `SKIP_GIT_CLEAN_CHECK=1 ENV_FILE="$envf" COMPOSE_FILE="$PWD/deploy/compose.production.yml" deploy/scripts/preflight.sh` | 0 | `60df4c828872a588e0ea4f235359dd8babc33a57ee8d27dc115e42f9ffdc09ee` |
| `docker compose --env-file "$envf" -f deploy/compose.production.yml config` | 0; worker command/DB health assertion passed | `a23ed494f89fdb2b653d3ed2e42e566d10e3ed047c039c84f53c89853925310e` |
| `docker run --rm --add-host backend:127.0.0.1 -v "$PWD/deploy/nginx/app-nginx.conf:/etc/nginx/nginx.conf:ro" nginx:1.27.4-alpine3.21 nginx -t` | 0 | `1b4564e6eaa90bbe93498d9c159a1184c3f24029216cca1f01f0419660c6e235` |
| `cd frontend && node scripts/check-whatsapp-billing-notifications-ui.mjs && npm run test:planilla-detail && npm run lint && npm run build` | 0 | `f27818b4aef12ed9ad74319c5d1715220ce346c1ed88b5fcc54b3d80f9fe2726` |

The negative preflight used the same setup except `TWILIO_ACCOUNT_SID=` and `TWILIO_OFFICIAL_MEDIA_MPS=0`; its exact command was `SKIP_GIT_CLEAN_CHECK=1 ENV_FILE="$envf" COMPOSE_FILE="$PWD/deploy/compose.production.yml" deploy/scripts/preflight.sh`, exited 1, and produced `97789bd669d785faa8f36527974b8d7fe5672623b3457c134bf1c35382dc1e51`.

### Rollback boundary — H.2 complete
Set both flags false, stop `official_whatsapp_worker`, then cancel only unleased jobs and revoke tokens through the approved procedure; keep all audit rows and use no email fallback. Revert H.2 source/config only: `backend/app/{config.py,routers/billing_publication.py,services/billing_notification_preview.py,workers/official_whatsapp_runner.py}`, `backend/tests/services/test_official_whatsapp_runner.py`, `deploy/{backend.Dockerfile,compose.production.yml,.env.production.example,nginx/app-nginx.conf,scripts/preflight.sh}`, and `DEPLOYMENT.md`. Database rollback is separate, non-automatic, and remains governed by the existing compatible-image/external-backup boundary.

### Native correction accounting
- Work-unit: `slice-h2-deployment-hardening-correction`; token `sha256:9fbe1f0c6d726b4652b4457ddc5f8a3a4867658e1d490507b50f7b9cc9d1ad2f`.
- Native correction settlement: complete (`slice-h2-hardening-settle-20260903-01`); source/tests/config plus retained evidence are within the 200-line bound.

## Next Step
Run final independent `sdd-verify` for `official-whatsapp-billing-notifications`.

## Slice H.2 Final Closure Correction
- URL parser tests now reject malformed/out-of-range ports without raising: `docker run --rm --pull=never -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_official_whatsapp_runner.py -q` exited 0 (3 passed), output SHA-256 `49619d7b47850f113574e71666df420a376305921a87f02e312f1c704711ed5d`.
- Progress structural check `test "$(grep -c '^## Next Step$' openspec/changes/official-whatsapp-billing-notifications/apply-progress.md)" -eq 1 && grep -q '^All slices \*\*A–H\*\* are complete: \*\*16/16\*\* tasks\.' openspec/changes/official-whatsapp-billing-notifications/apply-progress.md` exited 0, output SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Rollback: revert only this correction's `backend/app/workers/official_whatsapp_runner.py`, `backend/tests/services/test_official_whatsapp_runner.py`, and `openspec/changes/official-whatsapp-billing-notifications/apply-progress.md`; no database operation is part of rollback.

## Slice H.2 URL Proof and Ownership Hash Fix
- Added query, mismatched-effective-port, and distinct nonnumeric-port regression cases while retaining hostname-prefix, path, origin, and out-of-range-port coverage. Exact runner `docker run --rm --pull=never -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/services/test_official_whatsapp_runner.py -q` exited 0 (4 passed), SHA-256 `10b661100a48ecdbbcf9ce3f1e3ff6f8c1f38678fc52fa2938042edb8a64407e`.
- Exact ownership command now suppresses only the volume-create name: `docker volume create sipad_h2_media_ownership_196468 >/dev/null && docker run --rm --user 10001:10001 --read-only --tmpfs /tmp:size=16m -v sipad_h2_media_ownership_196468:/app/backend/data/billing-media sipad-h2-ownership-test:local sh -c 'test -d /app/backend/data/billing-media && test -w /app/backend/data/billing-media && touch /app/backend/data/billing-media/.ownership-check && test -f /app/backend/data/billing-media/.ownership-check'` exited 0, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Rollback: revert only `backend/tests/services/test_official_whatsapp_runner.py` and this evidence update; no database operation is involved.

## Final verification remediation — incomplete
- Implemented durable policy filtering for automatic and manual legacy billing email paths; pending/ambiguous consented jobs are blocked, while terminal `failed`/`undelivered` status selects the existing idempotent email alternative.
- Added executable `python -m app.workers.official_whatsapp_runner --rollback-unleased`, documented Compose invocation, and tested cancellation of queued unleased jobs with bound-token revocation while leased jobs remain untouched.
- Extended media-token expiry immediately before dispatch and made migration adoption guards tolerate a fully precreated compatible runtime schema.
- Focused Docker proof: `docker run --rm --pull=never -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/test_complete_runtime_schema_migration.py tests/routers/test_billing_publication_email.py tests/routers/test_billing_media.py tests/services/test_whatsapp_webhook_service.py tests/services/test_official_whatsapp_runner.py -q` → `39 passed`.
- **Primary failure:** full Docker backend pytest exited 1: `9 failed, 459 passed, 19 skipped`; failures are unchanged unrelated exclusion-planilla, biometric-smoke, and teacher-profile-import tests. PostgreSQL downgrade/runtime and frontend checks remain unrun.
- Native settlement was refused as `blocked(maintainer_decision)` because the correction candidate accounting reports **332 changed lines** against the active 400-line bound; no successful remediation settlement exists.
- Rollback boundary: revert this remediation's policy/router/webhook/runner/migration/test/document changes; the operation itself only cancels unleased queued WhatsApp jobs and revokes their linked tokens, preserving audit rows.

## Next Step
Obtain the required native maintainer decision/reset, then rerun PostgreSQL 16, frontend, and independent `sdd-verify`.

## Aggregate official-job fallback correction
- Replaced last-row-wins job status selection with aggregate precedence: any unresolved/ambiguous official WhatsApp job blocks legacy email, and only an all-terminal-failure set permits the terminal email alternative.
- Regression: `docker run --rm --pull=never -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/routers/test_billing_publication_email.py -q` exited 0: 21 passed; SHA-256 `bbafd5fec93f489e27e2fab1fd738bd5088015e9d41a1151d64b25d526f7e441`.
- Rollback boundary: revert only aggregate selection and its permutation regression test; durable existing job/email audit records remain untouched.

## Next Step
Run independent `sdd-verify`.
