import type { ChatConversationSummary, ChatMessage, ChatSenderRole } from '@/api/types'

// Limits mirror app/services/chat_service.py; the backend stays the authority.
export const CHAT_MAX_BODY_LENGTH = 4000
export const CHAT_MAX_FILES = 3
export const CHAT_MAX_FILE_BYTES = 10 * 1024 * 1024
export const CHAT_MAX_TOTAL_BYTES = 20 * 1024 * 1024
export const CHAT_ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'] as const
export const CHAT_ACCEPT = CHAT_ALLOWED_TYPES.join(',')
export const CHAT_INLINE_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export const CHAT_ADMIN_PATH = '/chat'
export const CHAT_PORTAL_PATH = '/portal/chat'

/** Open conversation refresh. */
export const CHAT_THREAD_POLL_MS = 5_000
/** Unread counters and the admin inbox list refresh. */
export const CHAT_INBOX_POLL_MS = 30_000

const BOLIVIA_TIME_ZONE = 'America/La_Paz'

export interface AttachmentCandidate {
  name: string
  type: string
  size: number
}

export interface AttachmentValidation<T extends AttachmentCandidate> {
  accepted: T[]
  errors: string[]
}

const MB = 1024 * 1024

/** Validates picked files against what is already attached; rejected files never enter `accepted`. */
export function validateAttachments<T extends AttachmentCandidate>(existing: T[], incoming: T[]): AttachmentValidation<T> {
  const accepted: T[] = []
  const errors: string[] = []
  let count = existing.length
  let total = existing.reduce((sum, file) => sum + file.size, 0)

  for (const file of incoming) {
    if (!(CHAT_ALLOWED_TYPES as readonly string[]).includes(file.type)) {
      errors.push(`«${file.name}»: solo se permiten archivos PDF, JPEG, PNG o WEBP`)
    } else if (file.size > CHAT_MAX_FILE_BYTES) {
      errors.push(`«${file.name}» supera el máximo de ${CHAT_MAX_FILE_BYTES / MB} MB por archivo`)
    } else if (count >= CHAT_MAX_FILES) {
      errors.push(`Solo puedes adjuntar hasta ${CHAT_MAX_FILES} archivos por mensaje; «${file.name}» no se agregó`)
    } else if (total + file.size > CHAT_MAX_TOTAL_BYTES) {
      errors.push(`«${file.name}» haría que los archivos del mensaje superen los ${CHAT_MAX_TOTAL_BYTES / MB} MB en total`)
    } else {
      accepted.push(file)
      count += 1
      total += file.size
    }
  }
  return { accepted, errors }
}

export function canSendMessage(body: string, fileCount: number, sending: boolean): boolean {
  if (sending || body.length > CHAT_MAX_BODY_LENGTH) return false
  return body.trim().length > 0 || fileCount > 0
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const format = (value: number) => value.toLocaleString('es-BO', { maximumFractionDigits: 1 })
  if (bytes < MB) return `${format(bytes / 1024)} KB`
  return `${format(bytes / MB)} MB`
}

/** Backend `detail` (string or FastAPI validation list) with a fallback; no axios dependency so it stays testable. */
// Shared with the user dialogs: string details as-is, FastAPI 422 lists flattened.
export { apiErrorMessage } from './userCredentials.ts'

/** Appends polled messages without refetching: dedupes by id (incoming wins) and keeps id order. */
export function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  if (incoming.length === 0) return current
  const byId = new Map<number, ChatMessage>()
  for (const message of current) byId.set(message.id, message)
  for (const message of incoming) byId.set(message.id, message)
  return [...byId.values()].sort((a, b) => a.id - b.id)
}

export function lastMessageId(messages: ChatMessage[]): number {
  return messages.length > 0 ? messages[messages.length - 1].id : 0
}

/**
 * The unread messages are the newest `unreadCount` messages from the other side; the divider goes
 * before the oldest of them. With more unread than loaded it falls back to the oldest loaded one.
 */
export function unreadDividerMessageId(messages: ChatMessage[], viewer: ChatSenderRole, unreadCount: number): number | null {
  if (unreadCount <= 0) return null
  let remaining = unreadCount
  let dividerId: number | null = null
  for (let index = messages.length - 1; index >= 0 && remaining > 0; index -= 1) {
    if (messages[index].sender_role === viewer) continue
    dividerId = messages[index].id
    remaining -= 1
  }
  return dividerId
}

