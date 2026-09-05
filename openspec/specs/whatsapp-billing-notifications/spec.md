# whatsapp-billing-notifications Specification

## Purpose
Deliver consented, auditable billing WhatsApp notifications from immutable publication snapshots.

## Requirements
### Requirement: Consent and confirmation
The system MUST require evidenced consent for a verified E.164 recipient and MUST never infer consent from a phone value. Preview MUST mask numbers and bind confirmation to a digest of publication, recipients, consent revisions, channels, approved Content SIDs, and PDF identities.
#### Scenario: Confirm eligible batch
- GIVEN current consent and verified E.164 data
- WHEN an administrator confirms the displayed digest
- THEN the system MUST accept only an identical, current digest and create the batch
#### Scenario: Stale or unsafe confirmation
- GIVEN consent, recipient, readiness, or media data changed
- WHEN the old digest is confirmed
- THEN the system MUST reject it and create no jobs

### Requirement: Fail-closed readiness and durable dispatch
Production WhatsApp MUST be unavailable unless sender status is exactly `ONLINE`, every billing Content SID is currently Approved Utility, callbacks/signing and canonical URLs are configured, and credentials are valid. Each recipient MUST have one durable intent with exactly-once claim semantics.
#### Scenario: Ready dispatch
- GIVEN readiness passes and confirmation succeeds
- WHEN the worker processes the batch
- THEN one immutable intent per recipient MUST be leased and dispatched with an auditable status
#### Scenario: Not ready or ambiguous
- GIVEN readiness fails or provider outcome is unknown
- WHEN dispatch is attempted
- THEN WhatsApp MUST fail closed; no email fallback or duplicate create is allowed

### Requirement: PDF media delivery
Each PDF MUST derive from the immutable snapshot and be served through an opaque expiring token, `application/pdf`, no-store headers, and a size of at most 15,000,000 bytes. The endpoint MUST support repeated `HEAD` and `GET` until expiry/revocation.
#### Scenario: Valid fetch
- GIVEN an unexpired bound token
- WHEN Twilio performs repeated HEAD/GET requests
- THEN each response MUST expose correct MIME and length and return the PDF
#### Scenario: Invalid media
- GIVEN an expired, revoked, oversized, or unbound artifact
- WHEN media is requested
- THEN the endpoint MUST reject it without exposing billing data

### Requirement: Signed monotonic callbacks and reconciliation
Status/inbound callbacks MUST validate signature, canonical URL, and raw parameters before mutation; events MUST be idempotent and state projection monotonic. SIDs MUST accept `SM` and `MM` forms. Unknown outcomes MUST remain WhatsApp-only until bounded reconciliation.
#### Scenario: Out-of-order callbacks
- GIVEN valid duplicate callbacks arriving out of order
- WHEN callbacks are processed
- THEN events MUST be deduplicated and terminal state MUST NOT regress
#### Scenario: STOP or unknown sender
- GIVEN a validated STOP event
- WHEN it is processed
- THEN opt-out MUST be recorded and unsent WhatsApp jobs cancelled without a duplicate reply
- GIVEN an unknown sender
- THEN no account linkage or fallback send MUST occur

### Requirement: Channel policy and operations
The system MUST classify recipients as WhatsApp, email alternative, blocked, or skipped; email MAY be selected only for absent consent or definite terminal WhatsApp failure. Ambiguous outcomes MUST NOT select email. Admins MUST see durable delivery status, and an official-WhatsApp feature flag MUST support rollback by stopping workers, cancelling unleased jobs, and revoking media tokens.
#### Scenario: Definite failure and rollback
- GIVEN a verified terminal failed/undelivered status
- WHEN status is projected
- THEN the recipient MAY receive the defined email alternative
- GIVEN the feature flag is disabled
- THEN no new WhatsApp jobs MUST dispatch and audits MUST remain preserved
