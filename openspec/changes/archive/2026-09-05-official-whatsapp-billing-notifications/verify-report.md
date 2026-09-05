```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:4afa6e9a7192ce76d2948ad0277912181af989e036fa95cf1d3b0d9629fba5a3
verdict: pass
blockers: 0
critical_findings: 0
requirements: 7/7
scenarios: 13/13
test_command: "docker run --rm --pull=never -v $PWD:/workspace -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/test_complete_runtime_schema_migration.py tests/services/test_billing_notification_service.py tests/routers/test_billing_publication_email.py tests/services/test_twilio_whatsapp_transport.py tests/services/test_billing_notification_worker.py tests/services/test_whatsapp_webhook_service.py tests/routers/test_billing_media.py tests/services/test_official_whatsapp_runner.py -q"
test_exit_code: 0
test_output_hash: sha256:367f6a354ec3998cfa2ed77209f985005db4f074fc01fec62a3a383dc0e93c95
build_command: "cd frontend && node scripts/check-whatsapp-billing-notifications-ui.mjs && npm run test:planilla-detail && npm run lint && npm run build"
build_exit_code: 0
build_output_hash: sha256:33c3a1ec4bd77b372db472282ce475a25bf0df125dbe51cac1fe98888e67ff02
```

## Verification Report

**Change**: official-whatsapp-billing-notifications
**Version**: N/A
**Mode**: Standard

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 16 |
| Tasks complete | 16 |
| Tasks incomplete | 0 |
| Requirements | 7 |
| Scenarios | 13 |

The totals were counted from the current `### Requirement:` and `#### Scenario:` headings in both delta specifications.

### Build & Tests Execution

**Focused official WhatsApp and migration suite**: ✅ Passed
```text
docker run --rm --pull=never -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/test_complete_runtime_schema_migration.py tests/services/test_billing_notification_service.py tests/routers/test_billing_publication_email.py tests/services/test_twilio_whatsapp_transport.py tests/services/test_billing_notification_worker.py tests/services/test_whatsapp_webhook_service.py tests/routers/test_billing_media.py tests/services/test_official_whatsapp_runner.py -q
71 passed, 48 warnings in 22.30s
exit: 0
output sha256: 367f6a354ec3998cfa2ed77209f985005db4f074fc01fec62a3a383dc0e93c95
```

**Final multi-job ambiguity regression**: ✅ Passed in both insertion orders
```text
docker run --rm --pull=never -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest tests/routers/test_billing_publication_email.py -k 'ambiguous_job_dominates_terminal_job_regardless_of_row_order' -q
2 passed, 19 deselected, 4 warnings in 2.05s
exit: 0
output sha256: 5c875833155decfdb752b881d8b96835e770ffeaac48fa5f7061620c6934a514
```
The regression creates `undelivered + ambiguous` jobs in both row orders for the same teacher and publication. `_email_eligible_users` returns no recipient in either case. Static inspection agrees: it groups all states per teacher and permits fallback only when every state is `failed` or `undelivered`; any unresolved or ambiguous state dominates independently of query order.

**Full backend suite with writable data tmpfs**: ⚠️ Four pre-existing order-dependent failures; no candidate-caused failure
```text
docker run --rm --pull=never --tmpfs /workspace/backend/data:rw,mode=1777 -v "$PWD:/workspace" -w /workspace/backend whatsapp-pr1-test:latest python -m pytest -q
4 failed, 466 passed, 19 skipped, 348 warnings in 77.77s
exit: 1
output sha256: a33107f360a798c0bb4d041fc91777cfa1b7d742f78968d1296b732ec5697d6a
```
All four failures are the teacher-profile import cases that attempt to insert an already-seeded `ACTIVE_ACADEMIC_PERIOD`. The exact same four tests fail during the frozen-base full-suite run at commit `bd6329aad26e0629c3e6e52e3140f986cde2260a`; that base run had 33 unrelated failures overall and output SHA-256 `beb97a3a363d28a90abee8ddf8342adba6ca0658dfc4c154dbc02f830fece098`. The teacher-profile file passes in isolation on both the current candidate (9 passed, SHA-256 `30ffb8e0c202f83a59c56e4258408ccefa5684becd14845e969d4b662d850f7c`) and frozen base (9 passed, SHA-256 `fb422fe5809248cab0350c72bce5a4abfa3293334f8ecfb859a0014252d27cb3`). This proves a pre-existing suite-order fixture interaction rather than a candidate regression.

