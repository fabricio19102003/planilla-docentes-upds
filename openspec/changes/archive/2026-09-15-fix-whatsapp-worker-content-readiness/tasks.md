# Implementation Tasks: Fix WhatsApp Worker Content Readiness

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 25–45 across two files |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

## Phase 1 — Focused Regression (test first)

- [x] 1.1 RED — In `backend/tests/services/test_official_whatsapp_runner.py`, add a one-cycle mocked runner regression beside `test_runner_ordinary_dispatch_authorization_uses_effective_enabled`: patch settings with enabled process and activation gates, a 32-byte HMAC key, and an exact valid `HX` Content SID; capture `status_from_readiness()` keyword arguments; return global delivery off with activation capable; capture `claim_intent`; assert the SID is forwarded exactly and that `claim_intent()` is `"activation_test"` rather than ordinary; stop with `KeyboardInterrupt` without provider or database I/O. <!-- sdd-owner: implementation -->
- [x] 1.2 RED verification — Run `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py` (or the repository-local Python environment when `venv/bin/python` is unavailable) and confirm the new regression fails because `configured_content_sid` is absent at the readiness boundary. <!-- sdd-owner: implementation -->

## Phase 2 — Minimal Runtime Correction

- [x] 2.1 GREEN — In `backend/app/workers/official_whatsapp_runner.py`, add only `configured_content_sid=settings.TWILIO_OFFICIAL_CONTENT_SID` to the existing `status_from_readiness()` call in `run()`; retain the service-owned validation, default compatibility behavior for other callers, all global-delivery gates, leasing, authorization, transport, and rollback logic unchanged. <!-- sdd-owner: implementation -->
- [x] 2.2 GREEN verification — Re-run `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py` (with the same local-environment fallback) and confirm the mocked cycle forwards the SID and chooses only `activation_test` while global delivery is off. <!-- sdd-owner: implementation -->

## Phase 3 — Boundary Validation and Cleanup

- [x] 3.1 TRIANGULATE — Run `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py tests/services/test_whatsapp_delivery_control.py` (with the same local-environment fallback) to prove the worker wiring and existing missing, malformed, and non-`HX` SID fail-closed readiness validation together. <!-- sdd-owner: implementation -->
- [x] 3.2 REFACTOR — Review the two-file diff at `backend/app/workers/official_whatsapp_runner.py` and `backend/tests/services/test_official_whatsapp_runner.py`; keep it limited to one forwarded argument and one isolated regression, remove incidental test-only complexity, and confirm it remains below the 400-line budget with no deployment, configuration, provider, schema, API, or runbook change. <!-- sdd-owner: implementation -->

## Rollback

Revert the single readiness-call argument and its focused runner regression. This restores the prior fail-closed worker behavior without changing persisted settings, jobs, authorizations, provider state, deployment configuration, or operator procedures.
