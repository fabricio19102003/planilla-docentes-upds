import { Copy, Download, KeyRound } from 'lucide-react'
import { useState } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { credentialsCsv, type TemporaryCredential } from '@/lib/reenrollmentState'

function saveCsv(content: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

/** Shows freshly issued temporary passwords once; they are never retrievable again. */
export function CredentialsDialog({ credentials, onClose }: { credentials: TemporaryCredential[]; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const single = credentials.length === 1 ? credentials[0] : null

  return (
    <Dialog open={credentials.length > 0} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogPopup className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10">
              <KeyRound size={20} className="text-primary" aria-hidden="true" />
            </div>
            <div className="flex flex-col gap-1">
              <DialogTitle>{single ? 'Clave temporal generada' : `${credentials.length} claves temporales generadas`}</DialogTitle>
              <DialogDescription>Entregala en persona. El estudiante entra con su número de documento y la cambia la primera vez.</DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <DialogPanel className="space-y-4">
          <Alert variant="warning">
            <AlertDescription>Esta es la única vez que se muestra. Si se pierde, generá una nueva: la anterior deja de funcionar.</AlertDescription>
          </Alert>
          {single ? (
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">{single.full_name} · {single.document_number}</p>
              <p className="mt-1 font-mono text-2xl tracking-wider text-foreground">{single.temporary_password}</p>
            </div>
          ) : (
            <div className="max-h-80 overflow-auto rounded-lg border">
              <table className="w-full text-sm">
                <TableHeader>
                  <TableRow><TableHead className="px-3">Estudiante</TableHead><TableHead className="px-3">Clave temporal</TableHead></TableRow>
                </TableHeader>
                <TableBody>
                  {credentials.map((c) => (
                    <TableRow key={c.student_id}>
                      <TableCell className="px-3 py-2">{c.full_name}<p className="text-xs text-muted-foreground">{c.document_number}</p></TableCell>
                      <TableCell className="px-3 py-2 font-mono">{c.temporary_password}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </table>
            </div>
          )}
        </DialogPanel>
        <DialogFooter>
          {single ? (
            <Button variant="outline" onClick={() => void navigator.clipboard.writeText(single.temporary_password).then(() => setCopied(true))}>
              <Copy aria-hidden="true" />{copied ? 'Copiada' : 'Copiar clave'}
            </Button>
          ) : (
            <Button variant="outline" onClick={() => saveCsv(credentialsCsv(credentials), 'claves-temporales-portal.csv')}>
              <Download aria-hidden="true" />Descargar CSV
            </Button>
          )}
          <Button onClick={onClose}>Listo</Button>
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  )
}
