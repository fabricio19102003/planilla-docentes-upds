import { useState, useEffect } from 'react'
import { ClipboardCheck, Loader2, Info } from 'lucide-react'
import {
  useAttendance,
  useAttendanceSummary,
  useProcessAttendance,
} from '@/api/hooks/useAttendance'
import { useUploadHistory, useBiometricDateRange } from '@/api/hooks/useBiometric'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { DataTable } from '@/components/shared/DataTable'
import type { Tone } from '@/components/shared/tones'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import type { AttendanceWithDetails } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'
import { Users, AlertTriangle, XCircle, Clock } from 'lucide-react'

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

function formatIsoDate(isoDate: string): string {
  return isoDate ? isoDate.split('-').reverse().join('/') : '—'
}

function formatTime(timeStr: string | null): string {
  if (!timeStr) return '—'
  return timeStr.slice(0, 5)
}

const MONTH_ITEMS = Object.entries(MONTH_NAMES).map(([value, label]) => ({ value, label }))

const STATUS_CONFIG: Record<string, { label: string; tone: Tone }> = {
  ATTENDED: { label: 'Asistió', tone: 'success' },
  LATE: { label: 'Tardanza', tone: 'warning' },
  ABSENT: { label: 'Ausente', tone: 'destructive' },
  NO_EXIT: { label: 'Sin Salida', tone: 'info' },
}

const attendanceColumns: Column<AttendanceWithDetails>[] = [
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
    key: 'actual_entry',
    header: 'Entrada',
    className: 'tabular-nums',
    render: (item) => formatTime(item.actual_entry),
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
    key: 'academic_hours',
    header: 'Horas',
    align: 'right',
    render: (item) => `${item.academic_hours}h`,
  },
]

