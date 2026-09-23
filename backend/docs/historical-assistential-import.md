# Run the II/2026 historical assistential import safely

This internal CLI creates two immutable schedule publications without creating teacher availability or legacy `Designation` rows. Normal API and UI validation remains unchanged.

## Quick path

1. Keep all five private inputs outside the repository and calculate each SHA-256 locally.
2. Run `preview`; retain its canonical JSON and `digest`.
3. Review blockers, masked profile actions, lineage, and the expected `33 → 32` block counts.
4. Run `apply` with the unchanged files and `--expected-digest`. Apply uses one database transaction.

From `backend/`, use private paths outside the repository:

```bash
python -m scripts.historical_assistential_import preview \
  --designation "$PRIVATE_DIR/designation.xlsx" --designation-sha256 "$DESIGNATION_SHA256" \
  --curriculum "$PRIVATE_DIR/curriculum.txt" --curriculum-sha256 "$CURRICULUM_SHA256" \
  --enrollment "$PRIVATE_DIR/enrollment.xlsx" --enrollment-sha256 "$ENROLLMENT_SHA256" \
  --profiles "$PRIVATE_DIR/teacher-profiles.json" --profiles-sha256 "$PROFILES_SHA256" \
  --decisions "$PRIVATE_DIR/corrections.json" --decisions-sha256 "$DECISIONS_SHA256" \
  --actor-ci "$ADMIN_CI" --policy historical_availability_not_recorded \
  --effective-date 2026-08-20 --historical-availability-unrecorded
```

Use the same arguments for `apply`, adding `--expected-digest "$PREVIEW_DIGEST"`. Do not redirect preview output into the private input directory if that directory is synchronized or shared.

## Decision file contract

The private decision JSON is the explicit authority for corrections. It contains:

- `academic_period`: exactly `II/2026`;
- `default_effective_date`, `inclusive_until`, and `replacement_from`;
- `physical_source_rows` (37 distinct rows) and `red_source_rows` backed by workbook style;
- `blocks`: 33 canonical blocks with subject code, source label, semester, group, weekday, exact time, classroom evidence, source rows, and teacher intervals;
- classroom `enrollment_row` and physical `capacity` for normal rooms; `EXTRA` uses type `other`, name `Sin aula / campo asistencial`, and `capacity=NULL` because physical capacity does not apply;
- assignment `teacher_ci` values that must exist as exact keys in the private profile JSON.

The importer requires 36 logical intervals, three replacements on 2026-09-02, and 32 assigned blocks in the second revision. A duplicated physical source assignment is represented by two `source_rows` on one logical interval.

## Safety properties

| Concern | Enforcement |
|---|---|
| Historical exception | CLI-only service; no normal planner validator is changed |
| Availability | No `TeacherAvailability` row is created |
| Source drift | Five required source hashes plus preview digest |
| State drift | Preview digest includes a database-state fingerprint |
| Replay | Durable source-hash idempotency receipt |
| Concurrency | PostgreSQL transaction-scoped advisory lock |
| Privacy | Output masks CI and reports profile field actions without values |
| Authority policy | One closed policy token with a fixed technical description; no free-form note is accepted or persisted |
| Partial state | Existing target catalogs, drafts, publications, or legacy practice rows are refused |
| Retroactive effects | Relevant attendance, practice payroll, contracts, and billing evidence blocks apply |
| Atomicity | Catalogs, profiles, drafts, publications, receipt, and audit event share one transaction |

The curriculum parser checks only the four exact subject codes. Malformed unrelated curriculum text cannot change their mapping.
