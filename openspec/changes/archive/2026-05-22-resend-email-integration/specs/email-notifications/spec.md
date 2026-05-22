# email-notifications Specification

## Purpose

Define outbound billing-publication email behavior that complements (and never breaks) existing publication and internal notification flows.

## Requirements

### Requirement: Config-gated outbound email

The system MUST treat outbound email as optional and configuration-gated. When email is disabled or required provider configuration is unavailable, publication behavior SHALL continue without outbound email attempts.

#### Scenario: Email disabled by configuration

- GIVEN billing publication is requested
- AND email notifications are disabled by configuration
- WHEN publication completes
- THEN the system MUST perform zero outbound email attempts
- AND publication outcome MUST remain successful if core publication rules pass

#### Scenario: Provider credentials missing

- GIVEN billing publication is requested
- AND email notifications are enabled
- AND required provider credentials or sender identity are missing
- WHEN publication completes
- THEN the system MUST skip outbound email attempts
- AND publication outcome MUST remain successful if core publication rules pass

### Requirement: Recipient eligibility filtering

The system MUST attempt billing-publication emails only for eligible recipients. Recipients without a usable email address SHALL be skipped and MUST NOT cause publication failure.

#### Scenario: Missing recipient email

- GIVEN billing publication is requested
- AND at least one intended recipient has no usable email address
- WHEN publication completes
- THEN the system MUST skip that recipient for outbound email
- AND publication outcome MUST remain successful if core publication rules pass

### Requirement: Successful outbound delivery attempt

When outbound email is enabled and recipient data is eligible, the system MUST attempt one billing-publication email per eligible recipient after publication data is successfully committed.

#### Scenario: Successful send attempt

- GIVEN billing publication has been committed successfully
- AND email notifications are enabled with valid provider configuration
- AND recipients are eligible
- WHEN outbound email processing runs
- THEN the system MUST attempt one billing-publication email per eligible recipient
- AND the system MUST report send outcomes as operational results

### Requirement: UPDS-branded billing email template contract

Billing-publication emails MUST render a UPDS-branded HTML template with a bounded container and structured billing table. The container SHALL use Segoe UI/Arial, approximate max width 650px, and include border, radius, and shadow. The header MUST use institutional colors (`#003366` background, white text, `#f4b400` bottom border) and include title `UNIVERSIDAD PRIVADA DOMINGO SAVIO` plus subtitle `Notificación de Honorarios Docentes`.

#### Scenario: Template includes mandatory static sections

- GIVEN billing publication has committed and recipient is eligible
- WHEN the billing email content is generated
- THEN the template MUST include greeting `Estimado(a) docente,`
- AND the docente full name MUST be visually highlighted in institutional blue
- AND the message MUST include the billing month
- AND the footer MUST include auto-generated notice and Gestión Humana contact `Lisseth, (+591) 69063028`

### Requirement: Billing table mirrors consolidated snapshot items

The billing table MUST use fixed columns `Materia`, `Monto a facturar`, `Grupo`, `Semestre` and render one data row per consolidated billing item from the existing publication snapshot shape. The system MUST NOT introduce a new billing calculation algorithm for email rendering.

#### Scenario: Multiple items render zebra rows and exact total

- GIVEN an eligible recipient has multiple consolidated billing items in the publication snapshot
- WHEN the billing table is rendered
- THEN each item MUST appear as one row under the fixed columns
- AND row backgrounds MUST alternate `#ffffff` and `#f9f9f9`
- AND a closing TOTAL row MUST use background `#e8f0fe` with `TOTAL:` right-aligned in `#003366`
- AND the total amount cell MUST display the exact consolidated total in `#d93025`
- AND the last two columns in the TOTAL row MUST be merged with `colspan="2"`

### Requirement: Provider failure is best-effort

Outbound provider or network failures MUST be treated as best-effort failures. The system MUST NOT rollback a successful publication commit nor suppress already-created internal notifications due to outbound email errors.

#### Scenario: Provider failure during send

- GIVEN billing publication has been committed successfully
- AND email notifications are enabled with eligible recipients
- WHEN the provider returns an error or the request times out
- THEN the system MUST record failed outbound attempts as operational failures
- AND the publication result MUST remain successful
- AND internal notifications MUST remain available
