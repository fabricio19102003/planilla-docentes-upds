import { useMemo, useState } from 'react'
import { ArrowRightLeft, CheckCircle2, TriangleAlert } from 'lucide-react'

import { useAcademicTeacherSearch } from '@/api/hooks/useAcademicManagement'
import { useApplyTeacherChange, usePreviewTeacherChange, useTeacherDesignations } from '@/api/hooks/useTeacherChange'
import type { DesignationChangePreview, DesignationChangeResult, DesignationChangeTeacherImpact } from '@/api/types'
import { TeacherCombobox } from '@/components/academic-management/TeacherCombobox'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { getTodayInBolivia } from '@/lib/boliviaDates'
import { TEACHER_SEARCH_PAGE_SIZE } from '@/lib/academicManagementState'
import { activeDesignations, apiErrorText, changeRequestBody, formatBs, impactRows, impactTotals, outgoingUntil } from '@/lib/teacherChangeState'

const selectClass = 'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'
const ALL = 'all'
const PLANILLA_LABEL = { regular: 'teoría', practice: 'práctica' } as const

function useTeacherPicker() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const query = useAcademicTeacherSearch(search, page)
  const pageCount = Math.max(1, Math.ceil((query.data?.total ?? 0) / TEACHER_SEARCH_PAGE_SIZE))
  return { search, setSearch, page, setPage, query, pageCount }
}

