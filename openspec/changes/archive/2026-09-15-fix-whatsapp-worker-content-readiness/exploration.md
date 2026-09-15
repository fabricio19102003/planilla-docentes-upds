# Exploration: Fix WhatsApp Worker Content Readiness

## Phase result contract

| Field | Result |
| --- | --- |
| Change | `fix-whatsapp-worker-content-readiness` |
| Phase | explore |
| Status | ready for proposal/apply |
| Artifact store | OpenSpec |
| Execution mode | auto |
| Delivery strategy | ask-on-risk |
| Review budget | 400 changed lines |
| Skill resolution | none (no phase-skill path was injected) |
| Production/operator action | none; production remains fail-closed and operator scripts remain untouched |

## Confirmed defect

`backend/app/workers/official_whatsapp_runner.py:169` calls `status_from_readiness()` with the process gates, activation gates, and recipient-HMAC key but omits `configured_content_sid`.

`status_from_readiness()` in `backend/app/services/whatsapp_delivery_control.py` requires that optional value to validate the configured `HX` Content SID before setting `activation.creation_capable`. With its default `None`, `_configured_content_sid_is_valid()` returns false, therefore `creation_capable`, `dispatch_capable`, and compatibility field `activation.capable` are false even when the deployed worker has valid settings and all other activation prerequisites pass.

In the worker cycle, a false `activation.capable` invokes `rollback_unleased_activation()`, and `intent()` cannot return `activation_test`. Thus a properly released activation authorization is revoked/cancelled instead of being claimed and sent. This is fail-closed but incorrectly prevents the intended bounded activation path.

The same settings value is already supplied at the other relevant readiness boundary: `current_delivery_status()` passes `settings.TWILIO_OFFICIAL_CONTENT_SID` to `status_from_readiness()`. The worker call is the lone production call site that omits it.

## Minimal implementation plan

1. **RED — runner regression:** Add one focused test in `backend/tests/services/test_official_whatsapp_runner.py` that runs one mocked worker cycle with global delivery disabled, both activation gates enabled, a 32-byte HMAC key, and a valid configured `HX` SID. Its mocked `status_from_readiness()` must assert it receives `configured_content_sid` equal to the configured setting and return a capable global-off activation status; the captured `claim_intent()` must return `activation_test`.
2. **GREEN — single wiring change:** In `backend/app/workers/official_whatsapp_runner.py`, add `configured_content_sid=settings.TWILIO_OFFICIAL_CONTENT_SID` to the existing `status_from_readiness()` call inside `run()`.
3. **Focused verification:** Run `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py tests/services/test_whatsapp_delivery_control.py` (or the repository-local Python environment if this worktree lacks `backend/venv`). No full suite is required for this one-argument correction unless the focused suite reveals coupling.

Expected product-source surface: two files, one test and one runtime wiring line. This should be materially below the 400-line review budget; no delivery decision or size exception is presently required.

## Exact regression shape

The new runner test should mirror the existing `test_runner_ordinary_dispatch_authorization_uses_effective_enabled` mocking pattern while proving the activation branch:

- Patch `SessionLocal`, `mark_worker_heartbeat`, `sweep_expired_activations`, and `OfficialWhatsAppRuntime.from_settings` so no provider/database/production I/O occurs.
- Supply settings with `BILLING_WHATSAPP_ACTIVATION_API_ENABLED=True`, `BILLING_WHATSAPP_ACTIVATION_DISPATCH_ENABLED=True`, `WHATSAPP_RECIPIENT_HMAC_KEY="h" * 32`, and a valid `TWILIO_OFFICIAL_CONTENT_SID`.
- Capture `status_from_readiness()` keyword arguments and assert the exact configured SID was forwarded. Return `global_delivery={"requested": False, "effective": False}` and `activation={"capable": True}`.
- Capture the `claim_intent` callback passed to `BillingNotificationWorker`, assert it produces `"activation_test"`, then stop the infinite runner loop with `KeyboardInterrupt` as the existing test does.

This catches both the missing argument and the meaningful behavioral consequence: valid global-off activation work becomes claimable. It does not simulate transport, consume a dispatch authorization, or send a provider message.

## Edge cases and compatibility

- A missing, malformed, or non-`HX` Content SID must remain incapable: `status_from_readiness()` already validates it and the proposed change forwards the actual configured value rather than bypassing validation.
- Invalid/missing configuration still stops before the loop because `OfficialWhatsAppRuntime.from_settings()` remains unchanged.
- Disabled activation gates, a short/missing HMAC key, unavailable provider/worker, enabled ordinary global delivery, or failed process gates remain false/cancelled by existing control logic.
- Ordinary global-on dispatch is unchanged: `intent()` still selects `ordinary` only when global delivery is requested/effective and readiness is true; the existing ordinary authorization test remains relevant.
- Direct callers of `status_from_readiness()` retain its optional `configured_content_sid=None` signature and current fail-closed behavior. No schema, API, migration, deployment configuration, operator script, or rollback command changes are needed.
- `current_delivery_status()` and the admin readiness route already forward the configured SID, so they are not part of this correction.

## Rollback

Revert the single worker argument and its regression test. The worker then returns to the prior fail-closed behavior: it cannot consume activation jobs because readiness remains incapable. This rollback does not change persisted delivery settings, jobs, authorizations, provider state, or operator scripts.

## Constraints preserved

- Do not touch production, provider state, deployment configuration, or `deploy/runbooks/**`.
- Do not modify existing untracked artifacts or `.codegraph/**`.
- Do not refactor readiness calculation, activation authorization, worker leasing, or ordinary dispatch.
- The existing official Content transport and all activation authorization/revocation safeguards remain the only execution path.
