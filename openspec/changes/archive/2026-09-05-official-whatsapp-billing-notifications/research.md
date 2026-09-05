# SDD Research: Official WhatsApp Billing Notifications

```yaml
schema: gentle-ai.sdd-research/v1
change: official-whatsapp-billing-notifications
revision: 2
outcome: done
artifact_store: hybrid
accessed_at: 2026-09-02T13:39:47Z
freshness_cutoff: 2026-09-02
```

## Admission

- Requested evidence classes: `documentation`, `open-web`
- Capability declaration: `{"schema":"gentle-ai.sdd-research-capability/v1","grants":{"documentation":true,"open-web":true}}`
- Admitted schema: `gentle-ai.sdd-research-capability/v1`
- Observed exact grants: `{"documentation":true,"open-web":true}`
- Admission result: admitted
- Source policy: current first-party Twilio and Meta sources only. Meta Developer pages returned HTTP 429 during collection, so validated claims rely on current official Twilio product documentation and Help Center material that describes the Twilio-to-Meta contract. No third-party source was admitted.

## Questions

1. What are the production `twilio/media`, `ContentSid`, `ContentVariables`, sender, recipient, and callback request contracts?
2. What makes a billing template Utility, and what approval/category lifecycle must readiness observe?
3. How can production verify sender `ONLINE` readiness?
4. What opt-in, opt-out, and 24-hour customer-service-window rules apply?
5. How must webhook signatures be validated behind Nginx or another proxy?
6. What are status callback retry, duplication, ordering, status, and reconciliation semantics?
7. How should inbound opt-out events be handled?
8. Which Message SID forms are valid?
9. What PDF MIME, size, fetch, and filename constraints apply?
10. Which Restricted API Key permissions are required?
11. What throughput, quality, and unique-recipient limits constrain rollout?
12. Which current pricing facts belong in operations rather than code?

## Sources

