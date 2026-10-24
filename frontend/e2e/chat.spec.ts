import { expect, test } from '@playwright/test'

import { FakeChatApi, PNG_BYTES } from './support/chat'

const png = (name: string) => ({ name, mimeType: 'image/png', buffer: PNG_BYTES })
const pdf = (name: string, size = 1200) => ({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(size, 0x25) })

test('docente sends a message with an attachment to Administración', async ({ page }) => {
  const chat = new FakeChatApi()
  await chat.install(page, 'docente')
  await page.goto('/portal/chat')

  await expect(page.getByRole('heading', { name: 'Administración' })).toBeVisible()
  await expect(page.getByText('Aún no hay mensajes')).toBeVisible()

  const composer = page.getByRole('textbox', { name: 'Escribir mensaje' })
  const send = page.getByRole('button', { name: 'Enviar mensaje' })
  await expect(send).toBeDisabled()
  await composer.fill('Hola, adjunto mi carnet')
  await expect(page.getByText('23/4000')).toBeVisible()

  await page.getByTestId('chat-file-input').setInputFiles(png('carnet.png'))
  await expect(page.getByRole('list', { name: 'Archivos por enviar' }).getByText('carnet.png')).toBeVisible()
  await send.click()

  const log = page.getByRole('log', { name: 'Mensajes de la conversación' })
  await expect(log.getByText('Hola, adjunto mi carnet')).toBeVisible()
  await expect(log.getByRole('button', { name: 'Ver imagen carnet.png' })).toBeVisible()
  await expect(composer).toHaveValue('')
  await expect(page.getByRole('list', { name: 'Archivos por enviar' })).toHaveCount(0)
  await expect(page.getByText('0/4000')).toBeVisible()

  expect(chat.sent).toEqual([
    { path: '/chat/me/messages', body: 'Hola, adjunto mi carnet', files: [{ name: 'carnet.png', type: 'image/png' }] },
  ])
  // The attachment is private: it is fetched with the auth header, not linked.
  expect(chat.attachmentAuth.length).toBeGreaterThan(0)
  expect(new Set(chat.attachmentAuth)).toEqual(new Set(['Bearer e2e-docente-token']))
  await expect(log.locator('a[href*="/api/"]')).toHaveCount(0)

  await log.getByRole('button', { name: 'Ver imagen carnet.png' }).click()
  await expect(page.getByRole('dialog').getByRole('img', { name: 'carnet.png' })).toBeVisible()
})

test('Enter sends and Shift+Enter adds a new line', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Keyboard behavior')
  const chat = new FakeChatApi()
  await chat.install(page, 'docente')
  await page.goto('/portal/chat')

  const composer = page.getByRole('textbox', { name: 'Escribir mensaje' })
  await composer.fill('primera línea')
  await composer.press('Shift+Enter')
  await composer.pressSequentially('segunda línea')
  expect(chat.sent).toHaveLength(0)
  await composer.press('Enter')

  await expect(page.getByRole('log').getByText('segunda línea')).toBeVisible()
  expect(chat.sent.map((m) => m.body)).toEqual(['primera línea\nsegunda línea'])
})

test('docente sees the admin reply after a poll and polling pauses while the tab is hidden', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Polling behavior')
  const chat = new FakeChatApi()
  chat.push('docente', 'Buenas, tengo una consulta', 5)
  await chat.install(page, 'docente')
  await page.clock.install()
  await page.goto('/portal/chat')

  const log = page.getByRole('log', { name: 'Mensajes de la conversación' })
  await expect(log.getByText('Buenas, tengo una consulta')).toBeVisible()
  expect(chat.threadRequests[0].after).toBeNull()

  chat.push('admin', 'Hola Ana, ya lo revisé', 0)
  await page.clock.runFor(5_500)
  await expect(log.getByText('Hola Ana, ya lo revisé')).toBeVisible()
  await expect(log.getByText('Buenas, tengo una consulta')).toBeVisible()
  // The poll asks only for what is new and appends it.
  expect(chat.threadRequests.at(-1)?.after).toBe('1')
  await expect.poll(() => chat.readCalls.length).toBeGreaterThan(0)

  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' })
    document.dispatchEvent(new Event('visibilitychange', { bubbles: true }))
  })
  const before = chat.threadRequests.length
  chat.push('admin', 'Mensaje mientras la pestaña está oculta', 0)
  await page.clock.runFor(30_000)
  expect(chat.threadRequests.length).toBe(before)
  await expect(log.getByText('Mensaje mientras la pestaña está oculta')).toHaveCount(0)

  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' })
    document.dispatchEvent(new Event('visibilitychange', { bubbles: true }))
  })
  await expect(log.getByText('Mensaje mientras la pestaña está oculta')).toBeVisible()
})

