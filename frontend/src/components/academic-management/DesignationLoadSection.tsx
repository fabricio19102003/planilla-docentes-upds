import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, DoorOpen, FileSpreadsheet, TriangleAlert } from 'lucide-react'

import {
  useApplyClassroomCatalog,
  useApplyDesignationLoad,
  usePreviewClassroomCatalog,
  usePreviewDesignationLoad,
} from '@/api/hooks/useScheduleConflicts'
import type { ClassroomCatalogPlan, DesignationLoadPreview, DesignationLoadResult } from '@/api/types'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { getTodayInBolivia } from '@/lib/boliviaDates'
import { clashDescription, clashLabel, weekdayLabel } from '@/lib/scheduleConflictsState'
import type { DesignationLoadForm } from '@/lib/scheduleConflictsState'
import { apiErrorText } from '@/lib/teacherChangeState'

const FIELD_LABEL: Record<string, string> = { name: 'nombre', capacity: 'capacidad', classroom_type: 'tipo', active: 'activa' }

function CatalogPlan({ plan }: { plan: ClassroomCatalogPlan }) {
  return (
    <div className="flex flex-col gap-2 text-sm">
      <p>
        {plan.create.length} aulas nuevas, {plan.update.length} corregidas, {plan.unchanged} sin cambios.
      </p>
      {plan.create.length > 0 && <p className="text-slate-600">Nuevas: {plan.create.map((item) => item.code).join(', ')}.</p>}
      {plan.update.length > 0 && (
        <ul className="list-disc pl-5 text-slate-600">
          {plan.update.map((item) => (
            <li key={item.code}>
              {item.code}: {Object.entries(item.changes).map(([field, [before, after]]) => `${FIELD_LABEL[field] ?? field} ${String(before)} → ${String(after)}`).join(', ')}
            </li>
          ))}
        </ul>
      )}
      {plan.conflicts.length > 0 && (
        <Alert>
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>Aulas con otro edificio o piso</AlertTitle>
          <AlertDescription>
            Estas aulas existen con un código que no coincide con el catálogo; no se modifican porque pueden estar en horarios publicados:{' '}
            {plan.conflicts.map((item) => `${item.code} (catálogo: ${item.catalog_code})`).join(', ')}.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

function ClassroomCatalogCard() {
  const preview = usePreviewClassroomCatalog()
  const apply = useApplyClassroomCatalog()
  const plan = apply.data ?? preview.data
  const pending = preview.data && (preview.data.create.length > 0 || preview.data.update.length > 0)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><DoorOpen aria-hidden="true" className="size-5 text-sky-700" />Catálogo de aulas</CardTitle>
        <CardDescription>
          Edificio antiguo: aulas 1 a 10, A y B. Edificio nuevo: aulas 11 a 29 (pisos 2 a 4). Revise los cambios antes de aplicarlos.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => { apply.reset(); preview.mutate() }} disabled={preview.isPending}>
            {preview.isPending ? 'Revisando…' : 'Revisar catálogo'}
          </Button>
          <Button type="button" onClick={() => apply.mutate()} disabled={!pending || apply.isPending || apply.isSuccess}>
            {apply.isPending ? 'Aplicando…' : 'Aplicar catálogo'}
          </Button>
        </div>
        {(preview.isError || apply.isError) && (
          <p role="alert" className="text-sm text-red-700">{apiErrorText(preview.error ?? apply.error, 'No se pudo revisar el catálogo de aulas.')}</p>
        )}
        {apply.isSuccess && <p className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 aria-hidden="true" className="size-4" />Catálogo aplicado.</p>}
        {plan && <CatalogPlan plan={plan} />}
      </CardContent>
    </Card>
  )
}

function LoadPreview({ preview }: { preview: DesignationLoadPreview }) {
  const { create, counts } = preview
  return (
    <div className="flex flex-col gap-4 text-sm">
      {preview.blockers.length > 0 && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>No se puede crear el borrador</AlertTitle>
          <AlertDescription>
            <Table>
              <caption className="sr-only">Filas que impiden la carga</caption>
              <TableHeader>
                <TableRow><TableHead>Designación</TableHead><TableHead>Materia</TableHead><TableHead>Grupo</TableHead><TableHead>Motivo</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {preview.blockers.map((item, index) => (
                  <TableRow key={`${item.code}-${item.designation_id}-${index}`}>
                    <TableCell>{item.designation_id ?? '—'}</TableCell>
                    <TableCell>{item.subject ?? '—'}</TableCell>
                    <TableCell>{item.semester ? `${item.semester} ${item.group_code}` : '—'}</TableCell>
                    <TableCell className="whitespace-normal">{item.message}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AlertDescription>
        </Alert>
      )}
      <p>
        <span className="font-medium">{preview.draft_name}</span>: {counts.designations} designaciones, {counts.blocks} bloques y {counts.assignments} asignaciones docentes.
      </p>
      <ul className="list-disc pl-5 text-slate-700">
        <li>Materias nuevas: {create.subjects.length ? create.subjects.join(', ') : 'ninguna'}.</li>
        <li>Ofertas nuevas: {create.offerings}. Grupos nuevos: {create.groups.length ? create.groups.join(', ') : 'ninguno'}.</li>
        <li>Aulas del catálogo que se crean: {create.classrooms.length ? create.classrooms.join(', ') : 'ninguna'}.</li>
        <li>Disponibilidad docente que se agrega (06:30–23:05 en los días con clase): {create.availability}.</li>
      </ul>
      <section aria-labelledby="load-conflicts" className="flex flex-col gap-2">
        <h3 id="load-conflicts" className="font-semibold text-slate-950">
          Choques que tendrá el borrador: {preview.conflicts.summary.conflicts} (avisos: {preview.conflicts.summary.warnings})
        </h3>
        <p className="text-slate-600">No impiden crear el borrador: corríjalos en el planificador o revíselos en Conflictos y huecos.</p>
        {preview.conflicts.clashes.length > 0 && (
          <ul className="flex flex-col gap-1">
            {preview.conflicts.clashes.slice(0, 20).map((clash) => (
              <li key={`${clash.kind}-${clash.keys.join('-')}`}>
                <span className="font-medium">{clashLabel(clash.kind)}</span> · {weekdayLabel(clash.weekday)} {clash.start_time}–{clash.end_time}: {clashDescription(clash)}
              </li>
            ))}
            {preview.conflicts.clashes.length > 20 && <li className="text-slate-600">… y {preview.conflicts.clashes.length - 20} más.</li>}
          </ul>
        )}
      </section>
    </div>
  )
}

export function DesignationLoadSection() {
  const [period, setPeriod] = useState('II/2026')
  const [effectiveFrom, setEffectiveFrom] = useState(getTodayInBolivia())
  const [file, setFile] = useState<File | null>(null)
  const [previewedForm, setPreviewedForm] = useState<DesignationLoadForm | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [result, setResult] = useState<DesignationLoadResult | null>(null)
  const preview = usePreviewDesignationLoad()
  const apply = useApplyDesignationLoad()
  const current = file ? { period, effectiveFrom, file } : null
  const previewMatches = Boolean(previewedForm && current && previewedForm.period === current.period
    && previewedForm.effectiveFrom === current.effectiveFrom && previewedForm.file === current.file)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!current) return
    setResult(null)
    apply.reset()
    preview.mutate(current, { onSuccess: () => setPreviewedForm(current) })
  }

  const confirm = () => {
    if (!previewedForm || !preview.data) return
    apply.mutate({ form: previewedForm, digest: preview.data.digest }, {
      onSuccess: (data) => { setResult(data); setConfirmOpen(false) },
      onError: () => setConfirmOpen(false),
    })
  }

  return (
    <section aria-labelledby="designation-load-heading" className="flex flex-col gap-5">
      <div>
        <h2 id="designation-load-heading" className="flex items-center gap-2 text-xl font-semibold text-slate-900">
          <FileSpreadsheet aria-hidden="true" className="size-5 text-sky-700" />Cargar designación al módulo
        </h2>
        <p className="text-sm text-slate-500">
          Crea un borrador de horario con la teoría vigente (las designaciones) y el aula de cada clase según la columna AULA del Excel. El borrador no cambia pagos hasta publicarse.
        </p>
      </div>

      <ClassroomCatalogCard />

      <Card>
        <CardHeader>
          <CardTitle>Designación vigente</CardTitle>
          <CardDescription>Use el mismo Excel de designación (hoja DOCENTES TEORICOS) con la columna AULA completa.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="load-period">Período</Label>
              <Input id="load-period" required value={period} onChange={(event) => setPeriod(event.target.value.trim())} placeholder="II/2026" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="load-date">Vigente desde</Label>
              <Input id="load-date" type="date" required value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="load-workbook">Excel de designación</Label>
              <Input id="load-workbook" type="file" required accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </div>
            <Button type="submit" disabled={!current || preview.isPending}>{preview.isPending ? 'Analizando…' : 'Vista previa'}</Button>
          </form>
          {preview.isError && <p role="alert" className="text-sm text-red-700">{apiErrorText(preview.error, 'No se pudo analizar la designación.')}</p>}
          {apply.isError && <p role="alert" className="text-sm text-red-700">{apiErrorText(apply.error, 'No se pudo crear el borrador.')}</p>}
          {preview.data && previewMatches && !result && (
            <>
              <LoadPreview preview={preview.data} />
              <div>
                <Button type="button" onClick={() => setConfirmOpen(true)} disabled={!preview.data.can_apply || apply.isPending}>Crear borrador</Button>
              </div>
            </>
          )}
          {result && (
            <Alert>
              <CheckCircle2 aria-hidden="true" />
              <AlertTitle>Borrador creado</AlertTitle>
              <AlertDescription>
                {result.draft_name}: {result.blocks} bloques y {result.assignments} asignaciones. Choques a revisar: {result.conflicts.conflicts}.{' '}
                <Link className="font-medium text-sky-700 underline" to={`/schedule-planner?draft=${result.draft_id}`}>Abrir en el planificador</Link>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Crear el borrador de horario?</DialogTitle>
            <DialogDescription>
              Se crea «{preview.data?.draft_name}» con {preview.data?.counts.blocks ?? 0} bloques, junto con las materias, grupos, aulas y disponibilidades que faltan. Las designaciones y los pagos no cambian.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirmOpen(false)}>Cancelar</Button>
            <Button type="button" onClick={confirm} disabled={apply.isPending}>{apply.isPending ? 'Creando…' : 'Crear borrador'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
