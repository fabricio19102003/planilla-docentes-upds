import { api } from '@/api/client'

export function safeDownloadSegment(value: string | undefined, fallback: string): string {
  const safe = (value ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9._-]+/g, '_')
    .replace(/^[._-]+|[._-]+$/g, '')
  return safe || fallback
}

export async function downloadApiBlob(path: string, filename?: string): Promise<void> {
  const response = await api.get(path, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
  const link = document.createElement('a')
  link.href = url
  const disposition = response.headers['content-disposition'] as string | undefined
  const serverFilename = disposition?.match(/filename="?([^";]+)"?/i)?.[1]
  link.download = filename ?? serverFilename ?? 'download'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
