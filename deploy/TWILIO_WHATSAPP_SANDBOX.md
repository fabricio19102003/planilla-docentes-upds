# Twilio WhatsApp Sandbox

This release supports **Sandbox mode only**. It cannot be converted to a
production sender by replacing the sender number. Production onboarding needs
a separate configuration contract, approved templates, persisted teacher
opt-in, and a verified Twilio webhook signature policy.

## Runtime configuration

Keep all values in the private production environment file:

- `WHATSAPP_ENABLED=true`
- `WHATSAPP_MODE=sandbox`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_API_KEY_SID`
- `TWILIO_API_KEY_SECRET`
- `TWILIO_WHATSAPP_SANDBOX_FROM=+14155238886`
- `TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT=<joined E.164 test number>`

The API authenticates with the API Key SID and Secret. The master Auth Token is
not used. Never place credentials or the test phone number in source, shell
history, deployment logs, or committed environment examples.

## Delivery and fallback contract

- With WhatsApp disabled, the existing Resend email path remains active.
- With Sandbox enabled, one representative billing notification is sent to the
  configured joined test recipient; the remaining batch is skipped deliberately.
- If the Sandbox is unavailable, invalid, not joined/configured, or Twilio
  rejects the request, only that representative notification falls back to
  Resend. This prevents a test configuration error from emailing an entire batch.
- Every provider/channel claim is written before the external call. Completed,
  failed, and ambiguous pending claims are not automatically retried, preventing
  duplicate notifications after operator retries.
- Audit rows never store destination addresses, message bodies, credentials, or
  provider response bodies.

Twilio acceptance records the provider message SID and means only that Twilio
queued the message. Delivery/read states are not yet ingested. A future webhook
must verify Twilio signatures before updating those states.