test('admin opens a conversation from the inbox and the unread badge clears', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop two-pane inbox')
  const chat = new FakeChatApi()
  chat.push('admin', 'Te respondo mañana', 30)
  chat.push('docente', 'Necesito mi certificado', 10)
  chat.push('docente', 'Es urgente', 9)
  await chat.install(page, 'admin')
  await page.goto('/chat')

  const sidebar = page.getByRole('navigation', { name: 'Secciones' })
  await sidebar.getByText('Docentes y académico').click()
  await expect(sidebar.getByRole('link', { name: /Mensajes/ })).toBeVisible()
  await expect(sidebar.getByText('2 mensajes sin leer')).toBeVisible()

  const inbox = page.getByRole('region', { name: 'Conversaciones' })
  const row = inbox.getByRole('button', { name: /Ana Docente/ })
  await expect(row).toContainText('Es urgente')
  await expect(row.getByText('2 mensajes sin leer')).toBeAttached()
  await expect(page.getByText('Selecciona una conversación')).toBeVisible()

  await row.click()
  await expect(page).toHaveURL(/\/chat\?c=7$/)
  const log = page.getByRole('log', { name: 'Mensajes de la conversación' })
  await expect(log.getByText('Necesito mi certificado')).toBeVisible()
  await expect(log.getByText('Mensajes nuevos')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ana Docente' })).toBeVisible()

  await expect.poll(() => chat.readCalls).toEqual(['/chat/conversations/7/read'])
  await expect(row.getByText('2 mensajes sin leer')).toHaveCount(0)
  await expect(sidebar.getByText('2 mensajes sin leer')).toHaveCount(0)

  await page.getByRole('textbox', { name: 'Escribir mensaje' }).fill('Ya está listo')
  await page.getByRole('button', { name: 'Enviar mensaje' }).click()
  await expect(log.getByText('Ya está listo')).toBeVisible()
  expect(chat.sent).toEqual([{ path: '/chat/conversations/7/messages', body: 'Ya está listo', files: [] }])

  await inbox.getByLabel('Buscar conversación').fill('zzz')
  await expect(inbox.getByText('Ninguna conversación coincide con la búsqueda.')).toBeVisible()
})

test('a fourth file, an oversized file and a wrong type are rejected on the client', async ({ page }) => {
  const chat = new FakeChatApi()
  await chat.install(page, 'docente')
  await page.goto('/portal/chat')

  const input = page.getByTestId('chat-file-input')
  const chips = page.getByRole('list', { name: 'Archivos por enviar' }).getByRole('listitem')
  await input.setInputFiles([pdf('uno.pdf'), pdf('dos.pdf'), pdf('tres.pdf')])
  await expect(chips).toHaveCount(3)

  await input.setInputFiles(pdf('cuatro.pdf'))
  await expect(page.getByRole('alert')).toHaveText('Solo puedes adjuntar hasta 3 archivos por mensaje; «cuatro.pdf» no se agregó')
  await expect(chips).toHaveCount(3)

  await page.getByRole('button', { name: 'Quitar tres.pdf' }).click()
  await expect(chips).toHaveCount(2)
  await input.setInputFiles({ name: 'enorme.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(10 * 1024 * 1024 + 1, 0x25) })
  await expect(page.getByRole('alert')).toHaveText('«enorme.pdf» supera el máximo de 10 MB por archivo')
  await input.setInputFiles({ name: 'nota.txt', mimeType: 'text/plain', buffer: Buffer.from('hola') })
  await expect(page.getByRole('alert')).toHaveText('«nota.txt»: solo se permiten archivos PDF, JPEG, PNG o WEBP')
  await expect(chips).toHaveCount(2)
  expect(chat.sent).toHaveLength(0)
})

test('the backend detail is shown when sending fails', async ({ page }) => {
  const chat = new FakeChatApi()
  await chat.install(page, 'docente')
  await page.route('**/api/chat/me/messages', (route) =>
    route.fulfill({ status: 413, json: { detail: 'El archivo supera el máximo de 10 MB' } }),
  )
  await page.goto('/portal/chat')

  const composer = page.getByRole('textbox', { name: 'Escribir mensaje' })
  await composer.fill('con error')
  await page.getByRole('button', { name: 'Enviar mensaje' }).click()
  await expect(page.getByRole('alert')).toHaveText('El archivo supera el máximo de 10 MB')
  await expect(composer).toHaveValue('con error')
  await expect(composer).toBeEnabled()
})

test('mobile: the list comes first, then the thread with a back button', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-chromium', 'Mobile inbox flow')
  const chat = new FakeChatApi()
  chat.push('docente', 'Hola administración', 10)
  await chat.install(page, 'admin')
  await page.goto('/chat')

  const inbox = page.getByRole('region', { name: 'Conversaciones' })
  await expect(inbox).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Escribir mensaje' })).toHaveCount(0)

  await inbox.getByRole('button', { name: /Ana Docente/ }).click()
  await expect(page.getByRole('textbox', { name: 'Escribir mensaje' })).toBeVisible()
  await expect(page.getByRole('log').getByText('Hola administración')).toBeVisible()
  await expect(inbox).toBeHidden()

  await page.getByRole('button', { name: 'Volver a conversaciones' }).click()
  await expect(inbox).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Escribir mensaje' })).toHaveCount(0)
  await expect(page).toHaveURL(/\/chat$/)
})