**Disposable PostgreSQL 16 migration proof**: ✅ Passed
```text
sh /tmp/verify_whatsapp_pg_v4.sh
fresh upgrade through dd4e5f6a7b8c: passed
downgrade to cc3d4e5f6a7b and re-upgrade: passed
fully precreated compatible schema stamped at b8c4d2e6f901 and adopted without losing MIGRATION_SENTINEL: passed
exit: 0
output sha256: 27625b6dc1b7d3b8000e16e5821c09949989cf5ec51322129714100a59acea52
```
The disposable PostgreSQL container and network were removed by the harness cleanup.

**Exact fallback, delayed-media, and rollback harness**: ✅ Passed
```text
terminal_email_alternative_exactly_once=passed
delayed_dispatch_media_expiry_refresh=passed
rollback_unleased_audit_preservation=passed
exit: 0
output sha256: 5cda8a344718cd982aec3ee043f4a4ebadc993bb610161acc243017cb4477d2a
```
The local fake-transport harness proves ambiguous lookup never emails, a verified terminal lookup produces one idempotent email attempt, delayed dispatch refreshes the bound media token, and rollback cancels/revokes only unleased queued work while preserving leased work and audit rows.

**Frontend structural, planilla regression, lint, and production build**: ✅ Passed
```text
cd frontend && node scripts/check-whatsapp-billing-notifications-ui.mjs && npm run test:planilla-detail && npm run lint && npm run build
exit: 0
output sha256: 33c3a1ec4bd77b372db472282ce475a25bf0df125dbe51cac1fe98888e67ff02
```

**Synthetic Compose/preflight and packaged Nginx checks**: ✅ Passed
```text
SKIP_GIT_CLEAN_CHECK=1 ENV_FILE=/tmp/verify-whatsapp-synthetic.env COMPOSE_FILE="$PWD/deploy/compose.production.yml" deploy/scripts/preflight.sh
docker compose --env-file /tmp/verify-whatsapp-synthetic.env -f deploy/compose.production.yml config
docker run --rm --pull=never --add-host backend:127.0.0.1 -v "$PWD/deploy/nginx/app-nginx.conf:/etc/nginx/nginx.conf:ro" nginx:1.27.4-alpine3.21 nginx -t
exit: 0
bounded output sha256: 8eabe615f4a1f7364e04fb8906d90e5087e882aa34d5c6659c098e0a33a4e620
compose render sha256: 48089908ce4dbb15357a295b197fc7eefb4999a725c61beb597fefb448528c77
```
The synthetic environment file was mode `0600`. Rendered Compose contains the dedicated worker command and database liveness check; packaged Nginx configuration is valid.

**Coverage**: ➖ Not available; the project declares no coverage threshold.

### Spec Compliance Matrix
| Requirement | Scenario | Runtime evidence | Result |
|-------------|----------|------------------|--------|
| Successful outbound delivery attempt | Successful send attempt | Publication router tests plus exact terminal-fallback harness | ✅ COMPLIANT |
| Successful outbound delivery attempt | Ambiguous WhatsApp outcome | Pending/ambiguous policy test and two-order multi-job regression | ✅ COMPLIANT |
| WhatsApp fallback boundary | No consent alternative | Policy and publication email tests | ✅ COMPLIANT |
| WhatsApp fallback boundary | Definite terminal alternative | Exact terminal/replay harness proves one durable attempt | ✅ COMPLIANT |
| Consent and confirmation | Confirm eligible batch | Consent, masked preview, digest, confirmation, and media-binding tests | ✅ COMPLIANT |
| Consent and confirmation | Stale or unsafe confirmation | Stale digest test rejects with zero jobs | ✅ COMPLIANT |
| Fail-closed readiness and durable dispatch | Ready dispatch | Worker leasing/capacity/transport tests and PostgreSQL proof | ✅ COMPLIANT |
| Fail-closed readiness and durable dispatch | Not ready or ambiguous | Readiness drift, timeout ambiguity, no-retry/no-email tests | ✅ COMPLIANT |
| PDF media delivery | Valid fetch | Repeated HEAD/GET and delayed-expiry-refresh tests | ✅ COMPLIANT |
| PDF media delivery | Invalid media | Expired, revoked, unbound, mismatched, tampered, and oversized tests | ✅ COMPLIANT |
| Signed monotonic callbacks and reconciliation | Out-of-order callbacks | Signature, dedupe, monotonic projection, and bounded reconciliation tests | ✅ COMPLIANT |
| Signed monotonic callbacks and reconciliation | STOP or unknown sender | Authenticated idempotent STOP and unknown-sender tests | ✅ COMPLIANT |
| Channel policy and operations | Definite failure and rollback | Exact idempotent fallback and rollback-preservation harness | ✅ COMPLIANT |

