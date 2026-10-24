import type { Page, Route } from '@playwright/test'

import { adminUser } from './admin'

export const docenteChatUser = {
  id: 42,
  ci: '12345678',
  full_name: 'Ana Docente',
  email: null,
  role: 'docente',
  teacher_ci: '12345678',
  is_active: true,
  last_login: null,
  must_change_password: false,
  avatar_url: null,
}

// 1x1 transparent PNG.
export const PNG_BYTES = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
)

export interface FakeAttachment {
  id: number
  filename: string
  content_type: string
  size_bytes: number
}

export interface FakeMessage {
  id: number
  conversation_id: number
  sender_user_id: number | null
  sender_role: 'admin' | 'docente'
  sender_name: string | null
  body: string
  created_at: string
  attachments: FakeAttachment[]
}

export interface SentMessage {
  path: string
  body: string
  files: Array<{ name: string; type: string }>
}

const CONVERSATION_ID = 7

function naiveUtc(minutesAgo: number): string {
  return new Date(Date.now() - minutesAgo * 60_000).toISOString().replace('Z', '')
}

function parseMultipart(route: Route): { body: string; files: SentMessage['files'] } {
  const request = route.request()
  const boundary = /boundary=(.+)$/.exec(request.headers()['content-type'] ?? '')?.[1] ?? ''
  const raw = request.postDataBuffer()?.toString('latin1') ?? ''
  let body = ''
  const files: Array<{ name: string; type: string }> = []
  for (const part of raw.split(`--${boundary}`)) {
    const headerEnd = part.indexOf('\r\n\r\n')
    if (headerEnd < 0) continue
    const head = part.slice(0, headerEnd)
    const value = part.slice(headerEnd + 4).replace(/\r\n$/, '')
    const name = /name="([^"]+)"/.exec(head)?.[1]
    const filename = /filename="([^"]*)"/.exec(head)?.[1]
    // Multipart encoding turns every newline in a text field into CRLF; compare with plain \n.
    if (name === 'body') body = Buffer.from(value, 'latin1').toString('utf8').replace(/\r\n/g, '\n')
    if (name === 'files' && filename) files.push({ name: filename, type: /Content-Type:\s*(\S+)/i.exec(head)?.[1] ?? '' })
  }
  return { body, files }
}

/** In-memory stand-in for the chat API (see odd/reference/router_chat.py). */
export class FakeChatApi {
  messages: FakeMessage[] = []
  adminReadId = 0
  docenteReadId = 0
  sent: SentMessage[] = []
  threadRequests: Array<{ path: string; after: string | null }> = []
  readCalls: string[] = []
  attachmentAuth: Array<string | undefined> = []
  private nextMessageId = 1
  private nextAttachmentId = 1

  push(role: 'admin' | 'docente', body: string, minutesAgo = 1, attachments: Array<Omit<FakeAttachment, 'id'>> = []): FakeMessage {
    const message: FakeMessage = {
      id: this.nextMessageId++,
      conversation_id: CONVERSATION_ID,
      sender_user_id: role === 'admin' ? adminUser.id : docenteChatUser.id,
      sender_role: role,
      sender_name: role === 'admin' ? 'E2E Admin' : docenteChatUser.full_name,
      body,
      created_at: naiveUtc(minutesAgo),
      attachments: attachments.map((a) => ({ ...a, id: this.nextAttachmentId++ })),
    }
    this.messages.push(message)
    return message
  }

  private unread(side: 'admin' | 'docente'): number {
    const mark = side === 'admin' ? this.adminReadId : this.docenteReadId
    const from = side === 'admin' ? 'docente' : 'admin'
    return this.messages.filter((m) => m.sender_role === from && m.id > mark).length
  }

  private latest(): string | null {
    return this.messages.length ? this.messages[this.messages.length - 1].created_at : null
  }

  private conversation(side: 'admin' | 'docente') {
    return {
      id: CONVERSATION_ID,
      teacher_ci: docenteChatUser.teacher_ci,
      teacher_name: docenteChatUser.full_name,
      unread_count: this.unread(side),
      last_message_at: this.latest(),
    }
  }

