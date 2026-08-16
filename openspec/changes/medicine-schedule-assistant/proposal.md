# Proposal: Medicine Schedule Assistant

## Intent

Add an admin-only SIPAD assistant for traceable Medicine data and ranked combinations.

## Scope

### In Scope
- Import Medicine workbook versions; preserve raw/canonical values; preview, validate, audit corrections/warning acceptance, activate, and restore.
- Query schedules; combine Convalidación with regular semesters; show seventh semester unsupported.
- Generate combinations with all mandatory subjects and variable optional additions, one complete group each. Apply hard availability/shift/conflict filters. Rank by conflict count, overlap minutes, optional count, then equal-weight day/time/group/teacher preferences; show top 10.
- Save only the selected combination as an immutable, archivable snapshot with inputs, metrics, warnings, actor, and version.
- Provide synchronized calendar/table and selected-combination PDF; prioritize desktop/tablet.

### Out of Scope
- Students, enrollment, other careers, configurable weights, or seventh-semester extraction.
- Native authoring, rooms/equipment, payroll migration, or replacing Excel.

## Capabilities

### New Capabilities
- `medicine-schedule-versioning`: Preview, validation, audited correction, activation, restoration, and raw-data lineage.
- `medicine-schedule-query`: Canonical filters and synchronized calendar/table presentation.
- `medicine-schedule-recommendation`: Generation, ranking, immutable snapshots, and PDF export.

### Modified Capabilities
- None; specs are unrelated.

## Approach

Build a Medicine compatibility layer using SIPAD authentication and imports. Use the parser as reference; separate versions and simulations.

**Approved coexistence boundary:** In V1, this change is authoritative only for Medicine queries and simulations. `Designation.schedule_json` remains authoritative for payroll, attendance, and designations. The unchanged `scheduling-module` does not govern Medicine. V1 includes no adapter, synchronization, or migration; future migration requires a separate explicit OpenSpec change.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/app/{models,schemas,services,routers}` | New/Modified | Version, query, ranking, audit, PDF. |
| `frontend/src/{pages,components,api}` | New/Modified | Import and simulation. |
| `backend/alembic/versions` | New | Versioned data and simulations. |
| `openspec/changes/scheduling-module` | Unchanged | Does not govern Medicine V1. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Workbook ambiguity | High | Block errors; accept warnings; preserve data and restores. |
| Combination growth/ranking | High | Bound results; set performance budgets. |
| Authority boundary drift | Medium | Enforce approved V1 ownership. |

## Rollback Plan

Disable endpoints, restore a prior version, and retain audits. Legacy and `scheduling-module` data remain unchanged.

## Dependencies

- Workbook contract and `horarios_med_query.py` reference.
- SIPAD authentication, migrations, and ReportLab.

## Success Criteria

- [ ] 100% of activations are versioned, attributed, restorable, and error-blocked.
- [ ] Queries/top-10 rankings reproduce; hard filters admit no rejected combination.
- [ ] Every result includes all mandatory subjects; every mandatory and included optional subject has exactly one complete group.
- [ ] Simulations/PDFs exactly reproduce selection, inputs, metrics, conflicts, and warnings.
- [ ] Seventh semester is visible/unsupported; no student or enrollment data is introduced.
