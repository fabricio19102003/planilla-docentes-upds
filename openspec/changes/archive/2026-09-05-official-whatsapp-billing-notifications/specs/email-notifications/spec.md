# Delta for email-notifications

## MODIFIED Requirements
### Requirement: Successful outbound delivery attempt
When outbound email is enabled and recipient data is eligible, the system MUST attempt one billing-publication email per eligible recipient after publication data is successfully committed, but billing email selection MUST be limited to recipients without WhatsApp consent or with a definite terminal WhatsApp failure.
(Previously: email was attempted for every eligible recipient.)
#### Scenario: Successful send attempt
- GIVEN billing publication has been committed successfully
- AND email notifications are enabled with valid provider configuration
- AND the recipient lacks WhatsApp consent or has a definite terminal WhatsApp failure
- WHEN outbound email processing runs
- THEN the system MUST attempt one billing-publication email
- AND the system MUST report send outcomes as operational results
#### Scenario: Ambiguous WhatsApp outcome
- GIVEN WhatsApp dispatch has an unknown or pending outcome
- WHEN outbound email processing runs
- THEN the system MUST NOT attempt email

## ADDED Requirements
### Requirement: WhatsApp fallback boundary
Email MUST NOT be used for WhatsApp readiness failure, stale confirmation, opt-out, blocked recipients, or ambiguous provider outcomes.
#### Scenario: No consent alternative
- GIVEN a recipient has no evidenced WhatsApp consent and a usable email
- WHEN the confirmed billing batch is processed
- THEN the system MAY attempt the billing email
#### Scenario: Definite terminal alternative
- GIVEN a recipient has a verified terminal WhatsApp failure and a usable email
- WHEN status is finalized
- THEN the system MAY attempt the billing email