  private thread(side: 'admin' | 'docente', after: number) {
    const visible = after > 0 ? this.messages.filter((m) => m.id > after) : this.messages
    const messages = visible.map((m) =>
      side === 'docente' && m.sender_role === 'admin' ? { ...m, sender_name: 'Administración' } : m,
    )
    return { conversation: this.conversation(side), messages }
  }

  private summaries() {
    const last = this.messages[this.messages.length - 1]
    if (!last) return []
    return [
      {
        ...this.conversation('admin'),
        last_message: {
          preview: last.body || (last.attachments[0] ? `📎 ${last.attachments[0].filename}` : ''),
          sender_role: last.sender_role,
          created_at: last.created_at,
        },
      },
    ]
  }

  private send(route: Route, role: 'admin' | 'docente', path: string) {
    const { body, files } = parseMultipart(route)
    this.sent.push({ path, body, files })
    if (!body.trim() && files.length === 0) {
      return route.fulfill({ status: 422, json: { detail: 'Escribe un mensaje o adjunta un archivo' } })
    }
    const message = this.push(
      role,
      body.trim(),
      0,
      files.map((f) => ({ filename: f.name, content_type: f.type, size_bytes: PNG_BYTES.length })),
    )
    return route.fulfill({ status: 201, json: message })
  }

  /** Routes every /api/ request the chat pages issue; anything else answers 501 so gaps are visible. */
  async install(page: Page, role: 'admin' | 'docente') {
    const token = role === 'admin' ? 'e2e-admin-token' : 'e2e-docente-token'
    await page.addInitScript((value) => window.localStorage.setItem('auth_token', value), token)

    await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const path = url.pathname.replace(/^\/api/, '')
      const method = request.method()
      const after = Number(url.searchParams.get('after') ?? 0)

      if (method === 'GET' && path === '/auth/me') return route.fulfill({ json: role === 'admin' ? adminUser : docenteChatUser })
      if (method === 'GET' && path === '/portal/notifications/unread-count') return route.fulfill({ json: { count: 0 } })

      if (role === 'docente') {
        if (method === 'GET' && path === '/chat/me') {
          this.threadRequests.push({ path, after: url.searchParams.get('after') })
          return route.fulfill({ json: this.thread('docente', after) })
        }
        if (method === 'POST' && path === '/chat/me/messages') return this.send(route, 'docente', path)
        if (method === 'POST' && path === '/chat/me/read') {
          this.readCalls.push(path)
          this.docenteReadId = this.messages.length ? this.messages[this.messages.length - 1].id : 0
          return route.fulfill({ json: { unread_count: this.unread('docente') } })
        }
        if (method === 'GET' && path === '/chat/me/unread-count') return route.fulfill({ json: { unread_count: this.unread('docente') } })
      } else {
        if (method === 'GET' && path === '/chat/conversations') {
          const q = (url.searchParams.get('q') ?? '').toLowerCase()
          const matches = !q || docenteChatUser.full_name.toLowerCase().includes(q) || docenteChatUser.teacher_ci.includes(q)
          return route.fulfill({ json: matches ? this.summaries() : [] })
        }
        if (method === 'GET' && path === '/chat/unread-count') return route.fulfill({ json: { unread_count: this.unread('admin') } })
        if (method === 'GET' && path === `/chat/conversations/${CONVERSATION_ID}/messages`) {
          this.threadRequests.push({ path, after: url.searchParams.get('after') })
          return route.fulfill({ json: this.thread('admin', after) })
        }
        if (method === 'POST' && path === `/chat/conversations/${CONVERSATION_ID}/messages`) return this.send(route, 'admin', path)
        if (method === 'POST' && path === `/chat/conversations/${CONVERSATION_ID}/read`) {
          this.readCalls.push(path)
          this.adminReadId = this.messages.length ? this.messages[this.messages.length - 1].id : 0
          return route.fulfill({ json: { unread_count: this.unread('admin') } })
        }
      }

      if (method === 'GET' && /^\/chat\/attachments\/\d+$/.test(path)) {
        this.attachmentAuth.push(request.headers()['authorization'])
        return route.fulfill({ status: 200, contentType: 'image/png', body: PNG_BYTES })
      }
      return route.fulfill({ status: 501, json: { detail: `Unexpected E2E request: ${method} ${path}` } })
    })
  }
}
