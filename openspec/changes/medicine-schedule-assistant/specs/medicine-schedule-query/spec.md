# Medicine Schedule Query Specification

## Purpose

Define admin-only discovery and presentation of the active Medicine schedule.

## Requirements

### Requirement: Medicine-only active-version queries

The system MUST query only the active Medicine version and MUST NOT expose student or enrollment data. Every SIPAD administrator MUST be allowed to query; other roles MUST be denied.

#### Scenario: Query active Medicine data
- GIVEN an administrator and an active Medicine version
- WHEN a schedule query is submitted
- THEN results come exclusively from that active version and contain no student or enrollment data

#### Scenario: No active version
- GIVEN no active Medicine version
- WHEN an administrator opens schedule query
- THEN a supported empty state explains that activation is required and offers no stale results

### Requirement: Canonical filters and semester combinations

The system MUST filter by canonical semester/category, subject, group, teacher, shift, day, and time. Convalidación MUST be a distinct selectable category and MAY be combined with regular semesters. Seventh semester MUST remain visible but disabled as unsupported in V1.

#### Scenario: Cross-category query
- GIVEN active regular-semester and Convalidación offerings
- WHEN both categories and additional filters are selected
- THEN matching offerings from both categories appear using canonical subject and teacher identities

#### Scenario: Seventh semester selection
- GIVEN the semester selector is displayed
- WHEN an administrator inspects seventh semester
- THEN it is visible, disabled, and identified as unsupported rather than silently omitted

### Requirement: Synchronized calendar and table

Results MUST provide synchronized weekly-calendar and detailed-table views representing the same filtered records. Switching views MUST preserve filters and selection, and both views MUST identify the same conflicts and warnings.

#### Scenario: Switch presentation
- GIVEN filtered results with a selected offering and warning
- WHEN the administrator switches between calendar and table
- THEN filters and selection remain unchanged and the warning identifies the same offering

### Requirement: Supported states and responsive operation

The system MUST distinguish loading, no-match, no-active-version, authorization, validation, and service-error states and MUST provide a retry for recoverable errors. Desktop and tablet SHOULD receive the optimized layout; mobile MUST remain functionally operable for filtering, viewing, and switching representations.

#### Scenario: No matching records
- GIVEN a valid query whose filters match no offering
- WHEN results complete
- THEN a no-match state is shown without presenting the condition as an error

#### Scenario: Query failure on mobile
- GIVEN an administrator using a mobile viewport
- WHEN a recoverable query failure occurs
- THEN an error state with retry remains operable and is not rendered as empty data
