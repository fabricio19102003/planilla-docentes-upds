import assert from 'node:assert/strict'

import {
  formatDateInBolivia,
  formatShortDateInBolivia,
  getTodayInBolivia,
} from '../src/lib/boliviaDates.ts'

assert.equal(formatDateInBolivia('2026-06-04'), '04/06/2026')
assert.equal(formatShortDateInBolivia('2026-06-04'), '04/06')
assert.equal(formatShortDateInBolivia(null), '—')
assert.equal(getTodayInBolivia(new Date('2026-06-04T03:59:59.000Z')), '2026-06-03')
assert.equal(getTodayInBolivia(new Date('2026-06-04T04:00:00.000Z')), '2026-06-04')

console.log('Bolivia date regression checks passed')
