# Designation Management Rollout

Issue: [#113](https://github.com/fabricio19102003/planilla-docentes-upds/issues/113)

## Objective

Move the II/2026 theory and internal-practice designation baseline into SIPAD's
effective-dated schedule workflow without overwriting legacy operational data.

## Delivery chain

```text
tracker (this branch)
  └── preview and source validation
        └── digest-bound draft apply
              └── administrative API contracts
                    └── frontend API and state
                          └── accessible import workflow
```

Only this tracker merges into `master` after every child slice has passed its
focused checks and been integrated into the tracker branch.

## Safety boundaries

- The initial import is all-or-nothing and creates a draft only.
- Publication remains a separate explicit action.
- Legacy designations and prior immutable publications are not mutated.
- Teacher and subject aliases are explicit, source-bound, and never fuzzy.
- Production apply requires a fresh preview against the live catalog state.
- Deployment and data apply require independent backups and read-back checks.

## Planned slices

1. Hardened workbook parsing, preview, and exact alias validation.
2. Idempotent, digest-bound draft apply with append-only receipts.
3. Admin-only HTTP contracts for preview, resolution, and apply.
4. Typed frontend API and deterministic client state.
5. Accessible schedule-planner import and alias-resolution workflow.

## Verification record

- Focused backend suite: 87 passed.
- PostgreSQL concurrency suite: 3 passed.
- Frontend build and lint: passed.
- Frontend academic-management, schedule-planner, publication, and bootstrap
  checks: passed.
- Independent correctness, privacy, and reliability re-review: passed.

## Rollback boundary

Before production apply, rollback is the exact release preceding this tracker.
After apply, rollback restores the pre-deployment database backup and prior
release together; application-only rollback is not sufficient after migration
or designation writes.
