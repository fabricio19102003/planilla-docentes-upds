import assert from 'node:assert/strict'
import {
  getHistoricalPaymentState,
  getVisiblePlanillaDetail,
} from '../src/lib/planillaHistory.ts'

const available = getHistoricalPaymentState({ data_status: 'available', total_payment: '120.00' })
const legacy = getHistoricalPaymentState({ data_status: 'legacy_unavailable', total_payment: null })
const detail = { rows: [{ teacher_ci: 'snapshot' }], total_payment: 120 }

assert.equal(getVisiblePlanillaDetail(detail, false, available.snapshotAvailable), detail)
const legacyDetail = getVisiblePlanillaDetail(detail, false, legacy.snapshotAvailable)
assert.equal(legacyDetail?.rows.length ?? 0, 0)
assert.equal(legacyDetail?.total_payment ?? null, null)
assert.equal(getVisiblePlanillaDetail(detail, true, available.snapshotAvailable), undefined)
