import { useEffect, useMemo, useState } from 'react'
import { CheckCircle, TriangleAlert, Users } from 'lucide-react'

import { api } from '@/api/client'
import { usePreviewDesignations, useUploadDesignations } from '@/api/hooks/useBiometric'
import type { DesignationImportChange, DesignationImportPreview, DesignationUploadResponse } from '@/api/types'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { FileUploader } from '@/components/shared/FileUploader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { changeSummary, changedFieldsText, errorDetails } from '@/lib/designationAdminState'

type ChangeFilter = 'create' | 'update' | 'noop'

const FILTER_LABEL: Record<ChangeFilter, string> = { create: 'Nuevas', update: 'Con cambios', noop: 'Sin cambios' }

function Step({ number, title, active, children }: { number: number; title: string; active: boolean; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`import-step-${number}`} className={`flex flex-col gap-3 ${active ? '' : 'opacity-60'}`}>
      <h4 id={`import-step-${number}`} className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <span className="flex size-6 items-center justify-center rounded-full border text-xs tabular-nums">{number}</span>
        {title}
      </h4>
      {children}
    </section>
  )
}

function ChangesTable({ changes }: { changes: DesignationImportChange[] }) {
  const summary = changeSummary(changes)
  const [filter, setFilter] = useState<ChangeFilter>(summary.create ? 'create' : summary.update ? 'update' : 'noop')
  const rows = changes.filter((change) => change.action === filter)
  return (
    <div className="flex flex-col gap-2">
      <div role="tablist" aria-label="Filtrar filas" className="flex flex-wrap gap-2">
        {(Object.keys(FILTER_LABEL) as ChangeFilter[]).map((key) => (
          <Button key={key} type="button" role="tab" aria-selected={filter === key} size="sm" variant={filter === key ? 'default' : 'outline'} onClick={() => setFilter(key)}>
            {FILTER_LABEL[key]} ({summary[key]})
          </Button>
        ))}
      </div>
      <div className="max-h-72 overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fila</TableHead>
              <TableHead>Docente</TableHead>
              <TableHead>Materia</TableHead>
              <TableHead>Sem. / Grupo</TableHead>
              {filter === 'update' && <TableHead>Qué cambia</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((change) => (
              <TableRow key={change.row}>
                <TableCell className="tabular-nums">{change.row}</TableCell>
                <TableCell>{change.teacher_name}</TableCell>
                <TableCell className="font-medium">{change.subject}</TableCell>
                <TableCell>{change.semester} · {change.group_code}</TableCell>
                {filter === 'update' && <TableCell>{changedFieldsText(change.fields)}</TableCell>}
              </TableRow>
            ))}
            {!rows.length && (
              <TableRow><TableCell colSpan={5} className="py-6 text-center text-muted-foreground">No hay filas en este grupo.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

/**
 * Import designations from the official Excel (or the audited .json): pick file and period,
 * read what each row will do, then confirm. Nothing is written before the confirmation.
 */
export function DesignationImportWizard({ periods = [], onImported }: {
  periods?: string[]
  onImported?: (result: DesignationUploadResponse) => void
}) {
  const [desFile, setDesFile] = useState<File | null>(null)
  const [desPreview, setDesPreview] = useState<DesignationImportPreview | null>(null)
  const [desResult, setDesResult] = useState<DesignationUploadResponse | null>(null)
  const [desProgress, setDesProgress] = useState(0)
  const [confirmDesApply, setConfirmDesApply] = useState(false)
  // The server value is only a suggested selection; importing never activates a period.
  const [academicPeriod, setAcademicPeriod] = useState('')
  const previewDesignations = usePreviewDesignations()
  const uploadDesignations = useUploadDesignations()
  const uploading = previewDesignations.isPending || uploadDesignations.isPending
  const failure = previewDesignations.error ?? uploadDesignations.error
  const problems = failure ? errorDetails(failure, 'Verificá el archivo e intentá de nuevo.') : null
  const changes = useMemo(() => desPreview?.changes ?? [], [desPreview])

  useEffect(() => {
    api.get<{ academic_period: string }>('/config/active-period')
      .then((res) => setAcademicPeriod((current) => current || res.data.academic_period))
      .catch(() => undefined)
  }, [])

  const reset = () => { setDesPreview(null); setDesResult(null); previewDesignations.reset(); uploadDesignations.reset() }

  const handleDesPreview = () => {
    if (!desFile || !academicPeriod.trim()) return
    setDesPreview(null)
    setDesResult(null)
    setDesProgress(0)
    previewDesignations.mutate(
      { file: desFile, academic_period: academicPeriod, onProgress: setDesProgress },
      { onSuccess: setDesPreview },
    )
  }

  const handleDesApply = () => {
    if (!desFile || !desPreview?.can_apply) return
    setDesProgress(0)
    uploadDesignations.mutate(
      { file: desFile, academic_period: academicPeriod, confirmation_digest: desPreview.digest, onProgress: setDesProgress },
      {
        onSuccess: (data) => { setDesResult(data); setDesPreview(null); setDesFile(null); onImported?.(data) },
        onSettled: () => setConfirmDesApply(false),
      },
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <Step number={1} title="Elegí el archivo y el período" active={!desPreview}>
        <FileUploader
          accept=".json,.xlsx"
          label="Seleccioná el Excel de designaciones"
          description="El Excel oficial de designaciones del semestre (también acepta el .json auditado)"
          onFileSelect={(f) => { setDesFile(f); reset() }}
          progress={uploading ? desProgress : null}
        />
        <Field>
          <FieldLabel>Período académico</FieldLabel>
          <Input
            list="designation-import-periods"
            value={academicPeriod}
            onChange={(e) => { setAcademicPeriod(e.target.value); reset() }}
            placeholder="Ej: II/2026"
          />
          <datalist id="designation-import-periods">{periods.map((period) => <option key={period} value={period} />)}</datalist>
          <FieldDescription>La importación usa este período, pero no lo activa automáticamente.</FieldDescription>
        </Field>
        <Button onClick={handleDesPreview} disabled={!desFile || !academicPeriod.trim() || uploading}>
          {previewDesignations.isPending ? 'Revisando el archivo…' : 'Generar vista previa'}
        </Button>
      </Step>

      {problems && (
        <Alert variant="error" role="alert">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>No se pudo leer o importar el archivo</AlertTitle>
          <AlertDescription>
            <p>{problems.title}</p>
            {problems.items.length > 0 && <ul className="list-disc pl-4">{problems.items.map((item) => <li key={item}>{item}</li>)}</ul>}
          </AlertDescription>
        </Alert>
      )}

      {desPreview && (
        <Step number={2} title="Revisá qué va a pasar" active>
          <p className="text-sm text-muted-foreground">
            El archivo tiene {desPreview.total_rows} filas para {desPreview.academic_period}. Todavía no se guardó nada.
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-md border p-3"><p className="text-2xl font-semibold tabular-nums">{desPreview.designations.creates}</p><p className="text-xs text-muted-foreground">designaciones nuevas</p></div>
            <div className="rounded-md border p-3"><p className="text-2xl font-semibold tabular-nums">{desPreview.designations.updates}</p><p className="text-xs text-muted-foreground">se actualizan</p></div>
            <div className="rounded-md border p-3"><p className="text-2xl font-semibold tabular-nums">{desPreview.designations.noops}</p><p className="text-xs text-muted-foreground">quedan igual</p></div>
          </div>
          {(desPreview.teachers.creates > 0 || desPreview.users.creates > 0) && (
            <p className="text-sm">
              También se crean {desPreview.teachers.creates} docente(s) nuevo(s) y {desPreview.users.creates} cuenta(s) de acceso.
            </p>
          )}
          {desPreview.errors.length > 0 && (
            <Alert variant="error">
              <TriangleAlert aria-hidden="true" />
              <AlertTitle>Hay que corregir el archivo antes de importar</AlertTitle>
              <AlertDescription>
                <ul className="list-disc pl-4">{desPreview.errors.map((error, index) => <li key={`error-${index}`}>{error}</li>)}</ul>
              </AlertDescription>
            </Alert>
          )}
          {desPreview.warnings.length > 0 && (
            <Alert variant="warning">
              <TriangleAlert aria-hidden="true" />
              <AlertTitle>Avisos (no impiden importar)</AlertTitle>
              <AlertDescription>
                <ul className="list-disc pl-4">{desPreview.warnings.map((warning, index) => <li key={`warning-${index}`}>{warning}</li>)}</ul>
              </AlertDescription>
            </Alert>
          )}
          {changes.length > 0 && <ChangesTable changes={changes} />}
          <p className="text-xs text-muted-foreground">
            Las designaciones que ya existen y no están en el archivo no se borran. Si editaste una designación a mano y
            vuelve a venir en el archivo, se reemplaza por lo que diga el archivo.
          </p>
          <Button onClick={() => setConfirmDesApply(true)} disabled={!desPreview?.can_apply || uploadDesignations.isPending}>
            {uploadDesignations.isPending ? 'Importando…' : 'Confirmar e importar'}
          </Button>
        </Step>
      )}

      {desResult && (
        <div className="flex flex-col gap-3">
          <Alert variant="success" role="status">
            <CheckCircle aria-hidden="true" />
            <AlertTitle>¡Designaciones cargadas!</AlertTitle>
            <AlertDescription>
              {desResult.designations.creates} nuevas · {desResult.designations.updates} actualizadas · {desResult.designations.noops} sin cambios
              {desResult.warnings.length > 0 && ` · ${desResult.warnings.length} aviso(s)`}
            </AlertDescription>
          </Alert>
          {desResult.users.creates > 0 && (
            <Alert variant="info">
              <Users aria-hidden="true" />
              <AlertTitle>{desResult.users.creates} usuarios docentes creados automáticamente</AlertTitle>
              <AlertDescription>Los docentes deberán solicitar el restablecimiento de su contraseña al administrador.</AlertDescription>
            </Alert>
          )}
        </div>
      )}

      <ConfirmAlertDialog
        summary={
          confirmDesApply && desPreview && desFile
            ? {
                title: 'Importar designaciones',
                confirmLabel: 'Importar designaciones',
                rows: [
                  { label: 'Archivo', value: desFile.name },
                  { label: 'Período académico', value: desPreview.academic_period },
                  { label: 'Designaciones', value: `${desPreview.designations.creates} nuevas · ${desPreview.designations.updates} se actualizan` },
                  { label: 'Docentes', value: `${desPreview.teachers.creates} nuevos · ${desPreview.teachers.updates} actualizaciones` },
                  { label: 'Cuentas de acceso', value: `${desPreview.users.creates} nuevas · ${desPreview.users.updates} vinculaciones` },
                ],
                warning: desPreview.teachers.updates + desPreview.designations.updates + desPreview.users.updates > 0
                  ? 'Las actualizaciones reemplazan datos ya guardados de docentes, designaciones y cuentas.'
                  : null,
                consequence: 'Los datos se guardan en SIPAD y afectan la planilla del período. No se activa el período académico.',
              }
            : null
        }
        pending={uploadDesignations.isPending}
        onConfirm={handleDesApply}
        onCancel={() => setConfirmDesApply(false)}
      />
    </div>
  )
}
