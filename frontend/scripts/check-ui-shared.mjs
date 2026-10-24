import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import test from 'node:test'

const root = resolve(import.meta.dirname, '..')
const src = join(root, 'src')

function read(relative) {
  const path = join(src, relative)
  assert.ok(existsSync(path), `src/${relative} is missing`)
  return readFileSync(path, 'utf8')
}

function exportedNames(code) {
  const exported = new Set()
  for (const match of code.matchAll(/export\s+(?:declare\s+)?(?:async\s+)?(?:function|const|class|interface|type)\s+(\w+)/g)) {
    exported.add(match[1])
  }
  for (const block of code.matchAll(/export\s*\{([^}]*)\}/g)) {
    for (const part of block[1].split(',')) {
      const alias = part.trim().split(/\s+as\s+/).pop()
      if (alias) exported.add(alias.replace(/^type\s+/, ''))
    }
  }
  return exported
}

function assertNoLegacyChrome(file) {
  const code = read(file)
  assert.deepEqual(code.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [], `${file} must not contain hex colors`)
  assert.deepEqual(code.match(/\bgradient-[\w-]+/g) ?? [], [], `${file} must not use gradient-* classes`)
  assert.deepEqual(code.match(/(?:linear|radial)-gradient/g) ?? [], [], `${file} must not use CSS gradients`)
  assert.doesNotMatch(code, /style=\{\{[^}]*(?:color|Color|background)/, `${file} must not set colors through style`)
}

test('page-slice helpers exist and are exported', () => {
  const expected = {
    'components/shared/PageHeader.tsx': ['PageHeader'],
    'components/shared/StatusBadge.tsx': ['StatusBadge'],
    'components/shared/EmptyState.tsx': ['EmptyState'],
    'components/shared/TableCard.tsx': ['TableCard'],
    'components/shared/ConfirmAlertDialog.tsx': ['ConfirmAlertDialog'],
  }
  for (const [file, names] of Object.entries(expected)) {
    const exported = exportedNames(read(file))
    for (const name of names) assert.ok(exported.has(name), `${file} must export ${name}`)
  }
})

test('PageHeader follows the S11 header pattern', () => {
  const code = read('components/shared/PageHeader.tsx')
  assert.match(code, /text-2xl font-semibold tracking-tight/)
  assert.match(code, /title/)
  assert.match(code, /description/)
  assert.match(code, /actions/)
  assert.match(code, /breadcrumb|back/i)
  assert.match(code, /flex-col/, 'actions must stack below the title on mobile')
  assert.match(code, /@example/, 'PageHeader needs a JSDoc usage example')
})

test('ConfirmAlertDialog is built on AlertDialog', () => {
  assert.match(read('components/shared/ConfirmAlertDialog.tsx'), /@\/components\/ui\/alert-dialog/)
})

test('StatusBadge is an outline badge with a colored dot', () => {
  const code = read('components/shared/StatusBadge.tsx')
  assert.match(code, /variant="outline"/)
  assert.match(code, /rounded-full/)
  for (const tone of ['primary', 'success', 'warning', 'destructive', 'info', 'neutral']) {
    assert.match(code, new RegExp(`\\b${tone}\\b`), `StatusBadge needs the ${tone} tone`)
  }
})

test('EmptyState wraps coss Empty and TableCard wraps Card + Table', () => {
  assert.match(read('components/shared/EmptyState.tsx'), /@\/components\/ui\/empty/)
  const tableCard = read('components/shared/TableCard.tsx')
  assert.match(tableCard, /@\/components\/ui\/card/)
  assert.match(tableCard, /@\/components\/ui\/table/)
})

test('StatCard exposes the semantic tone set and keeps the legacy props', () => {
  const code = read('components/shared/StatCard.tsx')
  const tones = read('components/shared/tones.ts')
  assert.match(code, /from '\.\/tones'/)
  for (const tone of ['primary', 'success', 'warning', 'destructive', 'info', 'neutral']) {
    assert.match(tones, new RegExp(`\\b${tone}\\b`), `tones.ts needs the ${tone} tone`)
  }
  assert.match(code, /tabular-nums/)
  assert.match(code, /\btone\b/)
  assert.match(code, /\bcolor\?:/, 'StatCard must keep the legacy color prop')
  assert.match(code, /\bgradient\?:/, 'StatCard must keep the legacy gradient prop')
})

test('shared base components carry no hex colors or gradient chrome', () => {
  for (const file of [
    'components/shared/StatCard.tsx',
    'components/shared/tones.ts',
    'components/shared/DataTable.tsx',
    'components/shared/LoadingSpinner.tsx',
    'components/shared/FileUploader.tsx',
    'components/shared/ConfirmActionDialog.tsx',
    'components/shared/ConfirmAlertDialog.tsx',
    'components/shared/PageHeader.tsx',
    'components/shared/StatusBadge.tsx',
    'components/shared/EmptyState.tsx',
    'components/shared/TableCard.tsx',
    'components/layout/Sidebar.tsx',
    'components/layout/Header.tsx',
    'components/layout/Layout.tsx',
    'components/layout/Logo.tsx',
  ]) {
    assertNoLegacyChrome(file)
  }
})

test('FileUploader can show coss Progress', () => {
  const code = read('components/shared/FileUploader.tsx')
  assert.match(code, /@\/components\/ui\/progress/)
  assert.match(code, /progress\?:/)
})

test('ConfirmActionDialog keeps importing ui/dialog', () => {
  const code = read('components/shared/ConfirmActionDialog.tsx')
  assert.match(code, /@\/components\/ui\/dialog/)
  assert.match(code, /export function ConfirmActionDialog/)
})

test('legacy utility classes used by pages stay in index.css', () => {
  const css = readFileSync(join(src, 'index.css'), 'utf8')
  for (const cls of ['card-3d', 'card-3d-static', 'gradient-navy', 'gradient-stat-blue', 'gradient-stat-green', 'animate-fade-in-up', 'animate-count-up']) {
    assert.match(css, new RegExp(`\\.${cls}\\b`), `index.css must keep .${cls}`)
  }
})

test('Input and Textarea document and implement the inner-control class path', () => {
  for (const file of ['components/ui/input.tsx', 'components/ui/textarea.tsx']) {
    const code = read(file)
    assert.match(code, /\binputClassName\?:\s*string/, `${file} must accept inputClassName`)
    const mentions = code.match(/^\s+inputClassName,\s*$/gm) ?? []
    assert.ok(mentions.length >= 2, `${file} must destructure inputClassName and merge it into the inner control`)
  }
  const input = read('components/ui/input.tsx')
  const header = input.slice(0, input.indexOf('import'))
  assert.match(header, /wrapper/i, 'input.tsx must document the wrapper rule at the top')
  assert.match(header, /inputClassName/)
})

test('collapsed sidebar rail does not clip the brand badge', () => {
  const code = read('components/layout/Sidebar.tsx')
  const header = code.slice(code.indexOf('<SidebarHeader'), code.indexOf('</SidebarHeader>'))
  assert.doesNotMatch(header, /\bpx-3\b/, 'brand header must not pad past the 3rem rail')
  assert.match(header, /group-data-\[collapsible=icon\]:/, 'brand header must adapt to the icon rail')
})
