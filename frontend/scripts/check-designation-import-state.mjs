import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const page = readFileSync(resolve(root, 'src/pages/UploadPage.tsx'), 'utf8')
const hooks = readFileSync(resolve(root, 'src/api/hooks/useBiometric.ts'), 'utf8')
const types = readFileSync(resolve(root, 'src/api/types.ts'), 'utf8')

assert.match(hooks, /\/uploads\/designations\/preview\?academic_period=/)
assert.match(hooks, /confirmation_digest=/)
assert.match(hooks, /if \(!payload\.confirmation_digest\)/)
assert.doesNotMatch(hooks, /academic_period \?\? ['"]I\/2026['"]/)

assert.match(page, /Generar vista previa/)
assert.match(page, /Confirmar e importar/)
assert.match(page, /desPreview\?\.can_apply/)
assert.match(page, /confirmation_digest: desPreview\.digest/)
assert.match(page, /setDesPreview\(null\)/)
assert.match(page, /no lo activa automáticamente/)

assert.match(types, /interface DesignationImportPreview/)
assert.match(types, /can_apply: boolean/)
assert.match(types, /conflicts: number/)

console.log('Designation import preview/apply UI contract: OK')
