import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

// S1-S3 (T8): Cursos de verano e invierno, Login and Cambiar contraseña in the editorial language of artboard 03.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const { seasonTone, seatsMeter, statusTone, enrollBlockReason } = await import('../src/components/student/courses/course-season.ts')
const { passwordRules, passwordStrength, eyeLabel } = await import('../src/components/student/access/student-access.ts')

const course = (patch = {}) => ({
  free: 12, capacity: 30, is_full: false, is_enrollment_open: true, status: 'open',
  enrollment_starts_on: '2027-01-10', enrollment_ends_on: '2027-01-20', ...patch,
})

test('S2: season tone tells summer (VER), winter (INV) and any other term apart', () => {
  assert.equal(seasonTone('VER/2027'), 'summer')
  assert.equal(seasonTone('INV/2026'), 'winter')
  for (const other of ['', 'I/2027', 'ver/2027', 'OTO/2027']) assert.equal(seasonTone(other), 'other', other)
})

test('S2: the seats meter reads "N cupos libres" with the free seats as value', () => {
  assert.deepEqual(seatsMeter(course()), {
    value: 12, max: 30, tone: 'default', label: '12 cupos libres', valueText: '12 de 30 cupos libres', few: false,
  })
  assert.equal(seatsMeter(course({ free: 1 })).label, '1 cupo libre')
})

test('S2: few seats warn at 20 % or less, and a full course reads "Sin cupos" with an empty meter', () => {
  const few = seatsMeter(course({ free: 6, capacity: 30 }))
  assert.equal(few.tone, 'warn')
  assert.equal(few.few, true)
  assert.equal(seatsMeter(course({ free: 7, capacity: 30 })).few, false)
  const full = seatsMeter(course({ free: 0, is_full: true }))
  assert.deepEqual(full, { value: 0, max: 30, tone: 'bad', label: 'Sin cupos', valueText: '0 de 30 cupos libres', few: false })
  assert.equal(seatsMeter(course({ free: 0, is_full: false })).label, 'Sin cupos', 'no free seat is full even if the flag lags')
  assert.equal(seatsMeter(course({ free: 40, capacity: 30 })).value, 30, 'free seats never exceed the capacity')
  assert.equal(seatsMeter(course({ capacity: 0, free: 0, is_full: true })).max, 1, 'an empty capacity keeps a valid meter range')
})

test('S1: the status badge maps the existing variants to editorial tones', () => {
  assert.deepEqual(['success', 'info', 'warning', 'outline', 'error'].map(statusTone), ['ok', 'info', 'warn', 'muted', 'bad'])
})

test('S1: a blocked enroll button always has a reason', () => {
  assert.equal(enrollBlockReason(course(), '2027-01-15'), null)
  assert.equal(enrollBlockReason(course({ is_full: true, free: 0 }), '2027-01-15'), 'full')
  assert.equal(enrollBlockReason(course({ is_enrollment_open: false }), '2027-01-05'), 'scheduled')
  assert.equal(enrollBlockReason(course({ is_enrollment_open: false }), '2027-01-25'), 'expired')
  assert.equal(enrollBlockReason(course({ status: 'closed', is_enrollment_open: false }), '2027-01-15'), 'closed')
})

test('S3: the password rules and labels are the ones the portal always had', () => {
  assert.deepEqual(passwordRules('', '').map((rule) => rule.label), [
    'Al menos 8 caracteres', 'Una mayúscula', 'Una minúscula', 'Un número', 'Las dos contraseñas coinciden',
  ])
  assert.deepEqual(passwordRules('', '').map((rule) => rule.passes), [false, false, false, false, false])
  assert.deepEqual(passwordRules('Abcdefg1', 'Abcdefg1').map((rule) => rule.passes), [true, true, true, true, true])
  assert.deepEqual(passwordRules('abcdefg1', 'abcdefg1').map((rule) => rule.passes), [true, false, true, true, true])
  assert.equal(passwordRules('', '')[4].passes, false, 'two empty passwords do not match')
  assert.equal(passwordRules('Abcdefg1', 'Abcdefg2')[4].passes, false)
})

test('S2: the strength meter counts the four character rules and stays empty without a password', () => {
  assert.deepEqual(passwordStrength(''), { score: 0, label: '', tone: 'default' })
  assert.deepEqual(passwordStrength('a'), { score: 1, label: 'Débil', tone: 'bad' })
  assert.deepEqual(passwordStrength('abcdefgh'), { score: 2, label: 'Regular', tone: 'warn' })
  assert.deepEqual(passwordStrength('Abcdefgh'), { score: 3, label: 'Buena', tone: 'warn' })
  assert.deepEqual(passwordStrength('Abcdefg1'), { score: 4, label: 'Fuerte', tone: 'ok' })
})

test('S2: the eye toggle names the action (one field or all of them)', () => {
  assert.equal(eyeLabel(false), 'Mostrar contraseña')
  assert.equal(eyeLabel(true), 'Ocultar contraseña')
  assert.equal(eyeLabel(false, true), 'Mostrar contraseñas')
  assert.equal(eyeLabel(true, true), 'Ocultar contraseñas')
})