export function AttendancePage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [page, setPage] = useState(1)
  const [processed, setProcessed] = useState(false)
  const [selectedUploadId, setSelectedUploadId] = useState<number | null>(null)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [datesManuallySet, setDatesManuallySet] = useState(false)
  const [confirmingProcess, setConfirmingProcess] = useState(false)

  const { data: bioRange } = useBiometricDateRange(month, year)

  // Reset manual flag when month/year changes so auto-fill can run again
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Month/year changes intentionally reset the manual override flag.
    setDatesManuallySet(false)
  }, [month, year])

  // Auto-fill dates from biometric range when available
  useEffect(() => {
    if (!datesManuallySet && bioRange?.has_data && bioRange.suggested_start && bioRange.suggested_end) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Form defaults are derived from async biometric coverage data.
      setStartDate(bioRange.suggested_start)
      setEndDate(bioRange.suggested_end)
    } else if (!datesManuallySet && bioRange !== undefined && !bioRange.has_data) {
      // No biometric data: fall back to standard cut-off period
      const prevMonth = month === 1 ? 12 : month - 1
      const prevYear = month === 1 ? year - 1 : year
      setStartDate(`${prevYear}-${String(prevMonth).padStart(2, '0')}-21`)
      setEndDate(`${year}-${String(month).padStart(2, '0')}-20`)
    }
  }, [bioRange, datesManuallySet, month, year])

  const { data: uploads } = useUploadHistory()
  const processAttendance = useProcessAttendance()

  const { data: summary, isLoading: summaryLoading } = useAttendanceSummary(month, year)
  const { data: records, isLoading: recordsLoading } = useAttendance({
    month,
    year,
    page,
    perPage: 15,
  })

  const totalPages = records ? Math.ceil(records.total / 15) : 1

  const handleProcess = () => {
    if (!selectedUploadId) return
    processAttendance.mutate(
      {
        upload_id: selectedUploadId,
        month,
        year,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      },
      {
        onSuccess: () => setProcessed(true),
        onSettled: () => setConfirmingProcess(false),
      },
    )
  }

  const hasData = summary && (summary.attended + summary.late + summary.absent + summary.no_exit > 0)
  const selectedUpload = uploads?.find((u) => u.id === selectedUploadId)
  const uploadItems = (uploads ?? []).map((u) => ({
    value: String(u.id),
    label: `${u.filename} — ${MONTH_NAMES[u.month]} ${u.year}`,
  }))
  const extendsBeyondBiometric = Boolean(
    bioRange?.has_data && startDate && endDate &&
    (startDate < (bioRange.suggested_start ?? '') || endDate > (bioRange.suggested_end ?? '')),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Procesamiento de asistencia"
        description="Procesá el reporte biométrico y revisá los registros de asistencia del mes."
      />

      {/* Controls */}
      <Card>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-[10rem_7rem_minmax(0,1fr)_auto] lg:items-end">
            <Field>
              <FieldLabel>Mes</FieldLabel>
              <Select
                value={String(month)}
                items={MONTH_ITEMS}
                onValueChange={(v) => { setMonth(Number(v)); setPage(1) }}
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
                onChange={(e) => { setYear(Number(e.target.value)); setPage(1) }}
                min={2020}
                max={2030}
                inputClassName="tabular-nums"
              />
            </Field>

            <Field>
              <FieldLabel>Upload biométrico</FieldLabel>
              <Select
                value={selectedUploadId === null ? null : String(selectedUploadId)}
                items={uploadItems}
                onValueChange={(v) => setSelectedUploadId(v ? Number(v) : null)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccioná un upload" />
                </SelectTrigger>
                <SelectPopup>
                  {uploadItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>

            <Button
              onClick={() => setConfirmingProcess(true)}
              disabled={!selectedUploadId || processAttendance.isPending}
              size="lg"
              className="sm:col-span-2 lg:col-span-1"
            >
              {processAttendance.isPending ? (
                <>
                  <Loader2 className="animate-spin" />
                  Procesando...
                </>
              ) : (
                <>
                  <ClipboardCheck />
                  Procesar Asistencia
                </>
              )}
            </Button>
          </div>

          <div className="space-y-3 border-t pt-5">
            <p className="text-sm font-medium text-foreground">Período de corte</p>

            {/* Biometric Coverage Info */}
            {bioRange && (
              bioRange.has_data ? (
                <Alert variant="info">
                  <Info />
                  <AlertTitle>Rango biométrico detectado</AlertTitle>
                  <AlertDescription className="gap-1 text-xs">
                    <p>{bioRange.message}</p>
                    <p>
                      Las fechas de inicio y fin se han ajustado automáticamente al rango del biométrico.
                      Puede modificarlas si lo necesita.
                    </p>
                  </AlertDescription>
                </Alert>
              ) : (
                <Alert variant="warning">
                  <AlertTriangle />
                  <AlertTitle>Sin datos biométricos</AlertTitle>
                  <AlertDescription className="text-xs">{bioRange.message}</AlertDescription>
                </Alert>
              )
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-[12rem_12rem_minmax(0,1fr)] lg:items-end">
              <Field>
                <FieldLabel>Fecha inicio</FieldLabel>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => { setStartDate(e.target.value); setDatesManuallySet(true) }}
                />
              </Field>
              <Field>
                <FieldLabel>Fecha fin</FieldLabel>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => { setEndDate(e.target.value); setDatesManuallySet(true) }}
                />
              </Field>
              <p className="text-xs text-muted-foreground sm:col-span-2 lg:col-span-1 lg:pb-2">
                Estándar: del 21 del mes anterior al 20 del mes actual
              </p>
            </div>

            {/* Warning: dates extend beyond biometric coverage */}
            {extendsBeyondBiometric && bioRange && (
              <Alert variant="warning">
                <AlertTriangle />
                <AlertTitle>Rango extendido más allá del biométrico</AlertTitle>
                <AlertDescription className="text-xs">
                  El rango seleccionado ({startDate} — {endDate}) excede la cobertura del biométrico
                  ({bioRange.suggested_start} — {bioRange.suggested_end}). Los días sin cobertura generarán
                  ausencias para todos los docentes con biométrico.
                </AlertDescription>
              </Alert>
            )}
          </div>

          {processAttendance.isError && (
            <Alert variant="error">
              <XCircle />
              <AlertDescription>
                Error al procesar. Verificá que el upload corresponda al mes seleccionado.
              </AlertDescription>
            </Alert>
          )}
          {(processAttendance.isSuccess || processed) && (
            <Alert variant="success">
              <ClipboardCheck />
              <AlertDescription>
                ✓ Asistencia procesada exitosamente
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Summary Cards */}
      {summaryLoading ? (
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4" role="status" aria-label="Cargando resumen">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
      ) : hasData ? (
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <StatCard icon={Users} title="Asistencias" value={summary.attended} tone="success" />
          <StatCard icon={Clock} title="Tardanzas" value={summary.late} tone="warning" />
          <StatCard icon={XCircle} title="Ausencias" value={summary.absent} tone="destructive" />
          <StatCard icon={AlertTriangle} title="Sin Salida" value={summary.no_exit} tone="info" />
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={ClipboardCheck}
            title="Seleccioná un mes y procesá la asistencia para ver los resultados"
            description="Asegurate de haber subido el reporte biométrico primero"
          />
        </Card>
      )}

      {/* Records Table */}
      {hasData && (
        <section className="space-y-3">
          <h3 className="text-base font-semibold text-foreground">
            Registros de Asistencia — {MONTH_NAMES[month]} {year}
          </h3>
          <DataTable
            columns={attendanceColumns}
            data={records?.items ?? []}
            loading={recordsLoading}
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            emptyMessage="No hay registros para este período"
          />
        </section>
      )}

      <ConfirmAlertDialog
        summary={
          confirmingProcess && selectedUpload
            ? {
                title: 'Procesar asistencia',
                confirmLabel: 'Procesar asistencia',
                rows: [
                  { label: 'Upload biométrico', value: selectedUpload.filename },
                  { label: 'Período', value: `${MONTH_NAMES[month]} ${year}` },
                  { label: 'Rango de corte', value: `${formatIsoDate(startDate)} — ${formatIsoDate(endDate)}` },
                ],
                warning: extendsBeyondBiometric
                  ? 'El rango excede la cobertura del biométrico: los días sin cobertura generarán ausencias.'
                  : null,
                consequence: 'Se recalculan los registros de asistencia del rango y reemplazan los ya procesados. La planilla del período usará estos datos.',
              }
            : null
        }
        pending={processAttendance.isPending}
        onConfirm={handleProcess}
        onCancel={() => setConfirmingProcess(false)}
      />
    </div>
  )
}
