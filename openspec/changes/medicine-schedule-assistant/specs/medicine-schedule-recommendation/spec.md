# Medicine Schedule Recommendation Specification

> **Coexistence invariant:** Authority covers only Medicine queries/simulations; `Designation.schedule_json` retains payroll/attendance/designation authority. `scheduling-module` is excluded; V1 forbids adapter/sync/migration; migration requires separate OpenSpec.

## Requirements

### Requirement: Complete combination generation

Every result MUST include all mandatory subjects. Optionals MUST be candidate additions: a result MAY omit them, and results MAY contain different optional subsets. Each included subject MUST use exactly one complete group containing every theory, practice, and laboratory meeting. Shifts, unavailable windows, and forced/excluded groups or teachers MUST be hard constraints; contradictions MUST cause validation errors.

#### Scenario: Generate complete groups
- GIVEN mandatory and optional subjects with multiple meetings and hard constraints
- WHEN an administrator simulates
- THEN every result includes one complete group for every mandatory subject
- AND each optional subject included in that result has one complete group

#### Scenario: Optional candidates vary across results
- GIVEN two optional candidates and feasible mandatory subjects
- WHEN combinations are generated
- THEN results MAY omit both or include different optional subsets
- AND omission of an optional subject does not invalidate a result

#### Scenario: No feasible combination
- GIVEN hard constraints that admit no complete combination
- WHEN simulation finishes
- THEN a supported no-results state explains the limiting constraints without partial groups

### Requirement: Conflict tolerance and alternatives

Positive-duration intersections MUST be conflicts; meetings where one endpoint equals the other's endpoint MUST NOT conflict. A result MUST NOT exceed either configured maximum duration per conflict or maximum conflict count. Alternatives within both limits MAY appear with warnings identifying subjects, day, exact interval, and overlap duration.

#### Scenario: Boundary and tolerated conflict
- GIVEN contiguous meetings and another overlap within both limits
- WHEN conflicts are evaluated
- THEN the contiguous meetings add zero conflicts and the overlap is retained with exact warning details

#### Scenario: Limit exceeded
- GIVEN a candidate exceeding either conflict limit
- WHEN candidates are admitted
- THEN that candidate is excluded rather than merely penalized

### Requirement: Deterministic ranking and result delivery

The system MUST rank deterministically by: fewer conflicts, fewer overlap minutes, more included optionals, greater equal-weight fulfillment of day/time/group/teacher preferences, fewer gap minutes, then fewer distinct groups. Gaps MUST equal each day's positive time between consecutive non-overlapping meetings, summed weekly. The first 10 results MUST appear; more MAY load without reordering.

#### Scenario: Rank tied candidates
- GIVEN candidates differing across ranking criteria
- WHEN ranked repeatedly against the same version and inputs
- THEN their order follows the exact precedence and remains identical

#### Scenario: Load more
- GIVEN more than ten ranked results
- WHEN the administrator loads more
- THEN the original top ten remain in order and subsequent results continue that order

### Requirement: Explicit immutable simulation snapshot

Saving MUST be explicit, require a name, MAY include a note, and persist only the selected result with filters, source version, metrics, warnings, creator, and timestamp. Saved simulations MUST be immutable, exportable, duplicable, and archivable but not deletable; archive actor/time MUST be audited.

#### Scenario: Save and duplicate selection
- GIVEN one selected result and a name
- WHEN it is saved and later duplicated
- THEN the saved snapshot stays unchanged and the duplicate carries its data into a new editable simulation

#### Scenario: Save without selection or name
- GIVEN no selected result or no name
- WHEN save is attempted
- THEN validation fails and no snapshot is created

### Requirement: Selected-combination PDF

PDF MUST contain only the selection, including period, subjects, groups, weekly calendar, gaps, conflicts, and warnings.

#### Scenario: Export PDF
- GIVEN a selected result containing warnings
- WHEN PDF export is requested
- THEN the PDF reproduces that selection and includes every required metric, conflict, and warning

#### Scenario: Export without selection
- GIVEN no selected combination
- WHEN PDF export is requested
- THEN export is rejected with a selection-required error
