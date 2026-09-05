# Tasks: WhatsApp Billing Notifications

## Forecast
| Field | Value |
|---|---|
| Lines | 1,000–1,400 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | A consent (feature/tracker) → B persistence (A) → C digest/policy (B) → D preview (C) → E worker (D) → F webhooks (E) → G PDF (F) → H UI/ops (G); tracker→main |
| Delivery | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained: Yes
Chain: feature-branch-chain
Budget risk: High
First slice: A

### Units
| Unit | Goal | PR/base | Test command | Harness | Rollback |
|---|---|---|---|---|---|
| A | Consent/E.164 preference | PR1/tracker | `cd backend && pytest tests/services/test_billing_notification_service.py` | SQLite + migration smoke | Revert preference migration |
| B | Batch/job/event/media persistence | PR2/A | `cd backend && pytest tests/services/test_billing_notification_service.py` | PostgreSQL smoke | Revert persistence migration |
| C | Digest, policy, flags/config | PR3/B | `cd backend && pytest tests/services/test_billing_notification_service.py` | SQLite policy fixtures | Revert policy/config |
| D | Preview/confirm | PR4/C | `cd backend && pytest tests/routers/test_billing_publication_email.py` | TestClient digest | Revert routes |
| E | Worker/provider/readiness | PR5/D | `cd backend && pytest tests/services/test_twilio_whatsapp_transport.py` | PostgreSQL two-worker lease | Stop worker; cancel unleased |
| F | Webhooks/reconciliation/opt-out | PR6/E | `cd backend && pytest tests/routers` | Signed webhook + SID lookup | Disable projection; retain events |
| G | PDF media | PR7/F | `cd backend && pytest tests/services/test_contract_pdf_page_size.py` | Repeated HEAD/GET | Revoke tokens/route |
| H | UI/deploy/docs | PR8/G | `cd frontend && npm run test:e2e && npm run build` | Staging walkthrough | Disable flags/worker; revert UI |

## P1: Consent (A)
- [x] A.1 **RED:** Tests: verified E.164, evidenced consent, revision/opt-out evidence.
- [x] A.2 Add `WhatsAppPreference`, schema/export, and Alembic migration.

## P2: Persistence (B)
- [x] B.1 **RED:** Tests: batch/job/event/media state and `SM|MM` SID contracts.
- [x] B.2 Add `BillingNotificationBatch/Job`, `WhatsAppEvent`, `BillingMediaToken` models, schemas, exports, migration.

## P3: Digest and Policy (C)
- [x] C.1 **RED:** Tests: digest binding, consent snapshots, channel fallback.
- [x] C.2 Implement digest, snapshots, email policy, flags.

## P4: Preview (D)
- [x] D.1 **RED:** Router tests for masked preview, capacity forecast, digest, stale rejection/no jobs.
- [x] D.2 Implement preview/replan/confirm.

## P5: Worker (E)
- [x] E.1 **RED:** PostgreSQL competing leases/reservations; clock tests for crash requeue, drift backoff, ambiguity, no email/duplicate.
- [x] E.2 Implement readiness/content adapters, restricted transport, `SKIP LOCKED`/SQLite CAS, throttling, retries, worker.

## P6: Webhooks (F)
- [x] F.1 **RED:** Signature URL/raw fields, duplicate ordering, unknown sender, STOP cancellation.
- [x] F.2 Implement webhook routes, dedupe/projection, reconciliation, opt-out, email fallback.

## P7: PDF (G)
- [x] G.1 **RED:** Binding, expiry, revocation, 15,000,000-byte cap, filename/MIME/no-store, repeated HEAD/GET.
- [x] G.2 Implement PDF, storage, tokens, route.

## P8: UI and Operations (H)
- [x] H.1 Add readiness, preview/confirm, status UI/hooks.
- [x] H.2 Add worker, secrets, Nginx URL, rollback runbook; run backend pytest and frontend lint/build.