test('S1: Cursos has no divide-y lists and renders its sheets, meter, figure and tooltip', () => {
  const page = read('src/pages/student/StudentIntensivePage.tsx')
  const card = read('src/components/student/courses/CourseCard.tsx')
  for (const code of [page, card]) assert.doesNotMatch(code, /divide-y|<ul className="divide/)
  assert.match(page, /import '@\/styles\/student\/courses\.css'/)
  assert.match(card, /<Sheet\b/)
  assert.match(card, /<Meter\b/)
  assert.match(card, /<DisplayFigure\b/)
  assert.match(card, /<InfoTip\b/)
  assert.ok(card.includes('precio estimado') || card.includes('Estimado'), 'the price tip explains the estimate')
  assert.match(page, /active:scale-95/, 'the CTA press feedback')
  assert.match(page, /\b(?:Sun|Snowflake)\b/, 'the season icon')
})

test('S3: Cursos keeps one PageHeader h1, the section titles and the confirmation', () => {
  const page = read('src/pages/student/StudentIntensivePage.tsx')
  assert.equal((page.match(/<PageHeader as="h1"/g) ?? []).length, 1)
  for (const text of ['Cursos de verano e invierno', 'Mis inscripciones', 'Cursos disponibles para vos']) assert.ok(page.includes(text), text)
  assert.match(page, /<ConfirmAlertDialog\b/)
  assert.match(page, /<EmptyState\b[^>]*icon=\{/)
  assert.match(page, /<Skeleton\b/)
})

test('S2: the season colors are tokens in courses.css (summer warm, winter cool, other neutral), never in the TSX', () => {
  const css = read('src/styles/student/courses.css')
  for (const season of ['summer', 'winter', 'other']) assert.match(css, new RegExp(`\\.cc-card--${season}\\b`), season)
  assert.match(css, /\.dark\b/, 'dark mode has its own season tokens')
  assert.match(css, /prefers-reduced-motion: reduce/)
  for (const path of [
    'src/pages/student/StudentIntensivePage.tsx', 'src/components/student/courses/CourseCard.tsx',
    'src/pages/student/StudentLoginPage.tsx', 'src/pages/student/StudentChangePasswordPage.tsx',
  ]) assert.deepEqual(read(path).match(/#[0-9a-fA-F]{3,8}\b|(?:linear|radial)-gradient|\brgba?\(/g) ?? [], [], path)
})

for (const [name, icon] of [['StudentLoginPage', 'IdCard'], ['StudentChangePasswordPage', 'Lock']]) {
  test(`S2: ${name} wears the student font and the glass sheet, with its own access components`, () => {
    const code = read(`src/pages/student/${name}.tsx`)
    assert.match(code, /<main className="[^"]*\bfont-student\b/, 'the root applies font-student')
    assert.match(code, /import '@\/styles\/student\/access\.css'/)
    assert.match(code, /<AccessCard\b/)
    assert.ok(code.includes(icon), `${name} uses ${icon}`)
    assert.doesNotMatch(code, /ForceChangePasswordPage/, 'staff password parts are not reused')
  })
}

test('S2: the password field has leading icon, an eye toggle with InfoTip, and the shake respects reduced motion', () => {
  const field = read('src/components/student/access/StudentPasswordField.tsx')
  assert.match(field, /<InfoTip\b/)
  assert.match(field, /eyeLabel\(/)
  assert.match(field, /aria-pressed/)
  assert.match(field, /Lock|IdCard|KeyRound/)
  const css = read('src/styles/student/access.css')
  assert.match(css, /\.sa-card\[data-shake='true'\] \{ animation: sa-shake/)
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.sa-card\[data-shake='true'\][\s\S]*animation: none/)
})

test('S2: Cambiar contraseña shows the animated rule checklist, the Meter strength and the short label with its tip', () => {
  const page = read('src/pages/student/StudentChangePasswordPage.tsx')
  assert.match(page, /<PasswordChecklist\b/)
  assert.match(page, /<PasswordStrength\b/)
  assert.match(page, /<InfoTip\b/)
  assert.ok(page.includes('la temporal si es tu primer ingreso'), 'the long label moved into the tip')
  assert.ok(!/FieldLabel[^>]*>[^<]*la temporal si es tu primer ingreso/.test(page), 'the label itself is short')
  assert.match(read('src/components/student/access/PasswordStrength.tsx'), /<Meter\b/)
  assert.match(read('src/components/student/access/PasswordChecklist.tsx'), /data-ok/)
})

test('S3: the shared ForceChangePasswordPage (staff) is untouched', () => {
  const path = 'src/pages/ForceChangePasswordPage.tsx'
  assert.ok(existsSync(resolve(root, path)))
  const diff = execFileSync('git', ['diff', 'HEAD', '--', path], { cwd: root, encoding: 'utf8' })
  assert.equal(diff, '', 'no change against HEAD')
})

test('S3: the API calls, redirects and error messages of the access pages are kept', () => {
  const login = read('src/pages/student/StudentLoginPage.tsx')
  assert.match(login, /useStudentLogin\(\)/)
  assert.ok(login.includes("navigate(session.must_change_password ? '/estudiante/cambiar-clave' : '/estudiante', { replace: true })"))
  assert.ok(login.includes("'No se pudo iniciar sesión. Intentá de nuevo.'"))
  assert.ok(login.includes('document_number: documentNumber.trim()'))
  const change = read('src/pages/student/StudentChangePasswordPage.tsx')
  assert.ok(change.includes('useStudentChangePassword()') && change.includes('useStudentMe()'))
  assert.ok(change.includes("<Navigate to=\"/estudiante/login\" replace />"))
  assert.ok(change.includes("navigate('/estudiante', { replace: true })"))
  assert.ok(change.includes("'No se pudo cambiar la contraseña.'"))
  assert.ok(change.includes('current_password: current, new_password: next'))
})