**Compliance summary**: 13/13 scenarios compliant; 7/7 requirements fully compliant.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Successful outbound delivery attempt | ✅ Implemented | Automatic and manual regular/practice routes apply the durable channel filter before legacy email execution. |
| WhatsApp fallback boundary | ✅ Implemented | No consent and all-terminal-failure are the only email alternatives; unresolved state dominates across multiple jobs. |
| Consent and confirmation | ✅ Implemented | Verified evidence, masked E.164, canonical digest, current-state replan, and atomic intent creation are present. |
| Fail-closed readiness and durable dispatch | ✅ Implemented | Readiness, leasing, retry, ambiguity, MPS, and moving-recipient capacity behavior passed. |
| PDF media delivery | ✅ Implemented | Immutable snapshot artifacts and bound opaque tokens enforce size, identity, expiry, revocation, MIME, and no-store. |
| Signed monotonic callbacks and reconciliation | ✅ Implemented | Canonical signature validation precedes idempotent monotonic projection and bounded lookup. |
| Channel policy and operations | ✅ Implemented | Durable status UI, default-off flags, executable unleased rollback, token revocation, and audit preservation passed. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Immutable outbox and transactional leasing | ✅ Yes | Durable intent uniqueness, committed leases, SQLite CAS, and PostgreSQL locking are covered. |
| Digest-bound confirmation | ✅ Yes | Current replan and stale-digest rejection pass. |
| Fail-closed Content transport/readiness | ✅ Yes | Content-only payload, canonical callbacks, capacity gates, and runtime URL validation pass. |
| Email only for absent consent or definite terminal failure | ✅ Yes | Aggregate precedence closes the final row-order ambiguity defect. |
| Secure repeatable media | ✅ Yes | Job/artifact/token binding and repeated HEAD/GET behavior pass. |
| Monotonic callbacks and bounded reconciliation | ✅ Yes | Duplicate/out-of-order events and known-SID lookup pass without email side effects. |
| Executable rollback preserving audit | ✅ Yes | Only unleased queued jobs and their tokens are mutated. |
| Additive compatible migration path | ✅ Yes | Fresh, downgrade/re-upgrade, and precreated-schema PostgreSQL flows pass. |

### Issues Found

**CRITICAL**: None.

**WARNING**:
1. Four teacher-profile import tests fail only in full-suite order on both the current candidate and frozen base because of duplicate `ACTIVE_ACADEMIC_PERIOD` fixture state; they pass independently and are not candidate-caused.
2. Vite reports a future native-config incompatibility and a production chunk above 500 kB.
3. Existing datetime, Pydantic, pytest-asyncio, and passlib deprecation warnings remain outside this change.

**SUGGESTION**:
1. Repair the shared teacher-profile/full-suite fixture isolation in a separate change.
2. Plan frontend chunk splitting and Vite native-config cleanup independently of this feature.

### Safety Boundary
No Twilio, Resend, Sandbox, provider network API, VPS, production database, production data, message, commit, push, PR, deployment, or production mutation occurred. Provider behavior used local fakes; PostgreSQL 16 and Nginx were disposable; deployment checks used synthetic values only.

### Verdict
PASS
All 7 requirements and all 13 scenarios have passing candidate-scoped runtime evidence. The final multi-job correction prevents email whenever any relevant job remains unresolved or ambiguous, independent of row order; the only full-suite failures are reproducible pre-existing order-dependent fixture defects.
