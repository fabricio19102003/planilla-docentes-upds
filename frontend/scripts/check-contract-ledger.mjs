import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/pages/ContractsPage.tsx', import.meta.url), 'utf8')
const detail = readFileSync(new URL('../src/pages/TeacherDetailPage.tsx', import.meta.url), 'utf8')
const hooks = readFileSync(new URL('../src/api/hooks/useContracts.ts', import.meta.url), 'utf8')
const teacherHooks = readFileSync(new URL('../src/api/hooks/useTeachers.ts', import.meta.url), 'utf8')

assert.match(page, /Historial Inmutable/)
assert.match(page, /aria-labelledby="contract-history-heading"/)
assert.match(page, /role="status"/)
assert.match(page, /role="alert"/)
assert.match(page, /key=\{document\.public_id\}/)
assert.match(page, /Emitir o Recuperar Contratos/)
assert.match(hooks, /\/contracts\/history/)
assert.match(hooks, /download_url/)
assert.doesNotMatch(detail, /ContractDateEditor|Fecha de inicio de contrato|Contrato inicio \/ fin/)
assert.doesNotMatch(teacherHooks, /contract-dates|useUpdateDesignationContractDates/)

console.log('Contract ledger frontend checks passed')
