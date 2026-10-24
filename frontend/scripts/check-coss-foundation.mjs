import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import test from 'node:test'

const root = resolve(import.meta.dirname, '..')
const src = join(root, 'src')

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    return /\.(ts|tsx)$/.test(name) ? [path] : []
  })
}

function readUi(name) {
  const path = join(src, 'components/ui', `${name}.tsx`)
  assert.ok(existsSync(path), `src/components/ui/${name}.tsx is missing`)
  return readFileSync(path, 'utf8')
}

function assertExports(name, expected) {
  const code = readUi(name)
  const exported = new Set()
  for (const match of code.matchAll(/export\s+(?:declare\s+)?(?:async\s+)?(?:function|const|class)\s+(\w+)/g)) {
    exported.add(match[1])
  }
  for (const block of code.matchAll(/export\s*\{([^}]*)\}/g)) {
    for (const part of block[1].split(',')) {
      const alias = part.trim().split(/\s+as\s+/).pop()
      if (alias) exported.add(alias.replace(/^type\s+/, ''))
    }
  }
  for (const symbol of expected) {
    assert.ok(exported.has(symbol), `ui/${name}.tsx must export ${symbol}`)
  }
}

test('no source file imports Radix', () => {
  const offenders = sourceFiles(src)
    .filter((file) => /from\s+['"](?:radix-ui|@radix-ui\/[^'"]+)['"]/.test(readFileSync(file, 'utf8')))
    .map((file) => relative(root, file))
  assert.deepEqual(offenders, [])
})

test('coss primitives requested for the UI upgrade exist with the expected exports', () => {
  assertExports('alert-dialog', ['AlertDialog', 'AlertDialogPopup', 'AlertDialogTitle', 'AlertDialogDescription'])
  assertExports('dialog', ['Dialog', 'DialogPopup', 'DialogPanel', 'DialogHeader', 'DialogFooter', 'DialogTitle'])
  assertExports('sheet', ['Sheet', 'SheetPopup', 'SheetTrigger', 'SheetTitle'])
  assertExports('combobox', ['Combobox', 'ComboboxInput', 'ComboboxPopup', 'ComboboxItem', 'ComboboxList'])
  assertExports('autocomplete', ['Autocomplete', 'AutocompleteInput', 'AutocompletePopup', 'AutocompleteItem'])
  assertExports('progress', ['Progress'])
  assertExports('field', ['Field', 'FieldLabel', 'FieldError', 'FieldDescription'])
  assertExports('form', ['Form'])
  assertExports('skeleton', ['Skeleton'])
  assertExports('table', ['Table', 'TableHeader', 'TableBody', 'TableRow', 'TableHead', 'TableCell'])
  assertExports('select', ['Select', 'SelectTrigger', 'SelectPopup', 'SelectItem', 'SelectValue'])
  assertExports('menu', ['Menu', 'MenuTrigger', 'MenuPopup', 'MenuItem'])
  assertExports('sidebar', ['SidebarProvider', 'Sidebar', 'SidebarTrigger', 'SidebarMenuButton', 'useSidebar'])
})

test('primitives needed by @coss/chat and the shell exist', () => {
  for (const name of [
    'button', 'input', 'label', 'badge', 'card', 'tabs', 'tooltip', 'popover', 'scroll-area', 'separator',
    'collapsible', 'empty', 'toggle', 'toolbar', 'avatar',
  ]) {
    readUi(name)
  }
})

test('Base UI primitives use the render prop, not asChild', () => {
  const offenders = sourceFiles(src)
    .filter((file) => /\basChild\b/.test(readFileSync(file, 'utf8')))
    .map((file) => relative(root, file))
  assert.deepEqual(offenders, [])
})

test('package.json drops Radix and pins Base UI', () => {
  const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
  const deps = { ...pkg.dependencies, ...pkg.devDependencies }
  assert.equal(deps['radix-ui'], undefined)
  assert.equal(Object.keys(deps).filter((name) => name.startsWith('@radix-ui/')).length, 0)
  assert.equal(deps['@base-ui/react'], '1.8.0')
})

test('index.css defines the coss status tokens', () => {
  const css = readFileSync(join(src, 'index.css'), 'utf8')
  for (const token of ['--success', '--warning', '--info', '--destructive-foreground', '--sidebar']) {
    assert.match(css, new RegExp(`${token}\\s*:`), `index.css must define ${token}`)
  }
  for (const token of ['--color-success', '--color-warning', '--color-info', '--color-destructive-foreground']) {
    assert.match(css, new RegExp(`${token}\\s*:`), `index.css must map ${token} in @theme`)
  }
})
