import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const root = resolve(import.meta.dirname, '..')
const billingPage = readFileSync(resolve(root, 'src/pages/BillingPage.tsx'), 'utf8')
const historyPage = readFileSync(resolve(root, 'src/pages/BillingHistoryPage.tsx'), 'utf8')

// Source text of a top-level `function Name` up to the next top-level function (or EOF).
function functionSource(source, name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `function ${name} must exist`)
  const next = source.indexOf('\nfunction ', start + 1)
  return source.slice(start, next === -1 ? undefined : next)
}

test('billing page lists designations as cards below sm and keeps the table from sm up', () => {
  assert.match(billingPage, /data-testid="designation-mobile-list"[^>]*sm:hidden|sm:hidden[^>]*data-testid="designation-mobile-list"/)
  assert.match(billingPage, /className="hidden sm:block/)
  assert.match(billingPage, /<table className="min-w-\[760px\] w-full text-sm">/)
})

test('billing designation card shows hours, gross and net from backend values', () => {
  const card = functionSource(billingPage, 'DesignationMobileCard')
  assert.match(card, /designation\.subject/)
  assert.match(card, /designation\.semester/)
  assert.match(card, /designation\.group/)
  assert.match(card, /designation\.hours/)
  assert.match(card, /formatBs\(designation\.gross_payment\)/)
  assert.match(card, /formatBs\(designation\.net_payment\)/)
})

test('billing designation card shows retention only when above zero and adjustment only on override', () => {
  const card = functionSource(billingPage, 'DesignationMobileCard')
  assert.match(card, /designation\.retention_amount > 0 &&/)
  assert.match(card, /formatBs\(designation\.retention_amount\)/)
  assert.match(card, /designation\.has_admin_override &&/)
  assert.match(card, /designation\.admin_adjustment/)
})

test('billing page has a mobile totals card replacing the table footer on small screens', () => {
  assert.match(billingPage, /data-testid="billing-mobile-totals"/)
  const totals = billingPage.slice(billingPage.indexOf('data-testid="billing-mobile-totals"'))
  assert.match(totals.slice(0, 2500), /billing\.total_hours/)
  assert.match(totals.slice(0, 2500), /formatBs\(billing\.gross_payment\)/)
  assert.match(totals.slice(0, 2500), /billing\.retention_amount > 0/)
  assert.match(totals.slice(0, 2500), /formatBs\(displayPayment\)/)
})

test('history page lists months as cards below sm and keeps the table from sm up', () => {
  assert.match(historyPage, /data-testid="history-mobile-list"[^>]*sm:hidden|sm:hidden[^>]*data-testid="history-mobile-list"/)
  assert.match(historyPage, /className="hidden sm:block/)
  assert.match(historyPage, /<table className="min-w-\[720px\] w-full text-sm">/)
})

test('history month card shows type, hours, net amount and the invoice headline with a toggle', () => {
  const card = functionSource(historyPage, 'BillingMonthCard')
  assert.match(card, /billing\.month_name/)
  assert.match(card, /billing\.year/)
  assert.match(card, /Prácticas/)
  assert.match(card, /Teóricas/)
  assert.match(card, /billing\.total_hours/)
  assert.match(card, /formatBs\(billing\.net_payment\)/)
  assert.match(card, /instruction\.headline/)
  assert.match(card, /aria-expanded=\{isExpanded\}/)
  assert.match(card, /onClick=\{onToggle\}/)
})

test('history expanded detail lists each designation as a card with amounts', () => {
  const card = functionSource(historyPage, 'BillingMonthCard')
  assert.match(card, /billing\.designations\.map/)
  assert.match(card, /designation\.hours/)
  assert.match(card, /formatBs\(designation\.gross_payment\)/)
  assert.match(card, /designation\.retention_amount > 0 &&/)
  assert.match(card, /designation\.has_admin_override &&/)
  assert.match(card, /formatBs\(designation\.net_payment\)/)
})

test('mobile and desktop history details use distinct element ids', () => {
  const card = functionSource(historyPage, 'BillingMonthCard')
  assert.match(card, /-mobile/)
})
