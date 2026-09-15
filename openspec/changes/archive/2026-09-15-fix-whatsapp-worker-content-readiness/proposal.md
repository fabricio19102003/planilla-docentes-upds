# Proposal: Fix WhatsApp Worker Content Readiness

## Intent

Correct the official WhatsApp worker's readiness wiring so a valid configured Twilio Content SID participates in activation capability evaluation.

Today, the worker omits `configured_content_sid` when it calls `status_from_readiness()`. The readiness service therefore receives its fail-closed default of `None` and reports activation as incapable even when the worker has a valid `HX` Content SID and every other prerequisite passes. This incorrectly causes released activation work to be rolled back instead of becoming claimable.

This change is a minimal fail-closed defect correction. It does not broaden activation policy, enable ordinary delivery, or authorize any production action.

## Scope

### In Scope

- Forward `settings.TWILIO_OFFICIAL_CONTENT_SID` from the official WhatsApp worker to its existing `status_from_readiness()` call.
- Add a focused worker regression test proving that:
  - the configured SID reaches the readiness boundary; and
  - when global delivery is off and readiness reports activation capable, the worker selects the `activation_test` claim intent.
- Preserve validation in `status_from_readiness()`, including rejection of missing, malformed, or non-`HX` Content SIDs.
- Run the focused runner and delivery-control test suites.

### Out of Scope

- Any production send, provider-state mutation, deployment change, configuration change, or operator action.
- Changes under `deploy/runbooks/**`.
- Enabling ordinary, batch, or global WhatsApp delivery.
- Refactoring readiness calculation, activation authorization, worker leasing, transport, callbacks, reconciliation, or ordinary dispatch.
- Schema, API, migration, frontend, or persisted-data changes.
- Changing the optional `configured_content_sid=None` compatibility behavior for other callers.

## Proposed Approach

1. Add a regression test following the existing mocked runner-cycle pattern. Configure both activation gates, a valid 32-byte recipient HMAC key, and a valid `HX` Content SID; isolate database and provider I/O; capture readiness arguments and the worker's claim intent; terminate the loop with `KeyboardInterrupt`.
2. Add `configured_content_sid=settings.TWILIO_OFFICIAL_CONTENT_SID` to the worker's existing `status_from_readiness()` keyword arguments.
3. Verify the runner behavior together with the existing delivery-control validation tests. No broader implementation changes are expected unless focused verification exposes direct coupling.

## Affected Areas

| Area | Expected change |
|---|---|
| `backend/app/workers/official_whatsapp_runner.py` | Forward the configured Twilio Content SID into the existing readiness projection. |
| `backend/tests/services/test_official_whatsapp_runner.py` | Add one focused regression covering SID forwarding and global-off activation claim intent. |
| `backend/app/services/whatsapp_delivery_control.py` | No implementation change; existing SID validation remains authoritative and is covered by focused verification. |

The expected product-source surface is two modified files and is materially below the 400 changed-line review budget. Under `ask-on-risk`, implementation must pause for a delivery decision only if discovered coupling threatens that budget or the confirmed narrow scope.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| An invalid SID accidentally makes activation capable | Continue using `_configured_content_sid_is_valid()` through `status_from_readiness()`; forward configuration without bypassing validation. |
| The correction unintentionally enables ordinary delivery | Keep global-delivery checks and ordinary claim selection unchanged; test only the existing global-off `activation_test` branch. |
| The test proves argument forwarding but misses behavior | Assert both the exact forwarded SID and that the captured `claim_intent()` returns `activation_test`. |
| Mocked execution touches provider or database state | Patch runtime, session, heartbeat, sweep, and worker boundaries so the test performs no external or production I/O. |
| Scope expands into readiness or authorization redesign | Restrict implementation to the worker argument and focused runner regression; pause if additional production changes appear necessary. |

## Rollback

Revert the worker argument and its regression test. The worker will return to the previous fail-closed behavior in which activation readiness remains incapable at this call site and activation jobs cannot be claimed. Reversion does not alter persisted delivery settings, jobs, authorizations, provider state, deployment configuration, or operator scripts.

## Success Criteria

- [ ] The worker passes the exact configured `TWILIO_OFFICIAL_CONTENT_SID` to `status_from_readiness()`.
- [ ] With ordinary global delivery disabled, both activation gates enabled, a valid HMAC key, a valid configured `HX` SID, and capable readiness, the worker selects `activation_test` as its claim intent.
- [ ] Missing, malformed, or non-`HX` Content SIDs remain fail-closed and incapable through existing readiness validation.
- [ ] Ordinary global-on dispatch selection and all existing authorization, leasing, transport, and rollback safeguards remain unchanged.
- [ ] No production/operator action, provider mutation, deployment/configuration change, schema/API migration, or runbook change is introduced.
- [ ] `cd backend && venv/bin/python -m pytest -q tests/services/test_official_whatsapp_runner.py tests/services/test_whatsapp_delivery_control.py` passes, using the repository-local Python environment if `backend/venv` is unavailable.
- [ ] The implementation remains within the 400 changed-line review budget; otherwise `ask-on-risk` pauses for an explicit delivery decision.