| ID | Class | Title | Publisher | Direct official URL | Accessed | Bounded excerpt |
|---|---|---|---|---|---|---|
| S1 | documentation | `twilio/media` | Twilio | https://www.twilio.com/docs/content/twilio-media | 2026-09-02 | “Variables are only supported after the domain.” |
| S2 | documentation | Content API Quickstart | Twilio | https://www.twilio.com/docs/content/create-and-send-your-first-content-api-template | 2026-09-02 | “ContentVariables” supplies placeholder substitutions. |
| S3 | documentation | Messages resource | Twilio | https://www.twilio.com/docs/messaging/api/message-resource | 2026-09-02 | Message SIDs match `SM` or `MM` plus 32 hexadecimal characters. |
| S4 | documentation | Message template approvals and statuses | Twilio | https://www.twilio.com/docs/whatsapp/tutorial/message-template-approvals-statuses | 2026-09-02 | Approved templates can later become Paused or Disabled. |
| S5 | documentation | Senders API - WhatsApp | Twilio | https://www.twilio.com/docs/whatsapp/api/senders | 2026-09-02 | Sender status includes `ONLINE`, `OFFLINE`, and onboarding states. |
| S6 | documentation | Overview of WhatsApp Business Platform with Twilio | Twilio | https://www.twilio.com/docs/whatsapp/api | 2026-09-02 | The customer service window lasts 24 hours after the latest inbound message. |
| S7 | documentation | Rules and Best Practices for WhatsApp Messaging | Twilio Help Center | https://help.twilio.com/articles/360017773294-Rules-and-Best-Practices-for-WhatsApp-Messaging-on-Twilio | 2026-09-02 | Production opt-in must be active, user-triggered, and specific about message types. |
| S8 | documentation | Advanced Opt-Out | Twilio | https://www.twilio.com/docs/messaging/tutorials/advanced-opt-out | 2026-09-02 | Matching inbound keywords produce `OptOutType` values such as `STOP`. |
| S9 | documentation | Webhooks security | Twilio | https://www.twilio.com/docs/usage/webhooks/webhooks-security | 2026-09-02 | Validation uses the exact URL, all parameters, signature header, and Auth Token. |
| S10 | documentation | Webhook connection overrides | Twilio | https://www.twilio.com/docs/usage/webhooks/webhooks-connection-overrides | 2026-09-02 | Retry attempts expose `I-Twilio-Idempotency-Token`. |
| S11 | documentation | Track outbound message status | Twilio | https://www.twilio.com/docs/messaging/guides/track-outbound-message-status | 2026-09-02 | Callback requests are not guaranteed to arrive in send order. |
| S12 | documentation | Outbound status callback transitions | Twilio | https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks | 2026-09-02 | Successful delivery progresses through sent and delivered, optionally read. |
| S13 | documentation | Delivery status logging best practices | Twilio | https://www.twilio.com/docs/messaging/guides/outbound-message-logging | 2026-09-02 | Persist the Message SID and reconcile missing terminal callbacks by polling. |
| S14 | documentation | Accepted content types for media | Twilio | https://www.twilio.com/docs/messaging/guides/accepted-mime-types | 2026-09-02 | Twilio may issue both `GET` and `HEAD` to validate media. |
| S15 | documentation | WhatsApp media guidance | Twilio | https://www.twilio.com/docs/whatsapp/guidance-whatsapp-media-messages | 2026-09-02 | `application/pdf` is accepted for WhatsApp documents. |
| S16 | documentation | WhatsApp media Help Center guide | Twilio Help Center | https://help.twilio.com/articles/360017961894 | 2026-09-02 | Template documents are PDF and document media is limited to 16 MB. |
| S17 | documentation | Restricted API Keys | Twilio | https://www.twilio.com/docs/iam/api-keys/restricted-api-keys | 2026-09-02 | Restricted keys grant fine-grained endpoint permissions, with at most 100 permissions. |
| S18 | documentation | Restricted Messaging permissions | Twilio | https://docs-resources.prod.twilio.com/documents/Twilio_Restricted_API_Keys_Permissions_-_Messaging_Permissions.pdf | 2026-09-02 | Messaging permissions separately cover message create/read, senders, and Content templates. |
| S19 | documentation | WhatsApp best practices and FAQs | Twilio | https://www.twilio.com/docs/whatsapp/best-practices-and-faqs | 2026-09-02 | Default outbound throughput is 80 messages per second per sender. |
| S20 | documentation | Sender limits and quality rating | Twilio Help Center | https://help.twilio.com/hc/en-us/articles/360024008153-WhatsApp-Sender-Message-Limits-and-Quality-Rating | 2026-09-02 | New portfolios start at 250 unique recipients per moving 24 hours. |
| S21 | operations | WhatsApp Messaging Pricing | Twilio | https://www.twilio.com/en-us/whatsapp/pricing | 2026-09-02 | Pricing combines Twilio per-message charges with Meta template charges. |
| S22 | operations | WhatsApp pricing changes effective October 2026 | Twilio Help Center | https://help.twilio.com/articles/53100480177819 | 2026-09-02 | Meta pricing changes again on 2026-10-01. |

## Validated Claims and Implementation Implications

### C1 — Content API and production send payload

A `twilio/media` Content resource uses `friendly_name`, `language`, sample `variables`, and `types["twilio/media"]` containing a `body` and required `media` string array. A variable media URL is allowed only after the domain; the combined sample URL must be public, resolvable, and include the file suffix. WhatsApp approves the media header as exactly one of Image, Video, or Document, and that approved header type cannot later be changed for the same template. [S1]

Production send uses `POST /2010-04-01/Accounts/{AccountSid}/Messages.json` with form fields `From=whatsapp:<E.164>`, `To=whatsapp:<E.164>`, `ContentSid=HX...`, optional JSON-string `ContentVariables`, and `StatusCallback=<public URL>`. `ContentSid` is an HX SID and replaces `Body`/`MediaUrl` as the content selector; `ContentVariables` is valid only with `ContentSid`. Twilio's outside-window error guidance explicitly says to remove `Body` and `MediaUrl` when sending a Content template. [S2, S3, S6]

