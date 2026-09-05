# SDD Pre-Proposal State: Official WhatsApp Billing Notifications

```yaml
schema: gentle-ai.sdd-preproposal/v1
change: official-whatsapp-billing-notifications
revision: 2
artifact_store: hybrid
proposal_ready: true
exploration_outcome: ready_for_proposal_after_selected_research
research_selection: targeted_official_twilio_meta
research_classes:
  - documentation
  - open-web
research_admission: admitted
research_status: done
product_decisions: confirmed
```

## Exploration Reference

- OpenSpec: `openspec/changes/official-whatsapp-billing-notifications/exploration.md`
- Engram: `sdd/official-whatsapp-billing-notifications/explore`
- Outcome: the billing-scoped PostgreSQL transactional outbox approach is recommended; selected provider research was required before proposal.

## Research Request

Validate only current official Twilio/Meta contracts for Content API and `twilio/media`, Utility approval/category lifecycle, sender `ONLINE` readiness, opt-in/opt-out, the 24-hour window, proxy-safe webhook signature validation, outbound status/callback retry and ordering, inbound opt-out, `SM|MM` Message SIDs, PDF media constraints, Restricted API Keys, throughput/quality/recipient limits, and volatile pricing.

## Admission and Outcome

- Capability declaration: `{"schema":"gentle-ai.sdd-research-capability/v1","grants":{"documentation":true,"open-web":true}}`
- Observed exact grants: `{"documentation":true,"open-web":true}`
- Admission: admitted.
- Outcome: `done`; every selected question has mapped official evidence or an explicit bounded uncertainty.
- Evidence boundary: Meta Developer pages returned HTTP 429, so validated claims use current official Twilio product and Help Center sources describing the Twilio-to-Meta integration contract. Manual Meta policy revalidation remains a deployment control, not a proposal blocker.

## Evidence References

- OpenSpec: `openspec/changes/official-whatsapp-billing-notifications/research.md`, `gentle-ai.sdd-research/v1`, revision 2.
- Engram: `sdd/official-whatsapp-billing-notifications/research`, `gentle-ai.sdd-research/v1`, revision 2.
- Hybrid requirement: both stores contain identical canonical bytes for the research and pre-proposal artifacts.

## Confirmed Product Decisions

- Scope is billing-only Utility notifications; general notices and Marketing are deferred.
- WhatsApp requires explicit, scoped, evidenced consent; phone presence or verification never implies consent.
- Admins receive a masked recipient/channel preview and must confirm a digest bound to immutable publication, recipient, consent, template, and media facts.
- Delivery uses a durable transactional outbox with leases, bounded retries, callback ingestion, and reconciliation.
- Billing PDFs come only from immutable publication snapshots and are fetched through expiring opaque URLs backed by private storage.
- Email is used only when WhatsApp consent is absent or a definite terminal WhatsApp failure is recorded; ambiguous provider outcomes never trigger email.
- Production fails closed unless Senders API v2 reports the configured sender exactly `ONLINE` and every configured billing Content SID is currently Approved Utility.
- Status/callback projection is idempotent and monotonic because callbacks may retry and arrive out of order.
- Billing PDF output is capped at 15,000,000 bytes because current official Twilio pages conflict between 16 MB and 20 MB.
- Runtime credentials use least-privilege Restricted API Key permissions, while the Account Auth Token is stored separately for Twilio webhook signature verification.
- Pricing is dated operational evidence only and is never encoded into channel-selection or billing-domain rules.

## Confirmed Provider Constraints for Proposal

1. Send a Document-header `twilio/media` Content template using WhatsApp E.164 From/To, `ContentSid`, JSON `ContentVariables`, and a public `StatusCallback`; do not combine `Body`/message-level `MediaUrl` with the template.
2. Validate every inbound/status webhook before mutation with Twilio's SDK, the exact configured canonical public URL plus query, all raw form parameters, `X-Twilio-Signature`, and the Account Auth Token.
3. Accept Message SIDs matching `^(SM|MM)[0-9a-fA-F]{32}$`.
4. Serve `application/pdf` through repeatable `HEAD` and `GET`, correct `Content-Length`, best-effort compliant `Content-Disposition`, and no session-cookie dependency while the opaque token is valid.
5. Observe sender quality, portfolio messaging limit, and throughput; default media throughput is 80 MPS and new portfolios may be limited to 250 unique business-initiated recipients per moving 24 hours.
6. Configure WhatsApp Advanced Opt-Out or an equivalent verified operational control; persist `OptOutType=STOP` immediately and cancel unsent WhatsApp jobs without sending a duplicate confirmation.

## Gate

Selected research is admitted and `done`, evidence references are valid, product decisions are confirmed, and canonical hybrid bytes were retained for readback. The change is ready for `sdd-propose`; the proposer must not reopen product discovery or infer additional consent.