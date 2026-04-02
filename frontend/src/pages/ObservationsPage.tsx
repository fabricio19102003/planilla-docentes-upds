import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { useObservations } from '@/api/hooks/useAttendance'
import { DataTable } from '@/components/shared/DataTable'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
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

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  LATE: { label: 'Tardanza', className: 'bg-yellow-100 text-yellow-700' },
  ABSENT: { label: 'Ausente', className: 'bg-red-100 text-red-700' },
  NO_EXIT: { label: 'Sin Salida', className: 'bg-orange-100 text-orange-700' },
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
    render: (item) => formatDate(item.date),
  },
  {
    key: 'scheduled_start',
    header: 'Horario',
    render: (item) => `${formatTime(item.scheduled_start)} - ${formatTime(item.scheduled_end)}`,
  },
  {
    key: 'status',
    header: 'Estado',
    render: (item) => {
      const cfg = STATUS_CONFIG[item.status] ?? { label: item.status, className: 'bg-gray-100 text-gray-700' }
      return <Badge className={cfg.className}>{cfg.label}</Badge>
    },
  },
  {
    key: 'late_minutes',
    header: 'Minutos de Tardanza',
    render: (item) => item.late_minutes > 0 ? `${item.late_minutes} min` : '—',
  },
  {
    key: 'observation',
    header: 'Observación',
    render: (item) => (
      <span className="text-gray-500 text-xs max-w-[200px] truncate block">
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
      {/* Controls */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Mes</label>
              <select
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] min-w-[130px]"
              >
                {Object.entries(MONTH_NAMES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Año</label>
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                min={2020}
                max={2030}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] w-24"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Observations Table with Tabs */}
      <Card>
        <CardHeader>
          <CardTitle style={{ color: '#003366' }}>
            Observaciones — {MONTH_NAMES[month]} {year}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              {TABS.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value}>
                  {tab.label}
                  {tab.value !== '' && observations && (
                    <span className="ml-1.5 text-xs">
                      ({observations.filter((o) => o.status === tab.value).length})
                    </span>
                  )}
                  {tab.value === '' && observations && (
                    <span className="ml-1.5 text-xs">({observations.length})</span>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>

            {TABS.map((tab) => (
              <TabsContent key={tab.value} value={tab.value}>
                {isLoading ? (
                  <LoadingPage />
                ) : !observations?.length ? (
                  <div className="py-16 text-center">
                    <AlertTriangle size={36} className="mx-auto text-gray-300 mb-3" />
                    <p className="text-gray-400">
                      No hay observaciones para este período
                    </p>
                  </div>
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
        </CardContent>
      </Card>
    </div>
  )
}
