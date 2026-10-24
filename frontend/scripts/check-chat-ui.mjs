import assert from 'node:assert/strict'
import test from 'node:test'

import {
  CHAT_MAX_BODY_LENGTH,
  CHAT_MAX_FILES,
  apiErrorMessage,
  applyThreadPage,
  buildThreadItems,
  canSendMessage,
  formatFileSize,
  groupByDay,
  mergeMessages,
  oldestMessageId,
  unreadDividerMessageId,
  validateAttachments,
} from '../src/lib/chat.ts'

const MB = 1024 * 1024
const file = (name, type, size = 1000) => ({ name, type, size })
const pdf = (name = 'a.pdf', size) => file(name, 'application/pdf', size)

function message(id, role = 'admin', createdAt = '2026-10-24T14:00:00', extra = {}) {
  return {
    id,
    conversation_id: 1,
    sender_user_id: role === 'admin' ? 1 : 42,
    sender_role: role,
    sender_name: role === 'admin' ? 'Administración' : 'Ana',
    body: `m${id}`,
    created_at: createdAt,
    attachments: [],
    ...extra,
  }
}

test('limits mirror the backend contract', () => {
  assert.equal(CHAT_MAX_BODY_LENGTH, 4000)
  assert.equal(CHAT_MAX_FILES, 3)
})

test('attachments: PDF, JPEG, PNG and WEBP are accepted', () => {
  const picked = [pdf(), file('b.jpg', 'image/jpeg'), file('c.png', 'image/png')]
  const result = validateAttachments([], picked)
  assert.deepEqual(result.accepted, picked)
  assert.deepEqual(result.errors, [])
  assert.deepEqual(validateAttachments([], [file('d.webp', 'image/webp')]).errors, [])
})

test('attachments: other types are rejected by name with a Spanish message', () => {
  const result = validateAttachments([], [file('virus.exe', 'application/x-msdownload'), file('doc.docx', '')])
  assert.deepEqual(result.accepted, [])
  assert.deepEqual(result.errors, [
    '«virus.exe»: solo se permiten archivos PDF, JPEG, PNG o WEBP',
    '«doc.docx»: solo se permiten archivos PDF, JPEG, PNG o WEBP',
  ])
})

test('attachments: a file over 10 MB is rejected, exactly 10 MB is accepted', () => {
  const ok = validateAttachments([], [pdf('ok.pdf', 10 * MB)])
  assert.equal(ok.accepted.length, 1)
  const big = validateAttachments([], [pdf('big.pdf', 10 * MB + 1)])
  assert.deepEqual(big.accepted, [])
  assert.deepEqual(big.errors, ['«big.pdf» supera el máximo de 10 MB por archivo'])
})

test('attachments: a fourth file is rejected and the first three are kept', () => {
  const existing = [pdf('1.pdf'), pdf('2.pdf')]
  const result = validateAttachments(existing, [pdf('3.pdf'), pdf('4.pdf')])
  assert.deepEqual(result.accepted.map((f) => f.name), ['3.pdf'])
  assert.deepEqual(result.errors, ['Solo puedes adjuntar hasta 3 archivos por mensaje; «4.pdf» no se agregó'])
})

test('attachments: the 20 MB total per message is enforced across picks', () => {
  const existing = [pdf('a.pdf', 10 * MB), pdf('b.pdf', 9 * MB)]
  const result = validateAttachments(existing, [pdf('c.pdf', 2 * MB)])
  assert.deepEqual(result.accepted, [])
  assert.deepEqual(result.errors, ['«c.pdf» haría que los archivos del mensaje superen los 20 MB en total'])
  assert.equal(validateAttachments(existing, [pdf('d.pdf', 1 * MB)]).accepted.length, 1)
})

test('attachments: valid files are kept when another one in the same pick fails', () => {
  const result = validateAttachments([], [pdf('ok.pdf'), file('x.gif', 'image/gif')])
  assert.deepEqual(result.accepted.map((f) => f.name), ['ok.pdf'])
  assert.equal(result.errors.length, 1)
})

