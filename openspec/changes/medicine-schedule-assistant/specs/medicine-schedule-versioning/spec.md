# Medicine Schedule Versioning Specification

## Purpose

Define the admin-only, auditable lifecycle for Medicine schedule workbooks.

## Requirements

### Requirement: Authorized strict import and preview

The system MUST permit every SIPAD administrator, and no other role, to upload only workbooks matching the current `horarios-med.xlsx` structure. Each upload MUST require an academic period, MAY include a description, and MUST produce a non-active preview without approximate extraction.

#### Scenario: Valid workbook preview
- GIVEN an administrator and a conforming workbook with an academic period
- WHEN the workbook is uploaded
- THEN a preview version is created with parsed Medicine records and optional description
- AND the active version remains unchanged

#### Scenario: Unauthorized or unsupported upload
- GIVEN a non-administrator or a workbook with an unsupported structure
- WHEN upload is attempted
- THEN the system rejects it with an explanatory error and creates no activatable version

### Requirement: Validation and corrections

The preview MUST separate errors from warnings and identify each issue's location and explanation. Errors MUST block activation; warnings MAY proceed only after explicit acceptance. Corrections and canonical subject/teacher unifications MUST preserve raw and corrected values, administrator, and timestamp; canonical values MUST drive queries while raw values remain inspectable.

#### Scenario: Correct and accept warnings
- GIVEN a preview containing correctable values and warnings but no remaining errors
- WHEN an administrator records corrections and explicitly accepts the warnings
- THEN the preview is activatable and preserves every raw value, correction, acceptance, actor, and timestamp

#### Scenario: Errors block activation
- GIVEN a preview with at least one unresolved error
- WHEN activation is requested
- THEN activation is rejected and the current active version is unchanged

### Requirement: Activation and restoration

The system MUST maintain exactly one active Medicine version when any version has been activated. Activation MUST atomically replace the active version. An administrator MUST be able to restore a prior activatable version, making it active without deleting later versions or lineage.

#### Scenario: Activate a validated version
- GIVEN an activatable preview and an existing active version
- WHEN an administrator activates the preview
- THEN the preview becomes the sole active version and the former version remains in history

#### Scenario: Restore prior version
- GIVEN a prior activatable version in history
- WHEN an administrator restores it
- THEN it becomes the sole active version and all intervening history remains available

### Requirement: Audited lifecycle

Every upload, warning acceptance, correction, activation, and restoration MUST record its administrator and timestamp. Version history MUST expose period, description, status, actors, timestamps, validation outcomes, and raw-to-canonical lineage.

#### Scenario: Inspect history
- GIVEN versions with lifecycle operations
- WHEN an administrator opens version history
- THEN each operation and lineage entry is attributable and chronologically inspectable
