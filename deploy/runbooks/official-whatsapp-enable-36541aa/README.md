# Controlled activation operator guidance — release 36541aa

This package is documentation and safety fixtures only. It contains no executable
production procedure, recipient, personal data, credential, secret value, provider
identifier, or live hostname. Operational scripts (`lib.sh`, `01-stage.sh` through
`04-rollback.sh`) refuse before work. `tests/run-fixtures.sh` is a harmless local
harness limited to local inspection and refusal stubs.

## Non-negotiable defaults

- Ordinary global delivery remains `false`; no step authorizes changing it.
- Every activation gate remains `false` unless its own current human approval says
  otherwise. A later terminal observation restores every activation gate to `false`.
- Readiness is a read-only observation. A ready result does **not** authorize
  creation, dispatch, deployment, or ordinary delivery.
- Earlier approval never carries forward. Stop if authorization is missing, stale,
  ambiguous, inconsistent, or outside this release boundary.

## Separate human authorization gates

Obtain and record a fresh, named approval for each gate below. An approval grants
only its listed action and expires at that action's terminal observation.

1. **Delivery governance:** push, pull request, and merge of this reviewed release
   boundary. This does not authorize deployment.
2. **Deployment:** release deployment with ordinary delivery and activation gates
   still false. This does not authorize readiness observation.
3. **Readiness-only observation:** a read-only, bounded observation of release,
   process gates, worker health, and transport capability. It does not authorize a
   configuration change, activation creation, or dispatch.
4. **One activation creation:** create exactly one activation after secure review of
   consent and current identity. This does not authorize dispatch.
5. **Final one-message dispatch:** dispatch the already-created activation once.
   This is the final, separate approval and never enables ordinary delivery.

## Exactly-one contract

The recipient is supplied only at execution time through an approved secure channel;
it is never written in this package or its evidence. Server-side controls must match
that supplied recipient to current identity, current consent, and the bound HMAC.

The approved execution creates exactly one activation, one job, one token, and one
publication binding. It must not create a batch, use fallback email, or substitute a
recipient, publication, token, or job. An unknown, timed-out, or otherwise ambiguous
outcome stops the lifecycle without retry. Callback evidence and the sanitized status
audit are required before terminal observation. After terminal observation, revoke
the token and restore all activation gates to `false`.

## Preflight evidence checklist

Before the specific gate being considered, capture only bounded evidence that:

- this is release 36541aa and the reviewed change boundary is intact;
- ordinary global delivery is false and activation gates are false by default;
- the approval record names only the pending gate and responsible operator;
- readiness observation is read-only and its result is not treated as authorization;
- consent, identity, HMAC, publication, and one-message constraints will be checked
  server-side at execution time; and
- ordinary queues and jobs have been observed and will remain untouched.

Stop and escalate if any evidence is absent, conflicts, exposes sensitive material,
or suggests an ordinary queue/job would be read, leased, changed, cancelled, or sent.

## Lifecycle and postflight evidence

1. Confirm the delivery-governance approval before push, pull request, or merge.
2. Confirm the deployment approval before deployment; retain **all five** false
   defaults: ordinary, official, dispatch, activation API, and activation dispatch.
3. Deploy schema first, then code, then focused verification; restore only a separately
   authorized process gate. Ordinary global delivery remains false throughout.
4. Confirm readiness-only approval before observation; record bounded results only.
5. Confirm activation-creation approval immediately before one creation; capture the
   sanitized activation/status audit proving one binding.
6. Before final dispatch, retain sanitized evidence of the release state and deadline.
   A creator cancellation or expiry must show cancelled work and revoked authority/media;
   a consumed state must retain its consumed proof and is never retried.
7. Confirm final-dispatch approval immediately before one dispatch; do not reuse any
   prior approval. Observe callback evidence and final sanitized status, then restore
   every activation gate to false. Prove ordinary queues/jobs remain untouched.

Postflight evidence must show release/cancel/expiry/consumed state as applicable, the
terminal status, callback/status audit, token revocation where required, false gates,
false ordinary global delivery, and unchanged ordinary queues/jobs. Use only bounded
IDs, state/reason codes, and timestamps: never record recipient data, idempotency keys,
provider payloads, HMACs, SIDs, token values/paths, credentials, or configuration
secrets.

## Stop, rollback, and incident boundary

Stop immediately for missing/stale approval, failed or non-read-only readiness,
identity/consent/HMAC mismatch, more than one binding, any ordinary queue/job change,
unknown dispatch outcome, missing callback evidence, or any sensitive disclosure.
Do not retry an ambiguous dispatch.

Rollback is a human decision, not a script. Disable release/activation dispatch and
stop activation workers first; revoke every unconsumed authorization and bound media
with the new lifecycle, while preserving consumed, ambiguous, and terminal evidence
without retry. **Do not deploy an old worker while any pending or authorized activation
graph remains eligible**: old status-only claim logic cannot enforce authorization.
Keep ordinary global delivery false, restore activation gates false, and preserve
bounded audit/callback evidence for reconciliation. Do not delete history, create a
replacement activation, or alter ordinary queues/jobs. Escalate to the incident owner
when outcome, authorization, identity, consent, audit, or queue isolation cannot be
proven.

## Local safety-fixture validation

```text
bash -n deploy/runbooks/official-whatsapp-enable-36541aa/{lib.sh,01-stage.sh,02-activate.sh,03-single-send.sh,04-rollback.sh,tests/run-fixtures.sh}
bash deploy/runbooks/official-whatsapp-enable-36541aa/tests/run-fixtures.sh
git diff --check 8d66c17 -- deploy/runbooks/official-whatsapp-enable-36541aa openspec/changes/official-whatsapp-controlled-activation
git diff --numstat 8d66c17 -- deploy/runbooks/official-whatsapp-enable-36541aa openspec/changes/official-whatsapp-controlled-activation
```

The fixture is the sole non-refusal shell file: a harmless local harness that runs
only local inspection and refusal stubs, then rejects unsafe command or sensitive
literal patterns statically. It performs no operational action.