test('canSendMessage needs text or a file, at most 4000 characters, and no send in flight', () => {
  assert.equal(canSendMessage('hola', 0, false), true)
  assert.equal(canSendMessage('   ', 0, false), false)
  assert.equal(canSendMessage('', 1, false), true)
  assert.equal(canSendMessage('a'.repeat(4000), 0, false), true)
  assert.equal(canSendMessage('a'.repeat(4001), 0, false), false)
  assert.equal(canSendMessage('hola', 0, true), false)
})

test('mergeMessages appends polled messages, dedupes by id and keeps id order', () => {
  const current = [message(1), message(2)]
  const merged = mergeMessages(current, [message(2), message(4), message(3)])
  assert.deepEqual(merged.map((m) => m.id), [1, 2, 3, 4])
  assert.equal(mergeMessages(current, []), current)
  assert.deepEqual(current.map((m) => m.id), [1, 2], 'the input is not mutated')
})

test('mergeMessages lets the incoming copy of a duplicate win', () => {
  const merged = mergeMessages([message(1)], [message(1, 'admin', '2026-10-24T14:00:00', { body: 'editado' })])
  assert.equal(merged.length, 1)
  assert.equal(merged[0].body, 'editado')
})

const conversation = { id: 1, teacher_ci: '7001', teacher_name: 'Ana', unread_count: 0, last_message_at: null }
const thread = (ids, hasMore, extra = {}) => ({ conversation: { ...conversation, ...extra }, messages: ids.map((id) => message(id)), has_more: hasMore })
const idsOf = (value) => value.messages.map((m) => m.id)

test('oldestMessageId is the first loaded id, or 0 when nothing is loaded', () => {
  assert.equal(oldestMessageId([message(5), message(6)]), 5)
  assert.equal(oldestMessageId([]), 0)
})

test('applyThreadPage: the first load is taken as is and a missing has_more means false', () => {
  assert.deepEqual(applyThreadPage(undefined, thread([6, 7], true), 'poll'), thread([6, 7], true))
  const legacy = { conversation, messages: [message(1)] }
  assert.equal(applyThreadPage(undefined, legacy, 'poll').has_more, false)
})

test('applyThreadPage: an older page is prepended in id order, deduped, and brings the new has_more', () => {
  const current = thread([6, 7, 8], true)
  const merged = applyThreadPage(current, thread([4, 5, 6], false), 'older')
  assert.deepEqual(idsOf(merged), [4, 5, 6, 7, 8])
  assert.equal(merged.has_more, false)
  assert.deepEqual(idsOf(current), [6, 7, 8], 'the cached thread is not mutated')
  assert.equal(applyThreadPage(current, thread([3, 4, 5], true), 'older').has_more, true)
})

test('applyThreadPage: an older page keeps the cached conversation (its unread counter is current)', () => {
  const current = thread([6, 7], true, { unread_count: 3 })
  const merged = applyThreadPage(current, thread([4, 5], true, { unread_count: 9 }), 'older')
  assert.equal(merged.conversation.unread_count, 3)
})

test('applyThreadPage: a poll appends newer messages and never resets has_more', () => {
  const current = thread([6, 7], true)
  const polled = applyThreadPage(current, thread([8], false, { unread_count: 1 }), 'poll')
  assert.deepEqual(idsOf(polled), [6, 7, 8])
  assert.equal(polled.has_more, true, 'a poll reports no older messages and must not hide the control')
  assert.equal(polled.conversation.unread_count, 1)
  assert.equal(applyThreadPage(thread([1, 2], false), thread([3], true), 'poll').has_more, false)
})

test('applyThreadPage: an empty poll keeps every message and the flag', () => {
  const current = thread([6, 7], true)
  const polled = applyThreadPage(current, thread([], false), 'poll')
  assert.deepEqual(idsOf(polled), [6, 7])
  assert.equal(polled.has_more, true)
})

test('unread divider sits before the first of the unread incoming messages', () => {
  const messages = [message(1, 'admin'), message(2, 'docente'), message(3, 'admin'), message(4, 'docente'), message(5, 'admin')]
  assert.equal(unreadDividerMessageId(messages, 'docente', 2), 3)
  assert.equal(unreadDividerMessageId(messages, 'docente', 1), 5)
  assert.equal(unreadDividerMessageId(messages, 'admin', 1), 4)
})