/** Backend datetimes are naive UTC. */
export function parseChatDate(value: string): Date {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`)
}

const dayKeyFormatter = new Intl.DateTimeFormat('en-CA', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: BOLIVIA_TIME_ZONE,
})
const longDateFormatter = new Intl.DateTimeFormat('es-BO', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: BOLIVIA_TIME_ZONE,
})
const timeFormatter = new Intl.DateTimeFormat('es-BO', {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: BOLIVIA_TIME_ZONE,
})
const shortDateFormatter = new Intl.DateTimeFormat('es-BO', {
  day: '2-digit',
  month: '2-digit',
  timeZone: BOLIVIA_TIME_ZONE,
})

function dayKey(date: Date): string {
  return dayKeyFormatter.format(date)
}

function dayLabel(date: Date, now: Date): string {
  const key = dayKey(date)
  if (key === dayKey(now)) return 'Hoy'
  if (key === dayKey(new Date(now.getTime() - 24 * 60 * 60 * 1000))) return 'Ayer'
  return longDateFormatter.format(date)
}

export function formatMessageTime(value: string): string {
  return timeFormatter.format(parseChatDate(value))
}

/** Inbox list timestamp: time today, "Ayer", otherwise dd/MM. */
export function formatListTimestamp(value: string | null, now: Date = new Date()): string {
  if (!value) return ''
  const date = parseChatDate(value)
  const label = dayLabel(date, now)
  if (label === 'Hoy') return formatMessageTime(value)
  if (label === 'Ayer') return label
  return shortDateFormatter.format(date)
}

export type ThreadItem =
  | { kind: 'date'; key: string; label: string }
  | { kind: 'unread'; key: string }
  | { kind: 'message'; key: string; message: ChatMessage; side: 'incoming' | 'outgoing'; grouped: boolean }

/**
 * Flattens messages into render items: date pills, the unread divider (before `dividerId`, frozen
 * by the caller when the conversation opens) and sender-grouped bubbles.
 */
export function buildThreadItems(
  messages: ChatMessage[],
  viewer: ChatSenderRole,
  dividerId: number | null,
  now: Date = new Date(),
): ThreadItem[] {
  const items: ThreadItem[] = []
  let currentDay = ''
  let previous: ChatMessage | null = null

  for (const message of messages) {
    const date = parseChatDate(message.created_at)
    const key = dayKey(date)
    let separated = false
    if (key !== currentDay) {
      currentDay = key
      items.push({ kind: 'date', key: `date-${key}`, label: dayLabel(date, now) })
      separated = true
    }
    if (message.id === dividerId) {
      items.push({ kind: 'unread', key: 'unread' })
      separated = true
    }
    const grouped =
      !separated &&
      previous !== null &&
      previous.sender_role === message.sender_role &&
      previous.sender_user_id === message.sender_user_id
    items.push({
      kind: 'message',
      key: `message-${message.id}`,
      message,
      side: message.sender_role === viewer ? 'outgoing' : 'incoming',
      grouped,
    })
    previous = message
  }
  return items
}

export interface ThreadDay {
  key: string
  label: string
  items: Exclude<ThreadItem, { kind: 'date' }>[]
}

/** Splits the flat items at each date pill so every day can render (and stick) on its own. */
export function groupByDay(items: ThreadItem[]): ThreadDay[] {
  const days: ThreadDay[] = []
  for (const item of items) {
    if (item.kind === 'date') days.push({ key: item.key, label: item.label, items: [] })
    else days[days.length - 1]?.items.push(item)
  }
  return days
}

export function initialsOf(name: string | null | undefined): string {
  const letters = (name ?? '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
  return letters || '?'
}

export function conversationTitle(conversation: Pick<ChatConversationSummary, 'teacher_name' | 'teacher_ci'>): string {
  return conversation.teacher_name || `CI ${conversation.teacher_ci}`
}

export function isInlineImage(contentType: string): boolean {
  return CHAT_INLINE_IMAGE_TYPES.includes(contentType)
}
