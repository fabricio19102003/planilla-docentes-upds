import { useEffect, useState } from 'react'
import { Download, FileText, ImageOff } from 'lucide-react'

import { fetchChatAttachment } from '@/api/hooks/useChat'
import type { ChatAttachment } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogHeader, DialogPopup, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage, formatFileSize, isInlineImage } from '@/lib/chat'

type ImageState = { status: 'loading' } | { status: 'ready'; url: string } | { status: 'error' }

// Attachments are private: the Blob is fetched with the auth header and shown through an object URL.
function ImageAttachment({ attachment }: { attachment: ChatAttachment }) {
  const [state, setState] = useState<ImageState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    fetchChatAttachment(attachment.id)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setState({ status: 'ready', url: objectUrl })
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' })
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [attachment.id])

  if (state.status === 'loading') {
    return <Skeleton className="h-32 w-44 rounded-lg" role="status" aria-label={`Cargando ${attachment.filename}`} />
  }

  if (state.status === 'error') {
    return (
      <div className="flex w-44 items-center gap-2 rounded-lg border bg-background/60 p-2 text-xs text-muted-foreground" role="status">
        <ImageOff className="size-4 shrink-0" aria-hidden="true" />
        <span className="min-w-0 truncate">No se pudo cargar «{attachment.filename}»</span>
      </div>
    )
  }

  return (
    <Dialog>
      <DialogTrigger
        render={
          <button
            type="button"
            aria-label={`Ver imagen ${attachment.filename}`}
            className="block overflow-hidden rounded-lg border bg-background outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        }
      >
        <img src={state.url} alt={attachment.filename} className="max-h-40 max-w-full object-cover" />
      </DialogTrigger>
      <DialogPopup className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="truncate pe-8">{attachment.filename}</DialogTitle>
          <DialogDescription>{formatFileSize(attachment.size_bytes)}</DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto px-6 pb-6">
          <img src={state.url} alt={attachment.filename} className="max-h-[70vh] max-w-full rounded-lg object-contain" />
        </div>
      </DialogPopup>
    </Dialog>
  )
}

function FileAttachment({ attachment }: { attachment: ChatAttachment }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const download = async () => {
    setDownloading(true)
    setError(null)
    try {
      const blob = await fetchChatAttachment(attachment.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = attachment.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo descargar el archivo'))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="max-w-full justify-start bg-background"
        aria-label={`Descargar ${attachment.filename}`}
        disabled={downloading}
        onClick={() => void download()}
      >
        <FileText aria-hidden="true" />
        <span className="min-w-0 truncate">{attachment.filename}</span>
        <span className="shrink-0 text-xs text-muted-foreground">{formatFileSize(attachment.size_bytes)}</span>
        <Download aria-hidden="true" />
      </Button>
      {error && (
        <p role="alert" className="text-xs text-destructive-foreground">
          {error}
        </p>
      )}
    </div>
  )
}

export function ChatAttachments({ attachments }: { attachments: ChatAttachment[] }) {
  if (attachments.length === 0) return null
  return (
    <ul aria-label="Archivos adjuntos" className="m-0 flex list-none flex-col items-start gap-2 p-0">
      {attachments.map((attachment) => (
        <li key={attachment.id} className="max-w-full">
          {isInlineImage(attachment.content_type) ? (
            <ImageAttachment attachment={attachment} />
          ) : (
            <FileAttachment attachment={attachment} />
          )}
        </li>
      ))}
    </ul>
  )
}
