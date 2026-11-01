import { useState } from 'react'
import { CheckCircle2, CircleHelp, FileUp } from 'lucide-react'

import { useApplyImport, useImportReceipts, usePreviewImport } from '@/api/hooks/useAcademicRecords'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { importCountRows, splitIssues, type ImportPreview, type ImportResult } from '@/lib/academicRecordsState'
import { apiErrorMessage } from '@/lib/userCredentials'

function Summary({ result }: { result: ImportPreview }) {
  const { errors, warnings } = splitIssues(result.issues)
  return (
    <div className="space-y-4">
      <dl className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {importCountRows(result.counts).map(({ label, value }) => (
          <div key={label} className="flex justify-between gap-3 rounded-md border px-3 py-2">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="font-medium tabular-nums">{value.toLocaleString('es-BO')}</dd>
          </div>
        ))}
      </dl>
      <p className="text-sm"><span className="text-muted-foreground">Períodos del archivo:</span> {result.terms.join(', ') || '—'}</p>
      {warnings.length > 0 && (
        <Alert variant="warning">
          <AlertTitle>Advertencias (se importan igual)</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">{warnings.map((issue) => <li key={issue.message}>{issue.message} · {issue.rows} fila(s)</li>)}</ul>
          </AlertDescription>
        </Alert>
      )}
      {errors.length > 0 && (
        <Alert variant="error">
          <AlertTitle>{result.counts.error_rows} fila(s) con error no se importan</AlertTitle>
          <AlertDescription>
            <ul className="max-h-48 list-disc overflow-y-auto pl-4">
              {errors.map((issue) => <li key={`${issue.row}-${issue.message}`}>Fila {issue.row}: {issue.message}</li>)}
            </ul>
            {errors.length < result.counts.error_rows && <p>Se muestran las primeras {errors.length}.</p>}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

export function AcademicHistoryImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [applied, setApplied] = useState<ImportResult | null>(null)
  const previewImport = usePreviewImport()
  const applyImport = useApplyImport()
  const receipts = useImportReceipts()
  const busy = previewImport.isPending || applyImport.isPending

  const choose = (selected: File | null) => {
    setFile(selected)
    setPreview(null)
    setApplied(null)
    previewImport.reset()
    applyImport.reset()
  }
  const runPreview = () => {
    if (file) previewImport.mutate(file, { onSuccess: setPreview })
  }
  const runApply = () => {
    if (file && preview) {
      applyImport.mutate({ file, sha256: preview.file_sha256 }, {
        onSuccess: (result) => { setApplied(result); setPreview(null) },
      })
    }
  }
  const error = previewImport.error ?? applyImport.error

  return (
    <div className="space-y-5">
      <PageHeader title="Importar historial académico" description="Cargá el CSV de una gestión exportado del sistema académico." />

      <details className="rounded-lg border bg-muted/30 px-4 py-3 text-sm">
        <summary className="flex cursor-pointer items-center gap-2 font-medium">
          <CircleHelp className="size-4" aria-hidden="true" />¿Cómo funciona la importación?
        </summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
          <li>Elegí el archivo <strong className="text-foreground">gestion-AAAA.csv</strong> y revisá la vista previa: nada se guarda hasta que confirmes.</li>
          <li>Podés importar el mismo archivo o uno más nuevo las veces que haga falta: los estudiantes se reconocen por su documento y cada materia por su número de registro, así que no se duplican.</li>
          <li>Si una materia cambió (por ejemplo, de <em>en curso</em> a <em>aprobada</em>), se actualiza.</li>
          <li>Las filas con error se omiten y se listan con su número de fila para corregirlas en el sistema académico.</li>
        </ul>
      </details>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">1. Elegir archivo</CardTitle>
          <CardDescription>Formato CSV del sistema académico, con las 48 columnas de exportación.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1">
            <Label htmlFor="history-file">Archivo CSV</Label>
            <Input id="history-file" type="file" accept=".csv,text/csv" disabled={busy} onChange={(event) => choose(event.target.files?.[0] ?? null)} />
          </div>
          <Button onClick={runPreview} disabled={!file || busy}>
            <FileUp aria-hidden="true" />{previewImport.isPending ? 'Analizando…' : 'Ver vista previa'}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(error, 'No se pudo procesar el archivo.')}</AlertTitle></Alert>
      )}

      {preview && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">2. Revisar y confirmar</CardTitle>
            <CardDescription>{preview.file_name}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Summary result={preview} />
            <Button onClick={runApply} disabled={busy || preview.counts.valid_rows === 0}>
              {applyImport.isPending ? 'Importando…' : `Importar ${preview.counts.valid_rows.toLocaleString('es-BO')} fila(s)`}
            </Button>
          </CardContent>
        </Card>
      )}

      {applied && (
        <Alert variant="success" role="status">
          <CheckCircle2 aria-hidden="true" />
          <AlertTitle>Historial importado desde {applied.file_name}</AlertTitle>
          <AlertDescription><Summary result={applied} /></AlertDescription>
        </Alert>
      )}

      <TableCard title="Importaciones realizadas" tableClassName="min-w-[720px]">
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="px-4">Archivo</TableHead>
            <TableHead className="px-4">Períodos</TableHead>
            <TableHead className="px-4 text-right">Nuevas / actualizadas</TableHead>
            <TableHead className="px-4">Realizada por</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {receipts.isLoading && (
            <TableRow><TableCell colSpan={4} role="status" className="px-4 py-6 text-center text-muted-foreground">Cargando importaciones…</TableCell></TableRow>
          )}
          {receipts.isError && (
            <TableRow><TableCell colSpan={4} role="alert" className="px-4 py-6 text-center text-destructive-foreground">No se pudieron cargar las importaciones.</TableCell></TableRow>
          )}
          {receipts.data?.length === 0 && (
            <TableRow><TableCell colSpan={4} className="px-4 py-6 text-center text-muted-foreground">Todavía no se importó ningún archivo.</TableCell></TableRow>
          )}
          {receipts.data?.map((receipt) => (
            <TableRow key={receipt.id}>
              <TableCell className="px-4 py-3">
                <p className="font-medium text-foreground">{receipt.file_name}</p>
                <p className="font-mono text-xs text-muted-foreground" title={receipt.file_sha256}>{receipt.file_sha256.slice(0, 12)}…</p>
              </TableCell>
              <TableCell className="px-4 py-3 whitespace-normal">
                <span className="flex flex-wrap gap-1">{receipt.terms.map((term) => <Badge key={term} variant="outline" size="sm">{term}</Badge>)}</span>
              </TableCell>
              <TableCell className="px-4 py-3 text-right tabular-nums">
                {receipt.counts.records_new.toLocaleString('es-BO')} / {receipt.counts.records_updated.toLocaleString('es-BO')}
              </TableCell>
              <TableCell className="px-4 py-3">
                {receipt.actor_name ?? '—'}
                <p className="text-xs text-muted-foreground">{new Date(receipt.created_at).toLocaleString('es-BO')}</p>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </TableCard>
    </div>
  )
}