Implementation implication: create one approved Document-header `twilio/media` Utility Content SID for each immutable billing layout/language variant. Put the secure PDF URL in the template media variable, not in the message-level `MediaUrl`, and serialize `ContentVariables` as JSON with keys matching the approved placeholders. Readiness must verify the configured SID pattern, exact variant mapping, and live approval state before confirmation.

### C2 — Utility category and approval lifecycle

Utility templates must relate to a specific agreed or user-initiated transaction and confirm, suspend, or change that transaction/account/subscription; Twilio's current pricing guidance expressly lists billing reminders and billing/payment notifications as Utility examples. Mixed Utility and Marketing content is classified as Marketing, and Meta may override the submitted category. [S4, S6, S21]

The Content Approval endpoint accepts category `UTILITY`. Its base lifecycle exposes `received`, `pending`, `approved`, and `rejected`; broader WhatsApp operational lifecycle also includes `paused` and `disabled` following negative feedback or policy enforcement. Twilio Event Streams can report status and category updates, but polling the Content approval resource is sufficient for a fail-closed readiness check. [S2, S4]

Implementation implication: only `approved` plus category `UTILITY` is send-ready. Treat received, pending, rejected, paused, disabled, missing, fetch-error, or recategorized Marketing as not ready. Keep notification copy strictly billing-specific and non-promotional.

### C3 — Sender readiness and observability

The WhatsApp Senders API v2 is the current endpoint (`https://messaging.twilio.com/v2/Channels/Senders`). Sender status values include `CREATING`, `ONLINE`, `OFFLINE`, `PENDING_VERIFICATION`, `VERIFYING`, `ONLINE:UPDATING`, `TWILIO_REVIEW`, `DRAFT`, and `STUBBED`; the resource also exposes `qualityRating`, `messagingLimit`, and offline reasons. Senders API v1 reached its documented deprecation date on 2026-09-01, so new code must use v2. [S5]

Implementation implication: production confirmation and worker dispatch must fail closed unless the exact configured sender resource resolves through v2 and status equals `ONLINE`. Cache only briefly for display; re-check at confirmation and dispatch. Surface quality, messaging limit, and sanitized offline reason for operators without treating them as consent or delivery evidence.

### C4 — Opt-in, opt-out, and the 24-hour window

Production WhatsApp requires an active opt-in caused by a user action, clear disclosure of the message types, and retained proof. A populated or verified phone number is not opt-in. A user's inbound message opens or refreshes a 24-hour customer service window; free-form messages are allowed inside it, while business-initiated messages outside it require an approved template. Billing delivery should still use the approved template consistently because this product decision avoids window-dependent content behavior. [S6, S7]

Twilio's default account-wide SMS keyword behavior does not automatically apply to WhatsApp unless Advanced Opt-Out is configured on a Messaging Service. Advanced Opt-Out supports WhatsApp senders, matches keywords case-insensitively, blocks later sends, and adds `OptOutType=STOP|START|HELP` to the inbound webhook. When Twilio already handled the keyword, the application should not send a second confirmation. [S7, S8]

Implementation implication: maintain application consent evidence independently of provider blocking. On a validated inbound `OptOutType=STOP`, persist opt-out immediately, cancel unsent WhatsApp jobs, and acknowledge the webhook without another outbound reply. Also apply a conservative application keyword fallback for normalized STOP-like bodies only when `OptOutType` is absent, because Advanced Opt-Out configuration can drift; never link an unknown sender to an account.

### C5 — Webhook signature validation behind Nginx/proxies

Twilio signs requests in `X-Twilio-Signature` using HMAC-SHA1 with the Twilio Account Auth Token. Form webhooks require the exact URL Twilio used plus the complete form parameter set. Twilio can add parameters without notice and recommends its SDK validator rather than a custom implementation. URL fragments used for connection overrides are excluded from signature calculation. [S9, S10]

