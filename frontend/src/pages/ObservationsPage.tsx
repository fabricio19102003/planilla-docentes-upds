import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { useObservations } from '@/api/hooks/useAttendance'
import { DataTable } from '@/components/shared/DataTable'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import type { Tone } from '@/components/shared/tones'

import { Card, CardContent } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import type { Observation } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

function formatTime(t: string): string {
  if (!t) return '—'
  return t.slice(0, 5)
}

const MONTH_ITEMS = Object.entries(MONTH_NAMES).map(([value, label]) => ({ value, label }))

const STATUS_CONFIG: Record<string, { label: string; tone: Tone }> = {
  LATE: { label: 'Tardanza', tone: 'warning' },
  ABSENT: { label: 'Ausente', tone: 'destructive' },
  NO_EXIT: { label: 'Sin Salida', tone: 'info' },
}

const observationColumns: Column<Observation>[] = [
  {
    key: 'teacher_name',
    header: 'Docente',
    render: (item) => (
      <span className="font-medium">{item.teacher_name ?? item.teacher_ci}</span>
    ),
  },
  { key: 'subject', header: 'Materia' },
  { key: 'group_code', header: 'Grupo' },
  {
    key: 'date',
    header: 'Fecha',
    className: 'tabular-nums',
    render: (item) => formatDate(item.date),
  },
  {
    key: 'scheduled_start',
    header: 'Horario',
    className: 'tabular-nums',
    render: (item) => `${formatTime(item.scheduled_start)} - ${formatTime(item.scheduled_end)}`,
  },
  {
    key: 'status',
    header: 'Estado',
    render: (item) => {
      const cfg = STATUS_CONFIG[item.status] ?? { label: item.status, tone: 'neutral' as Tone }
      return <StatusBadge tone={cfg.tone}>{cfg.label}</StatusBadge>
    },
  },
  {
    key: 'late_minutes',
    header: 'Minutos de Tardanza',
    align: 'right',
    render: (item) => item.late_minutes > 0 ? `${item.late_minutes} min` : '—',
  },
  {
    key: 'observation',
    header: 'Observación',
    render: (item) => (
      <span className="block max-w-[200px] truncate text-xs text-muted-foreground">
        {item.observation ?? '—'}
      </span>
    ),
  },
]

const TABS = [
  { value: '', label: 'Todas' },
  { value: 'LATE', label: 'Tardanzas' },
  { value: 'ABSENT', label: 'Ausencias' },
  { value: 'NO_EXIT', label: 'Sin Salida' },
]

export function ObservationsPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [activeTab, setActiveTab] = useState<string>('')

  const { data: observations, isLoading } = useObservations(
    month,
    year,
    activeTab || undefined,
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Observaciones de asistencia"
        description="Tardanzas, ausencias y salidas sin marcar del mes seleccionado."
      />

      {/* Controls */}
      <Card>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:max-w-sm">
            <Field>
              <FieldLabel>Mes</FieldLabel>
              <Select
                value={String(month)}
                items={MONTH_ITEMS}
                onValueChange={(v) => setMonth(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectPopup>
                  {MONTH_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>

            <Field>
              <FieldLabel>Año</FieldLabel>
              <Input
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                min={2020}
                max={2030}
                inputClassName="tabular-nums"
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      {/* Observations Table with Tabs */}
      <section className="space-y-3">
        <h3 className="text-base font-semibold text-foreground">
          Observaciones — {MONTH_NAMES[month]} {year}
        </h3>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="max-w-full overflow-x-auto">
            {TABS.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.label}
                {tab.value !== '' && observations && (
                  <span className="ml-1.5 text-xs tabular-nums">
                    ({observations.filter((o) => o.status === tab.value).length})
                  </span>
                )}
                {tab.value === '' && observations && (
                  <span className="ml-1.5 text-xs tabular-nums">({observations.length})</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>

          {TABS.map((tab) => (
            <TabsContent key={tab.value} value={tab.value}>
              {isLoading ? (
                <DataTable columns={observationColumns} data={[]} loading />
              ) : !observations?.length ? (
                <Card>
                  <EmptyState icon={AlertTriangle} title="No hay observaciones para este período" />
                </Card>
              ) : (
                <DataTable
                  columns={observationColumns}
                  data={observations}
                  emptyMessage="No hay observaciones para esta categoría"
                />
              )}
            </TabsContent>
          ))}
        </Tabs>
      </section>
    </div>
  )
}