test('unread divider is absent with nothing unread and falls back to the oldest loaded incoming message', () => {
  const messages = [message(1, 'admin'), message(2, 'docente')]
  assert.equal(unreadDividerMessageId(messages, 'docente', 0), null)
  assert.equal(unreadDividerMessageId([], 'docente', 3), null)
  assert.equal(unreadDividerMessageId(messages, 'docente', 5), 1)
})

test('thread items add a date pill per Bolivia day, group consecutive senders and place the divider', () => {
  const now = new Date('2026-10-24T20:00:00Z')
  const messages = [
    message(1, 'admin', '2026-10-23T12:00:00'),
    message(2, 'docente', '2026-10-24T13:00:00'),
    message(3, 'admin', '2026-10-24T13:01:00'),
    message(4, 'admin', '2026-10-24T13:02:00'),
  ]
  const items = buildThreadItems(messages, 'docente', unreadDividerMessageId(messages, 'docente', 2), now)
  assert.deepEqual(
    items.map((item) => (item.kind === 'message' ? `m${item.message.id}${item.side[0]}${item.grouped ? '+' : ''}` : item.kind)),
    ['date', 'm1i', 'date', 'm2o', 'unread', 'm3i', 'm4i+'],
  )
  assert.deepEqual(items.filter((i) => i.kind === 'date').map((i) => i.label), ['Ayer', 'Hoy'])
})

test('thread items regroup after a date change and keep ids as stable keys', () => {
  const now = new Date('2026-10-24T20:00:00Z')
  const messages = [message(1, 'admin', '2026-10-24T03:59:00'), message(2, 'admin', '2026-10-24T04:01:00')]
  const items = buildThreadItems(messages, 'admin', null, now)
  const rendered = items.filter((i) => i.kind === 'message')
  assert.equal(rendered[1].grouped, false)
  assert.equal(new Set(items.map((i) => i.key)).size, items.length)
})

test('groupByDay keeps the divider and messages under their own date pill', () => {
  const now = new Date('2026-10-24T20:00:00Z')
  const messages = [
    message(1, 'admin', '2026-10-23T12:00:00'),
    message(2, 'docente', '2026-10-24T13:00:00'),
    message(3, 'admin', '2026-10-24T13:01:00'),
  ]
  const days = groupByDay(buildThreadItems(messages, 'docente', 3, now))
  assert.deepEqual(days.map((d) => d.label), ['Ayer', 'Hoy'])
  assert.deepEqual(days.map((d) => d.items.map((i) => i.key)), [['message-1'], ['message-2', 'unread', 'message-3']])
  assert.deepEqual(groupByDay([]), [])
})

test('timestamps are naive UTC and the day is computed in Bolivia time', () => {
  const now = new Date('2026-10-24T20:00:00Z')
  // 01:00 UTC on the 24th is 21:00 on the 23rd in La Paz.
  const items = buildThreadItems([message(1, 'admin', '2026-10-24T01:00:00')], 'admin', null, now)
  assert.equal(items[0].label, 'Ayer')
})

test('apiErrorMessage prefers the backend detail', () => {
  const axiosLike = (data) => ({ isAxiosError: true, response: { status: 422, data } })
  assert.equal(apiErrorMessage(axiosLike({ detail: 'Escribe un mensaje o adjunta un archivo' }), 'x'), 'Escribe un mensaje o adjunta un archivo')
  assert.equal(apiErrorMessage(axiosLike({ detail: [{ msg: 'campo requerido' }, { msg: 'otro' }] }), 'x'), 'campo requerido · otro')
  assert.equal(apiErrorMessage(axiosLike({}), 'No se pudo enviar'), 'No se pudo enviar')
  assert.equal(apiErrorMessage(new Error('boom'), 'No se pudo enviar'), 'No se pudo enviar')
})

test('formatFileSize', () => {
  assert.equal(formatFileSize(512), '512 B')
  assert.equal(formatFileSize(2048), '2 KB')
  assert.equal(formatFileSize(5 * MB), '5 MB')
  assert.equal(formatFileSize(1.5 * MB), '1,5 MB')
})

test('an expired admin session on /chat returns to /chat after login', async () => {
  const { readFileSync } = await import('node:fs')
  const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
  const roots = client.match(/const adminRoots = new Set\(\[([\s\S]*?)\]\)/)?.[1] ?? ''
  assert.match(roots, /'chat'/)
})