Implementation implication: configure an immutable canonical public webhook base URL matching the URL registered/sent to Twilio, append the known route and actual query string, and validate raw form fields with the Twilio SDK and the Account Auth Token before any mutation. Do not reconstruct the signed URL from untrusted `Host` or arbitrary forwarded headers. Nginx may forward scheme/host for normal routing, but signature code must use the configured external HTTPS origin; reject mismatches and missing signatures. A Restricted API Key secret used for outbound REST authentication does not replace the Account Auth Token for webhook verification. This proxy rule is an engineering inference from Twilio's exact-URL contract. [S9]

### C6 — Outbound acceptance, callbacks, retries, ordering, and reconciliation

A successful create response returns a Message SID and an initial state, but `sent` means the upstream provider accepted the message, not that the recipient received it. Later states include `failed`, `delivered`, `undelivered`, and WhatsApp `read`. Status callbacks are `application/x-www-form-urlencoded` POSTs carrying `MessageSid`, `MessageStatus`, and optional `ErrorCode`; WhatsApp may additionally include `EventType=READ`. Twilio warns that callbacks can arrive out of order. [S3, S11, S12]

Webhook connection overrides can configure retry count zero through five and retry classes (`4xx`, `5xx`, connect timeout, read timeout, or all); the default retry policy is connect-timeout only with one retry. Retry attempts can be distinguished using `I-Twilio-Idempotency-Token`. [S10]

Implementation implication: preserve every validated callback as an idempotent event keyed by a stable payload fingerprint plus Message SID/status and, when present, the Twilio idempotency token. Project current state using a monotonic domain precedence, never arrival order; terminal delivery/read cannot regress to queued/sent. Treat `failed` and `undelivered` as definite terminal WhatsApp failures only after verifying the Message SID belongs to the job. Treat provider timeouts or lost create responses as ambiguous: do not send email or issue an unbounded duplicate WhatsApp create. Reconcile by known SID fetch and bounded operational lookup. Twilio recommends polling after 12 hours without delivered/undelivered and daily reconciliation for missed events. [S11, S13]

### C7 — Message SID contract

The Messages resource documents Message SID as `SID<SM|MM>` with pattern `^(SM|MM)[0-9a-fA-F]{32}$`. Code, database constraints, callback parsing, and reconciliation must accept both prefixes. Do not hard-code `SM` only. [S3]

### C8 — PDF media contract and contradictory size limits

`application/pdf` is accepted for WhatsApp. Twilio may issue both `HEAD` and `GET` to the media URL and rejects a mismatched `Content-Type`. The current accepted-MIME page says WhatsApp allows 20 MB total, recommends `Content-Disposition: inline; filename="..."`, and limits filenames to 20 characters using ASCII letters, digits, hyphen, underscore, and period. [S14]

However, the current `twilio/media` page, WhatsApp overview/error pages, and Help Center media guide still state a 16 MB WhatsApp/template limit, while the general accepted-MIME and media-guidance pages state 20 MB. The message-resource generic `MediaUrl` description also carries older MMS-oriented 500 KB/5 MB language that is not the Content-template channel contract. [S1, S3, S14, S15, S16]

Conservative decision: for outbound PDF Content templates, enforce a product cap of 15,000,000 bytes and `application/pdf`, below both conflicting 16 MB and 20 MB statements. Use a filename at most 20 characters in the documented ASCII set and return `Content-Disposition: inline`. The secure token endpoint must support repeated `HEAD` and `GET` until expiry, return the real content length/type, avoid single-use semantics, and remain publicly fetchable without session cookies while the opaque token remains valid. Twilio says document filenames cannot always be set/captioned consistently in WhatsApp, so filename is best-effort presentation metadata, not a delivery guarantee. [S14, S15]

### C9 — Restricted API Key permissions and secret separation

