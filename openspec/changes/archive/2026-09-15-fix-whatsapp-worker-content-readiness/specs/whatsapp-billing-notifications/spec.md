# Delta for WhatsApp Billing Notifications

## ADDED Requirements

### Requirement: Fail-closed worker activation content readiness

The official WhatsApp worker MUST forward the configured official Content SID to the existing readiness evaluation before selecting a claim intent. When ordinary global delivery is disabled and all existing activation prerequisites, including a valid `HX` Content SID, are satisfied, the worker MUST select only the bounded `activation_test` claim intent. Missing, malformed, or non-`HX` Content SIDs MUST remain activation-incapable and MUST NOT cause the worker to select an activation claim intent or broaden ordinary delivery.

#### Scenario: Valid Content SID enables bounded activation intent

- GIVEN ordinary global WhatsApp delivery is disabled
- AND both existing activation gates, the recipient-HMAC prerequisite, and all other readiness prerequisites pass
- AND the configured official Content SID is valid and has the `HX` prefix
- WHEN the official WhatsApp worker evaluates readiness for a cycle
- THEN the worker MUST forward that exact configured Content SID to readiness evaluation
- AND the worker MUST select `activation_test` as its claim intent
- AND the worker MUST NOT select ordinary delivery

#### Scenario: Invalid or missing Content SID remains fail-closed

- GIVEN ordinary global WhatsApp delivery is disabled
- AND a configured official Content SID is missing, malformed, or does not have the `HX` prefix
- WHEN the official WhatsApp worker evaluates readiness for a cycle
- THEN readiness MUST report activation as incapable
- AND the worker MUST NOT select an activation claim intent
- AND the worker MUST NOT enable or select ordinary delivery

#### Scenario: Regression coverage isolates provider I/O

- GIVEN regression coverage exercises one official WhatsApp worker cycle for valid and invalid Content-SID readiness outcomes
- WHEN the coverage evaluates forwarded readiness arguments and claim intent
- THEN the coverage MUST perform no provider call
- AND the coverage MUST verify the bounded activation intent without sending a provider message
