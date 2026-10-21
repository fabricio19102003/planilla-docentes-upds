import { useMemo, useState } from 'react'
import { CalendarClock, TriangleAlert } from 'lucide-react'

import { useScheduleConflicts } from '@/api/hooks/useScheduleConflicts'
import { useScheduleDrafts } from '@/api/hooks/useSchedulePlanner'
import type { ScheduleConflictsReport } from '@/api/types'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { getTodayInBolivia } from '@/lib/boliviaDates'
import { clashDescription, clashLabel, filterFreeSlots, weekdayLabel } from '@/lib/scheduleConflictsState'
import { apiErrorText } from '@/lib/teacherChangeState'

const selectClass = 'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'

function Summary({ report }: { report: ScheduleConflictsReport }) {
  const items = [
    { label: 'Choques', value: report.summary.conflicts, alert: report.summary.conflicts > 0 },
    { label: 'Avisos', value: report.summary.warnings, alert: false },
    { label: 'Sin docente', value: report.summary.unassigned, alert: report.summary.unassigned > 0 },
    { label: `Docentes con más de ${report.load_threshold} h`, value: report.summary.overloaded_teachers, alert: report.summary.overloaded_teachers > 0 },
    { label: 'Bloques', value: report.summary.blocks, alert: false },
  ]
  return (
    <dl className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {items.map((item) => (
        <div key={item.label} className={`rounded-lg border p-3 ${item.alert ? 'border-red-200 bg-red-50' : 'bg-white'}`}>
          <dt className="text-xs text-slate-600">{item.label}</dt>
          <dd className={`text-2xl font-semibold tabular-nums ${item.alert ? 'text-red-700' : 'text-slate-950'}`}>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Clashes({ report }: { report: ScheduleConflictsReport }) {
  if (!report.clashes.length) return <p className="text-sm text-slate-600">No hay choques de más de {report.tolerance_minutes} minutos.</p>
  return (
    <Table>
      <caption className="sr-only">Choques de docentes, grupos y aulas</caption>
      <TableHeader>
        <TableRow>
          <TableHead>Tipo</TableHead>
          <TableHead>Día</TableHead>
          <TableHead>Se superponen</TableHead>
          <TableHead>Detalle</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {report.clashes.map((clash) => (
          <TableRow key={`${clash.kind}-${clash.keys.join('-')}`}>
            <TableCell>
              <Badge variant={clash.severity === 'conflict' ? 'destructive' : 'outline'}>{clashLabel(clash.kind)}</Badge>
            </TableCell>
            <TableCell>{weekdayLabel(clash.weekday)}</TableCell>
            <TableCell className="tabular-nums">{clash.start_time}–{clash.end_time} ({clash.overlap_minutes} min)</TableCell>
            <TableCell className="whitespace-normal">{clashDescription(clash)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function FreeSlots({ report }: { report: ScheduleConflictsReport }) {
  const [selection, setSelection] = useState('')
  const groups = useMemo(() => {
    const seen = new Map<string, string>()
    for (const item of report.free_slots.groups) {
      seen.set(`group:${item.semester}|${item.group_code}`, `${item.semester ?? '—'}.º ${item.group_code}`)
    }
    return [...seen]
  }, [report])
  const rooms = useMemo(() => [...new Set(report.free_slots.rooms.map((item) => item.classroom_code ?? ''))], [report])
  const slots = filterFreeSlots(report.free_slots, selection)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex max-w-sm flex-col gap-1.5">
        <Label htmlFor="free-slots-target">Grupo o aula</Label>
        <select id="free-slots-target" className={selectClass} value={selection} onChange={(event) => setSelection(event.target.value)}>
          <option value="">Seleccione un grupo o un aula</option>
          <optgroup label="Grupos">{groups.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</optgroup>
          <optgroup label="Aulas">{rooms.map((code) => <option key={code} value={`room:${code}`}>{code}</option>)}</optgroup>
        </select>
      </div>
      {report.summary.blocks_without_room > 0 && selection.startsWith('room:') && (
        <p className="text-sm text-amber-800">
          {report.summary.blocks_without_room} bloques no tienen aula registrada (la teoría vigente sale de las designaciones); un aula puede figurar libre aunque se use.
        </p>
      )}
      {selection && (slots.length ? (
        <ul className="grid gap-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {slots.map((item) => (
            <li key={`${item.weekday}-${item.start_time}`} className="rounded-md border bg-white px-3 py-2 tabular-nums">
              <span className="font-medium">{weekdayLabel(item.weekday)}</span> {item.start_time}–{item.end_time}
              <span className="text-slate-600"> · {item.minutes} min</span>
            </li>
          ))}
        </ul>
      ) : <p className="text-sm text-slate-600">No tiene horarios libres de {report.day_window.min_free_minutes} minutos o más.</p>)}
    </div>
  )
}

export function ScheduleConflictsSection() {
  const [period, setPeriod] = useState('II/2026')
  const [source, setSource] = useState<'current' | 'draft'>('current')
  const [draftId, setDraftId] = useState<number | null>(null)
  const [date, setDate] = useState(getTodayInBolivia())
  const [threshold, setThreshold] = useState(40)
  const drafts = useScheduleDrafts()
  const report = useScheduleConflicts({ period, source, draftId, date, threshold })
  const periodDrafts = (drafts.data ?? []).filter((item) => item.academic_period === period && item.status !== 'archived')
  const data = report.data

  return (
    <section aria-labelledby="conflicts-heading" className="flex flex-col gap-5">
      <div>
        <h2 id="conflicts-heading" className="flex items-center gap-2 text-xl font-semibold text-slate-900">
          <CalendarClock aria-hidden="true" className="size-5 text-sky-700" />Conflictos y huecos
        </h2>
        <p className="text-sm text-slate-500">
          Choques de docentes, grupos y aulas, horarios libres y carga semanal. Las superposiciones de hasta 5 minutos (cambio de aula) no cuentan como choque.
        </p>
      </div>

      <div className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="conflicts-period">Período</Label>
          <Input id="conflicts-period" value={period} onChange={(event) => setPeriod(event.target.value.trim())} placeholder="II/2026" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="conflicts-source">Fuente</Label>
          <select id="conflicts-source" className={selectClass} value={source} onChange={(event) => setSource(event.target.value as 'current' | 'draft')}>
            <option value="current">Vigente</option>
            <option value="draft">Borrador</option>
          </select>
        </div>
        {source === 'draft' && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="conflicts-draft">Borrador</Label>
            <select id="conflicts-draft" className={selectClass} value={draftId ?? ''} onChange={(event) => setDraftId(Number(event.target.value) || null)}>
              <option value="">Seleccione un borrador</option>
              {periodDrafts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="conflicts-date">Fecha</Label>
          <Input id="conflicts-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="conflicts-threshold">Alertar con más de (h/semana)</Label>
          <Input id="conflicts-threshold" type="number" min={1} max={80} value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} />
        </div>
      </div>

      {source === 'draft' && !draftId && <p className="text-sm text-slate-600">Seleccione el borrador que desea revisar.</p>}
      {report.isLoading && <p className="text-sm text-slate-600">Analizando el horario…</p>}
      {report.isError && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>No se pudo analizar el horario</AlertTitle>
          <AlertDescription>{apiErrorText(report.error, 'Revise los filtros e intente nuevamente.')}</AlertDescription>
        </Alert>
      )}

      {data && (
        <>
          <Summary report={data} />
          <Card>
            <CardHeader>
              <CardTitle>Choques</CardTitle>
              <CardDescription>Primero los choques reales; los grupos divididos (teoría y práctica a la vez) se muestran como aviso.</CardDescription>
            </CardHeader>
            <CardContent><Clashes report={data} /></CardContent>
          </Card>
          {data.unassigned.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Sin docente</CardTitle><CardDescription>Bloques sin docente asignado en la fecha elegida.</CardDescription></CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-1 text-sm">
                  {data.unassigned.map((item) => (
                    <li key={item.key}>{item.subject_name} · {item.semester}.º {item.group_code} · {item.start_time}–{item.end_time}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>Carga docente</CardTitle>
              <CardDescription>Horas de clase por semana (duración ÷ hora académica). En rojo, quienes superan {data.load_threshold} h.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <caption className="sr-only">Carga semanal por docente</caption>
                <TableHeader>
                  <TableRow>
                    <TableHead>Docente</TableHead>
                    <TableHead className="text-right">Bloques</TableHead>
                    <TableHead className="text-right">Horas por semana</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.teacher_loads.map((item) => (
                    <TableRow key={item.teacher_ci} className={item.over_threshold ? 'bg-red-50' : undefined}>
                      <TableCell className="font-medium">{item.teacher_name ?? item.teacher_ci}</TableCell>
                      <TableCell className="text-right tabular-nums">{item.blocks}</TableCell>
                      <TableCell className={`text-right tabular-nums ${item.over_threshold ? 'font-semibold text-red-700' : ''}`}>{item.weekly_hours}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Horarios libres</CardTitle>
              <CardDescription>
                Huecos de {data.day_window.min_free_minutes} minutos o más entre las {data.day_window.start_time} y las {data.day_window.end_time}, de lunes a sábado.
              </CardDescription>
            </CardHeader>
            <CardContent><FreeSlots report={data} /></CardContent>
          </Card>
        </>
      )}
    </section>
  )
}