Restricted keys support fine-grained permissions and a maximum of 100 permissions. The current Messaging permission matrix includes `twilio/messaging/messages/create`, `twilio/messaging/messages/read`, `twilio/messaging/whatsapp-senders/read`, `twilio/messaging/content-templates/read`, and optional list permissions for each resource family. Content template creation/approval and sender mutation are separately grantable. [S17, S18]

Implementation implication: the runtime sender key needs only message create, message read for reconciliation, sender read for readiness, and Content-template read/list needed to verify approval/category. Do not grant sender create/update/delete, Content create/update/delete/approval, message delete/update, or pricing access to the application worker. Store the Restricted Key SID/secret separately from the Account Auth Token; the latter is still required for webhook signatures. Whether `content-templates/read` alone returns approval data must be verified against the account during deployment; if the approval fetch is covered only by the documented template list permission, add that permission narrowly and record the result.

### C10 — Throughput, quality, and recipient limits

Default outbound throughput is 80 messages per second per WhatsApp sender for text and media. Text-only throughput can be raised by approval, but media throughput cannot exceed 80 MPS. Excess submissions queue; Twilio documents a four-hour maximum queue horizon. Large or uniquely generated media and slow media URLs can reduce effective throughput. [S19]

Business-initiated unique-recipient limits are separate from throughput and, since 2025-10-07, apply at the Meta Business Portfolio level shared across its senders. New portfolios start at 250 unique recipients in a moving 24-hour period, with documented tiers of 2,000, 10,000, 100,000, and unlimited. Quality rating is driven by recent user feedback such as blocks/reports and influences scaling. Sender API/WhatsApp Manager exposes current quality and messaging limit. [S5, S20]

Implementation implication: the outbox must throttle below observed sender capacity, honor the portfolio recipient limit, and display a forecast before confirmation. A small billing cohort must not assume the account tier; readiness should fetch current values and fail closed when unavailable for a batch that could exceed the last verified capacity.

### C11 — Pricing is volatile operational evidence, not a coded rule

As accessed on 2026-09-02, Twilio advertises a per-message WhatsApp fee plus Meta per-template charges, and Utility templates inside an open customer-service window currently avoid the Meta Utility fee. Twilio also announces that Meta will begin charging Utility templates inside the window and Service messages on 2026-10-01. Rates vary by destination/category/volume and may change without notice. [S21, S22]

Implementation implication: do not encode prices or cost-based channel selection in application logic. Operators must verify the live Twilio calculator/rate card before production launch and budget reviews. Persist provider price observations only as dated operational metadata if needed.

## Mapped Answers

| Question | Evidence answer | Sources |
|---|---|---|
| Q1 | Use an approved Document-header `twilio/media` HX Content SID; send WhatsApp E.164 From/To, JSON ContentVariables, and StatusCallback; do not combine message-level Body/MediaUrl with the template. | S1-S3 |
| Q2 | Billing/payment reminders can be Utility, but mixed promotional content becomes Marketing; send only when currently Approved and Utility, not paused/disabled/recategorized. | S2, S4, S6, S21 |
| Q3 | Query Senders API v2 and require exact `ONLINE`; observe quality, messaging limit, and offline reasons. | S5 |
| Q4 | Store explicit user-triggered scoped consent; 24 hours follows the latest inbound message; approved templates are required outside it; Advanced Opt-Out supplies OptOutType for WhatsApp. | S6-S8 |
| Q5 | Validate `X-Twilio-Signature` with Account Auth Token, exact canonical public URL, and all form parameters before mutation; do not trust proxy Host reconstruction. | S9, S10 |
| Q6 | Persist SID and callbacks, accept out-of-order/retried callbacks idempotently, use monotonic status projection, and reconcile missing terminals by fetch/poll. | S3, S10-S13 |
| Q7 | On validated STOP, persist opt-out and cancel queued WhatsApp work; do not duplicate Twilio's Advanced Opt-Out confirmation. | S8 |
| Q8 | Accept both `SM` and `MM` plus 32 hexadecimal characters. | S3 |
| Q9 | PDF is accepted; support HEAD/GET, exact MIME, constrained filename, and repeated fetch. Official limits conflict at 16/20 MB, so cap at 15,000,000 bytes. | S1, S14-S16 |
| Q10 | Narrow runtime key to message create/read, sender read, and Content read/list; keep Auth Token separately for webhook verification. | S9, S17, S18 |
| Q11 | Default sender throughput is 80 MPS; portfolio recipient tiers start at 250 unique users/24h and quality governs scaling. | S5, S19, S20 |
| Q12 | Prices and a 2026-10-01 policy change are dated operations evidence only; never hard-code them. | S21, S22 |

