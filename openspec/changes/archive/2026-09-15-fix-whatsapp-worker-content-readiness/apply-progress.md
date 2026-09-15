# Apply Progress: Fix WhatsApp Worker Content Readiness

## Status

- **Change:** `fix-whatsapp-worker-content-readiness`
- **Result:** completed; ready for verify
- **Evidence revision:** native attempt token `sha256:cf1454c99886dd85354d3bfe90286c4a5197a2bfc625cb91a7f1ceb8c2ec9679`
- **Structured status consumed:** authoritative OpenSpec apply-ready status; proposal, spec, design, and tasks were all present; apply began with 0/6 complete; verify and archive remained blocked pending apply completion.
- **Action context:** `repo-local`; authoritative workspace and only allowed edit root: `/home/pedro/projects/planilla-docuentes/planilla-docentes-upds-worktrees/github-policy-master`; no warnings.

## Completed Tasks

- [x] 1.1 Added a single mocked one-cycle runner regression that isolates database and provider I/O, captures readiness arguments, and proves the global-off activation intent is `activation_test`.
- [x] 1.2 Captured RED: the focused runner suite failed with `KeyError: 'configured_content_sid'` at the readiness-boundary assertion.
- [x] 2.1 Forwarded only `settings.TWILIO_OFFICIAL_CONTENT_SID` as `configured_content_sid` in the worker's existing `status_from_readiness()` call.
- [x] 2.2 Captured GREEN: the focused runner suite passed, including exact SID forwarding and activation-only claim intent.
- [x] 3.1 Triangulated the runner wiring with existing delivery-control missing, malformed, and non-`HX` SID fail-closed coverage.
- [x] 3.2 Reviewed the two-file product diff; it contains one runtime argument and one isolated regression with no incidental production changes.

All matching implementation checkboxes are visibly marked `[x]` in `tasks.md`.

## Files Changed

- `backend/app/workers/official_whatsapp_runner.py`
- `backend/tests/services/test_official_whatsapp_runner.py`
- `openspec/changes/fix-whatsapp-worker-content-readiness/tasks.md`
- `openspec/changes/fix-whatsapp-worker-content-readiness/apply-progress.md`

## Test Evidence

| Stage | Command | Result |
|---|---|---|
| RED | `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py` | Failed as intended: 1 failed, 11 passed; new regression raised `KeyError: 'configured_content_sid'`. |
| GREEN | `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py` | Passed: 12 passed. |
| TRIANGULATE | `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py tests/services/test_whatsapp_delivery_control.py` | Passed: 23 passed. |

The passing commands emitted existing Python 3.14 deprecation warnings from pytest-asyncio, FastAPI/Starlette, Pydantic, and `datetime.utcnow()`; no test failures resulted.

## Design Conformance and Scope

- No deviation from design.
- Validation remains service-owned; the existing optional default behavior for other callers remains unchanged.
- Global-delivery gates, leasing, authorization, transport, rollback, configuration, deployment, provider, schema, API, and runbook surfaces were unchanged.
- Product diff: 55 added lines, 0 removed lines (1 runtime line and 54 focused test lines); below the 400-line review budget and the 80-line attempt budget.

## Workload / PR Boundary

Single cohesive work unit: worker readiness-boundary forwarding plus its isolated regression. No chained PR or size exception is needed. No commit was created.

## Remaining Tasks

None. Every implementation-owned task is complete.