export function ImpactTable({ teachers, caption }: { teachers: DesignationChangeTeacherImpact[]; caption: string }) {
  const rows = impactRows(teachers)
  const totals = impactTotals(teachers)
  if (!rows.length) return <p className="text-sm text-slate-600">No cambia lo que cobra ningún docente en ese mes.</p>
  return (
    <Table>
      <caption className="sr-only">{caption}</caption>
      <TableHeader>
        <TableRow>
          <TableHead>Docente</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead className="text-right">Horas antes</TableHead>
          <TableHead className="text-right">Horas después</TableHead>
          <TableHead className="text-right">Antes</TableHead>
          <TableHead className="text-right">Después</TableHead>
          <TableHead className="text-right">Diferencia</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.teacher_ci}-${row.activity}`}>
            <TableCell className="font-medium">{row.teacher_name}</TableCell>
            <TableCell>{row.activity === 'theory' ? 'Teoría' : 'Práctica'}</TableCell>
            <TableCell className="text-right tabular-nums">{row.hours_before}</TableCell>
            <TableCell className="text-right tabular-nums">{row.hours_after}</TableCell>
            <TableCell className="text-right tabular-nums">{formatBs(row.amount_before)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatBs(row.amount_after)}</TableCell>
            <TableCell className={`text-right tabular-nums ${row.amount_delta < 0 ? 'text-red-700' : row.amount_delta > 0 ? 'text-emerald-700' : ''}`}>
              {row.amount_delta > 0 ? '+' : ''}{formatBs(row.amount_delta)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell colSpan={4}>Total</TableCell>
          <TableCell className="text-right tabular-nums">{formatBs(totals.before)}</TableCell>
          <TableCell className="text-right tabular-nums">{formatBs(totals.after)}</TableCell>
          <TableCell className="text-right tabular-nums">{totals.delta > 0 ? '+' : ''}{formatBs(totals.delta)}</TableCell>
        </TableRow>
      </TableFooter>
    </Table>
  )
}

function PreviewResult({ preview }: { preview: DesignationChangePreview }) {
  return (
    <div className="flex flex-col gap-4">
      {preview.blockers.length > 0 && (
        <Alert variant="error">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>El cambio no se puede aplicar</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {preview.blockers.map((item, index) => <li key={`${item.code}-${index}`}>{item.message}</li>)}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {preview.warnings.length > 0 && (
        <Alert>
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>Avisos</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">{preview.warnings.map((item) => <li key={item}>{item}</li>)}</ul>
          </AlertDescription>
        </Alert>
      )}
      {preview.regenerate.length > 0 && (
        <Alert>
          <AlertTitle>Planillas para regenerar</AlertTitle>
          <AlertDescription>
            Después de aplicar, regenerá: {preview.regenerate.map((item) => `${PLANILLA_LABEL[item.planilla]} ${item.month}/${item.year}`).join(', ')}.
          </AlertDescription>
        </Alert>
      )}
      <section aria-labelledby="teacher-change-items" className="flex flex-col gap-2">
        <h3 id="teacher-change-items" className="font-semibold text-slate-950">Designaciones que cambian</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {preview.items.map((item) => (
            <li key={item.designation_id} className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{item.designation_type === 'practice' ? 'Práctica' : 'Teoría'}</Badge>
              <span className="font-medium">{item.subject}</span>
              <span className="text-slate-600">Sem. {item.semester} · {item.group_code}</span>
              <span className="text-slate-600">saliente hasta {item.outgoing_until}, entrante desde {item.incoming_from}{item.incoming_until ? ` hasta ${item.incoming_until}` : ''}</span>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="teacher-change-impact" className="flex flex-col gap-2">
        <h3 id="teacher-change-impact" className="font-semibold text-slate-950">
          Pago base de {preview.impact.month}/{preview.impact.year} (antes de descuentos por asistencia)
        </h3>
        <ImpactTable teachers={preview.impact.teachers} caption="Impacto del cambio en la planilla por docente" />
      </section>
    </div>
  )
}

export function TeacherChangeSection() {
  const [period, setPeriod] = useState('II/2026')
  const [effectiveFrom, setEffectiveFrom] = useState(getTodayInBolivia())
  const [outgoingCi, setOutgoingCi] = useState('')
  const [incomingCi, setIncomingCi] = useState('')
  const [selection, setSelection] = useState<string>(ALL)
  const [previewedKey, setPreviewedKey] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [applied, setApplied] = useState<DesignationChangeResult | null>(null)
  const outgoing = useTeacherPicker()
  const incoming = useTeacherPicker()
  const designations = useTeacherDesignations(period, outgoingCi)
  const preview = usePreviewTeacherChange()
  const apply = useApplyTeacherChange()

  const active = useMemo(
    () => activeDesignations(designations.data ?? [], effectiveFrom),
    [designations.data, effectiveFrom],
  )
  const designationId = selection === ALL ? null : Number(selection)
  const body = changeRequestBody({ period, effectiveFrom, incomingCi, outgoingCi, designationId })
  const bodyKey = body ? JSON.stringify(body) : null
  const previewIsCurrent = Boolean(bodyKey && previewedKey === bodyKey && preview.data)

  const resetPreview = () => { setPreviewedKey(null); setApplied(null); preview.reset(); apply.reset() }

  const runPreview = () => {
    if (!body) return
    setApplied(null)
    apply.reset()
    preview.mutate(body, { onSuccess: () => setPreviewedKey(JSON.stringify(body)) })
  }

  const confirmApply = () => {
    if (!body) return
    apply.mutate(body, {
      onSuccess: (result) => { setApplied(result); setConfirmOpen(false); setPreviewedKey(null); preview.reset() },
      onError: () => setConfirmOpen(false),
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ArrowRightLeft className="size-5" aria-hidden="true" />Cambiar docente</CardTitle>
        <CardDescription>
          Cuando un docente deja una materia, se le paga hasta el día anterior al cambio y el docente entrante cobra desde la fecha del cambio.
          Aplica a las designaciones; para un horario publicado, reemplazá al docente desde el planificador y volvé a publicar.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="teacher-change-period">Período académico</Label>
            <Input id="teacher-change-period" value={period} onChange={(event) => { setPeriod(event.target.value.trim()); setSelection(ALL); resetPreview() }} placeholder="II/2026" />
          </div>
          <div>
            <Label htmlFor="teacher-change-date">Fecha del cambio</Label>
            <Input id="teacher-change-date" type="date" value={effectiveFrom} onChange={(event) => { setEffectiveFrom(event.target.value); resetPreview() }} aria-describedby="teacher-change-date-help" />
            <p id="teacher-change-date-help" className="mt-1 text-xs text-slate-500">
              {effectiveFrom ? `El docente saliente cobra hasta el ${outgoingUntil(effectiveFrom)}.` : 'Elegí la fecha desde la que enseña el docente entrante.'}
            </p>
          </div>
          <div>
            <Label htmlFor="teacher-change-outgoing">Docente saliente</Label>
            <TeacherCombobox
              id="teacher-change-outgoing"
              teachers={outgoing.query.data?.items ?? []}
              value={outgoingCi}
              onChange={(ci) => { setOutgoingCi(ci); setSelection(ALL); resetPreview() }}
              search={outgoing.search}
              onSearchChange={(value) => { outgoing.setSearch(value); outgoing.setPage(1) }}
              loading={outgoing.query.isLoading}
              page={outgoing.page}
              pageCount={outgoing.pageCount}
              onPageChange={outgoing.setPage}
            />
          </div>
          <div>
            <Label htmlFor="teacher-change-incoming">Docente entrante</Label>
            <TeacherCombobox
              id="teacher-change-incoming"
              teachers={incoming.query.data?.items ?? []}
              value={incomingCi}
              onChange={(ci) => { setIncomingCi(ci); resetPreview() }}
              search={incoming.search}
              onSearchChange={(value) => { incoming.setSearch(value); incoming.setPage(1) }}
              loading={incoming.query.isLoading}
              page={incoming.page}
              pageCount={incoming.pageCount}
              onPageChange={incoming.setPage}
            />
          </div>
          <div className="md:col-span-2">
            <Label htmlFor="teacher-change-scope">Qué cambia</Label>
            <select
              id="teacher-change-scope"
              className={selectClass}
              value={selection}
              disabled={!outgoingCi || designations.isLoading}
              onChange={(event) => { setSelection(event.target.value); resetPreview() }}
            >
              <option value={ALL}>Todas sus designaciones activas en esa fecha ({active.length})</option>
              {active.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.subject} · Sem. {item.semester} · {item.group_code} · {item.designation_type === 'practice' ? 'Práctica' : 'Teoría'}{item.schedule_raw ? ` · ${item.schedule_raw}` : ''}
                </option>
              ))}
            </select>
            {designations.isError && <p role="alert" className="mt-1 text-sm text-red-700">No se pudieron cargar las designaciones del docente.</p>}
            {outgoingCi && designations.isSuccess && active.length === 0 && (
              <p className="mt-1 text-sm text-slate-600">Este docente no tiene designaciones activas en {period} para esa fecha.</p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" disabled={!body || preview.isPending} onClick={runPreview}>
            {preview.isPending ? 'Calculando…' : 'Vista previa'}
          </Button>
          <Button type="button" disabled={!previewIsCurrent || !preview.data?.can_apply || apply.isPending} onClick={() => setConfirmOpen(true)}>
            Aplicar cambio
          </Button>
        </div>

        {preview.isError && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{apiErrorText(preview.error, 'No se pudo calcular la vista previa.')}</p>}
        {apply.isError && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{apiErrorText(apply.error, 'No se pudo aplicar el cambio.')}</p>}
        {previewIsCurrent && preview.data && <PreviewResult preview={preview.data} />}
        {applied && (
          <Alert role="status">
            <CheckCircle2 aria-hidden="true" />
            <AlertTitle>Cambio aplicado</AlertTitle>
            <AlertDescription>
              {applied.ended_designation_ids.length} designación(es) terminan el {outgoingUntil(effectiveFrom)} y se crearon {applied.created_designation_ids.length} para el docente entrante.
              {applied.regenerate.length > 0 && ` Regenerá: ${applied.regenerate.map((item) => `${PLANILLA_LABEL[item.planilla]} ${item.month}/${item.year}`).join(', ')}.`}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogPopup>
          <DialogHeader>
            <DialogTitle>¿Aplicar el cambio de docente?</DialogTitle>
            <DialogDescription>
              Se modifican {preview.data?.items.length ?? 0} designación(es) desde el {effectiveFrom}. La planilla de esos días pasará a pagarse al docente entrante.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirmOpen(false)}>Cancelar</Button>
            <Button type="button" onClick={confirmApply} disabled={apply.isPending}>{apply.isPending ? 'Aplicando…' : 'Aplicar cambio'}</Button>
          </DialogFooter>
        </DialogPopup>
      </Dialog>
    </Card>
  )
}