## Contradictions and Conservative Resolution

1. Official Twilio pages disagree on the WhatsApp document/media ceiling: 16 MB in `twilio/media`, Help Center, and error/overview material versus 20 MB in accepted-MIME and media-guidance pages. Enforce 15,000,000 bytes for billing PDFs until Twilio resolves the contract. [S1, S14-S16]
2. The Content approval endpoint documents received/pending/approved/rejected, while broader template operations also expose paused/disabled and category changes. Readiness must combine approval and current operational state and accept only Approved Utility. [S2, S4]
3. Default WhatsApp keyword handling is not the same as Messaging Service Advanced Opt-Out. Require Advanced Opt-Out as an operational prerequisite and also persist application consent/opt-out state. [S7, S8]
4. Current pricing treatment changes on 2026-10-01. Keep all price figures and window-dependent fee assumptions outside coded business rules. [S21, S22]

## Uncertainty and Freshness

- Meta Developer pages were unavailable to the collector with HTTP 429. The admitted claims are therefore bounded to Twilio's current official integration contract; re-check Meta policy pages manually during sender/template onboarding.
- Twilio does not document an idempotency key for Message creation in the cited Messages resource. An ambiguous create timeout cannot be assumed safe to retry; reconciliation design must avoid duplicate billing notices.
- Twilio's permission PDF groups approval submission under Content-template creation and multiple approval/list reads under template-list permissions. Verify the exact least-privilege read set in a non-production Twilio account before rollout.
- Sender status, approval/category, quality, recipient limits, throughput, and pricing are volatile provider state and must be refreshed during deployment and operations.
- Revalidate all sources before production launch, after Twilio SDK/API-version upgrades, and whenever a provider error indicates a changed contract.

## Product Choices (Confirmed, Non-Authoritative)

- Billing-only Utility notifications; general notices and Marketing remain deferred.
- Explicit scoped consent; never infer consent from a phone number.
- Admin preview and digest-bound confirmation before dispatch.
- Durable transactional outbox and bounded reconciliation.
- Secure expiring PDF media URLs with private storage and repeatable Twilio fetches.
- Email only when consent is absent or a definite terminal WhatsApp failure is recorded; never for ambiguous provider outcomes.
- Production fails closed until sender status is `ONLINE` and every configured Content SID is currently Approved Utility.

## Evidence References and Readiness

- Exploration: `openspec/changes/official-whatsapp-billing-notifications/exploration.md` and Engram topic `sdd/official-whatsapp-billing-notifications/explore`.
- Research: `openspec/changes/official-whatsapp-billing-notifications/research.md` and Engram topic `sdd/official-whatsapp-billing-notifications/research`, revision 2.
- Pre-proposal: `openspec/changes/official-whatsapp-billing-notifications/preproposal.md` and Engram topic `sdd/official-whatsapp-billing-notifications/preproposal`, revision 2.
- Every selected research question is answered with mapped official evidence or an explicit bounded uncertainty.
- Research outcome: `done`.
- Product decisions: `confirmed` by orchestrator handoff.
- Proposal readiness: true only after identical-byte hybrid readback succeeds for both research and pre-proposal artifacts.