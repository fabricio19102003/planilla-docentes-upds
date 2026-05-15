# Contract Automation — Specification

> Change: `contract-automation`  
> Status: Implemented  
> Last updated: 2026-05-15  
> Commit: `d39624c feat: automate contract rates and dates`

---

## 1. Overview

The contracts module SHALL generate contracts using authoritative configuration and assignment data instead of manual contract-screen inputs. The contract PDF wording remains unchanged; only the injected values for hourly rate, duration, start date, and end date are automated.

---

## 2. Data Model

### 2.1 Designation contract dates

**Table**: `designations`

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `contract_start_date` | `Date` | nullable | `NULL` | Start date for this specific subject/group assignment. |
| `contract_end_date` | `Date` | nullable | `NULL` | End date for this specific subject/group assignment. |

### Business Rules

- BR-CD-1: Contract dates SHALL be stored per designation/assignment, not only per teacher.
- BR-CD-2: `contract_end_date` MUST NOT be earlier than `contract_start_date` when both are provided.
- BR-CD-3: Nullable dates are allowed at storage level to support staged imports and incomplete data.
- BR-CD-4: Contract generation MUST require both dates for every active-period designation included in that teacher's contract.

---

## 3. Contract Generation

### 3.1 Rate resolution

Given a teacher's active-period designations:

- If all designations have `designation_type == "practice"`, the contract MUST use `PRACTICE_HOURLY_RATE`.
- Otherwise, the contract MUST use `HOURLY_RATE`.
- The frontend MUST NOT send `hourly_rate` or `hourly_rate_literal` as contract inputs.
- The backend MUST format both numeric and literal Spanish currency values for the existing PDF template.

### 3.2 Date resolution

Given a teacher's active-period designations:

- The contract start date MUST be the minimum non-null `contract_start_date`.
- The contract end date MUST be the maximum non-null `contract_end_date`.
- If any designation lacks either date, single contract generation MUST fail with a clear error.
- In batch generation, teachers with invalid/missing dates SHOULD be skipped while successful teachers are still generated; errors SHOULD be returned in the response.
- Dates inserted into the PDF MUST be formatted in Spanish, e.g. `05 de marzo de 2026`.
- Duration text MUST be computed automatically from resolved start/end dates, e.g. `4 meses y 13 días`.

---

## 4. UPDS JSON Import

For UPDS official designation JSON files, the loader SHALL map:

| JSON Key | Designation Field |
|----------|-------------------|
| `FECHA INICIO` | `contract_start_date` |
| `FECHA FIN` | `contract_end_date` |

### Import Rules

- Valid ISO dates (`YYYY-MM-DD`) MUST be parsed into Python `date` objects.
- Empty or absent dates SHOULD remain `NULL`.
- Invalid date strings SHOULD add an import warning and store `NULL`.
- If both dates exist and end is earlier than start, the loader SHOULD warn and store both fields as `NULL` for that designation.
- Non-UPDS formats MUST NOT accidentally wipe previously stored contract dates.

---

## 5. Frontend Behavior

### 5.1 Contracts page

- The contracts page MUST NOT expose manual fields for hourly rate, rate literal, duration, start date, or end date.
- The page SHOULD explain that rates come from Configuración and dates come from each designation.

### 5.2 Teacher detail page

- The teacher detail page SHOULD allow admins to edit `contract_start_date` and `contract_end_date` per designation.
- Saving invalid date ranges MUST be rejected by the backend.

---

## 6. Scenarios

### Scenario: Practice-only teacher contract uses practice rate

Given a teacher has only active-period designations with `designation_type = "practice"`  
And every designation has `contract_start_date` and `contract_end_date`  
When an admin generates the teacher's contract  
Then the generated PDF MUST show the configured practice hourly rate.

### Scenario: Theory teacher contract uses regular rate

Given a teacher has at least one active-period designation that is not `practice`  
And every designation has `contract_start_date` and `contract_end_date`  
When an admin generates the teacher's contract  
Then the generated PDF MUST show the configured theory hourly rate.

### Scenario: Contract dates derive from assignments

Given a teacher has multiple active-period designations with contract dates  
When an admin generates the teacher's contract  
Then the PDF start date MUST be the earliest designation start date  
And the PDF end date MUST be the latest designation end date.

### Scenario: Missing designation dates block generation

Given a teacher has an active-period designation without contract start or end date  
When an admin generates the teacher's contract  
Then the backend MUST reject generation for that teacher  
And the error MUST identify the missing designation dates.

### Scenario: UPDS practice JSON populates contract dates

Given a UPDS official JSON row contains `FECHA INICIO` and `FECHA FIN`  
When an admin uploads the designations file  
Then the created or updated designation MUST persist those values as contract dates.

---

## 7. Verification

- `python -m py_compile backend/app/services/designation_loader.py`
- `npm run lint`
- `npm run build`
