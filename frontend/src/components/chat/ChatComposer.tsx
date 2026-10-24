import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, KeyboardEvent } from 'react'
import { FileText, Paperclip, Send, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  CHAT_ACCEPT,
  CHAT_MAX_BODY_LENGTH,
  CHAT_MAX_FILES,
  apiErrorMessage,
  canSendMessage,
  formatFileSize,
  validateAttachments,
} from '@/lib/chat'
import { cn } from '@/lib/utils'

export interface ChatComposerProps {
  onSend: (payload: { body: string; files: File[] }) => Promise<unknown>
}

export function ChatComposer({ onSend }: ChatComposerProps) {
  const [body, setBody] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [problems, setProblems] = useState<string[]>([])
  const [sending, setSending] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const wasSending = useRef(false)

  // The textarea is disabled while sending; give the focus back once it is enabled again.
  useEffect(() => {
    if (wasSending.current && !sending) textareaRef.current?.focus()
    wasSending.current = sending
  }, [sending])

  const overLimit = body.length > CHAT_MAX_BODY_LENGTH
  const sendable = canSendMessage(body, files.length, sending)

  const submit = async () => {
    if (!canSendMessage(body, files.length, sending)) return
    setSending(true)
    setProblems([])
    try {
      await onSend({ body, files })
      setBody('')
      setFiles([])
    } catch (error) {
      setProblems([apiErrorMessage(error, 'No se pudo enviar el mensaje. Inténtalo de nuevo.')])
    } finally {
      setSending(false)
    }
  }

  const pickFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (picked.length === 0) return
    const { accepted, errors } = validateAttachments(files, picked)
    setFiles((current) => [...current, ...accepted])
    setProblems(errors)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    void submit()
  }

  return (
    <form
      className="flex shrink-0 flex-col gap-2 border-t bg-card p-3"
      onSubmit={(event) => {
        event.preventDefault()
        void submit()
      }}
    >
      {problems.length > 0 && (
        <ul role="alert" className="m-0 flex list-none flex-col gap-0.5 p-0 text-xs text-destructive-foreground">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}
      {files.length > 0 && (
        <ul aria-label="Archivos por enviar" className="m-0 flex list-none flex-wrap gap-2 p-0">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}-${index}`}
              className="flex max-w-full items-center gap-1.5 rounded-full border bg-muted/60 py-1 pe-1 ps-2.5 text-xs"
            >
              <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 max-w-48 truncate">{file.name}</span>
              <span className="shrink-0 text-muted-foreground">{formatFileSize(file.size)}</span>
              <button
                type="button"
                aria-label={`Quitar ${file.name}`}
                disabled={sending}
                className="grid size-5 shrink-0 place-items-center rounded-full outline-none hover:bg-foreground/10 focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                onClick={() => {
                  setFiles((current) => current.filter((_, i) => i !== index))
                  setProblems([])
                }}
              >
                <X className="size-3" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          accept={CHAT_ACCEPT}
          data-testid="chat-file-input"
          onChange={pickFiles}
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label="Adjuntar archivo"
          disabled={sending}
          onClick={() => fileInputRef.current?.click()}
        >
          <Paperclip />
        </Button>
        <div className="min-w-0 flex-1">
          <Textarea
            ref={textareaRef}
            aria-label="Escribir mensaje"
            aria-describedby="chat-composer-hint"
            aria-invalid={overLimit || undefined}
            placeholder="Escribe un mensaje…"
            rows={1}
            className="[&_textarea]:max-h-40 [&_textarea]:min-h-10 [&_textarea]:resize-none"
            value={body}
            disabled={sending}
            onChange={(event) => setBody(event.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>
        <Button type="submit" size="icon" aria-label="Enviar mensaje" disabled={!sendable}>
          <Send />
        </Button>
      </div>
      <div id="chat-composer-hint" className="flex items-center justify-between gap-3 px-0.5 text-[11px] text-muted-foreground">
        <span>
          <span className="hidden sm:inline">Enter envía · Shift+Enter nueva línea · </span>
          hasta {CHAT_MAX_FILES} archivos (PDF, JPEG, PNG o WEBP, 10 MB c/u, 20 MB en total)
        </span>
        <span className={cn('shrink-0 tabular-nums', overLimit && 'font-medium text-destructive-foreground')}>
          {body.length}/{CHAT_MAX_BODY_LENGTH}
        </span>
      </div>
    </form>
  )
}
