import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Users, BookOpen, Upload, TrendingUp, DollarSign, AlertCircle, AlertTriangle, ClipboardCheck } from 'lucide-react'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { useDashboard } from '@/api/hooks/useDashboard'
import { useAppSettings } from '@/api/hooks/useAppSettings'
import { usePlanillaStatus } from '@/api/hooks/usePlanilla'
import { usePublicationStatus } from '@/api/hooks/useBillingPublication'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import { TONE_DOT, type Tone } from '@/components/shared/tones'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { formatPaymentBreakdown } from '@/lib/displayFormat'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

// Charts read the theme tokens through CSS variables, so they follow the light/dark theme.
const CHART_TOOLTIP_PROPS = {
  contentStyle: {
    borderRadius: 12,
    border: '1px solid var(--border)',
    background: 'var(--popover)',
    boxShadow: '0 8px 30px rgb(0 0 0 / 0.08)',
  },
  labelStyle: { color: 'var(--foreground)', fontWeight: 600 },
  itemStyle: { color: 'var(--muted-foreground)', fontWeight: 500 },
}

const AXIS_TICK = { fontSize: 11, fill: 'var(--muted-foreground)' }

// The API sends a raw color per slice; the page maps each slice name to a theme tone instead.
const DISTRIBUTION_TONE: Record<string, Tone> = {
  Asistidos: 'success',
  Tardanzas: 'warning',
  Ausencias: 'destructive',
  'Sin salida': 'neutral',
}

const TONE_FILL: Record<Tone, string> = {
  primary: 'var(--color-primary)',
  success: 'var(--color-success)',
  warning: 'var(--color-warning)',
  destructive: 'var(--color-destructive)',
  info: 'var(--color-info)',
  neutral: 'var(--color-muted-foreground)',
}

function distributionTone(name: string): Tone {
  return DISTRIBUTION_TONE[name] ?? 'neutral'
}

function ChartCard({ title, className, children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <Card className={className}>
      <CardHeader className="border-b pb-4">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col justify-center">{children}</CardContent>
    </Card>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Cargando el dashboard">
      <div className="space-y-2">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
    </div>
  )
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const year = d.getFullYear()
  return `${day}/${month}/${year}`
}

function formatCurrency(value: number): string {
  return `Bs ${value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function DashboardPage() {
  const now = new Date()
  const currentMonth = now.getMonth() + 1
  const currentYear = now.getFullYear()
  const { data, isLoading, error, refetch, isFetching } = useDashboard()
  const { data: settings } = useAppSettings()
  const billingMonth = data?.billing_period_month ?? currentMonth
  const billingYear = data?.billing_period_year ?? currentYear
  const hasBillingPeriod = data?.billing_period_month != null && data?.billing_period_year != null
  const { data: planillaStatus } = usePlanillaStatus(billingMonth, billingYear, hasBillingPeriod)
  const { data: publicationStatus } = usePublicationStatus(billingMonth, billingYear, hasBillingPeriod)

  if (isLoading) return <DashboardSkeleton />

  if (error) {
    return (
      <Alert variant="error">
        <AlertTriangle />
        <AlertTitle>Error al cargar el dashboard</AlertTitle>
        <AlertDescription>Verificá que el servidor esté en línea</AlertDescription>
        <AlertAction>
          <Button variant="outline" size="sm" onClick={() => refetch()} loading={isFetching}>
            Reintentar
          </Button>
        </AlertAction>
      </Alert>
    )
  }

  const attendanceRate = data?.latest_attendance_summary?.attendance_rate
  const lastUpload = data?.recent_uploads?.[0]
  const totalPayment = data?.total_monthly_payment ?? 0
  const pendingRequests = data?.pending_requests ?? 0
  const paymentBreakdown = totalPayment > 0 && data?.total_regular_payment != null && data?.total_practice_payment != null
    ? formatPaymentBreakdown(data.total_regular_payment, data.total_practice_payment)
    : null
  const isPublished = publicationStatus?.status === 'published'
  const planillaStatusText = !planillaStatus
    ? 'Sin generar'
    : isPublished
      ? 'Publicada ✓'
      : planillaStatus.status === 'approved'
        ? 'Aprobada (sin publicar)'
        : planillaStatus.status === 'rejected'
          ? 'Rechazada'
        : 'Pend. Aprobación'
  const planillaActionText = !planillaStatus
    ? 'Generar Planilla'
    : isPublished
      ? 'Ver Facturación'
      : planillaStatus.status === 'approved'
        ? 'Publicar Facturación'
        : planillaStatus.status === 'rejected'
          ? 'Regenerar Planilla'
        : 'Aprobar Planilla'
  const planillaRejected = planillaStatus?.status === 'rejected'
  const planillaTone: Tone = isPublished
    ? 'success'
    : planillaRejected
      ? 'destructive'
      : planillaStatus
        ? 'warning'
        : 'neutral'
  const activePeriod = settings?.active_academic_period || `Gestión ${currentYear}`
  const billingPeriodLabel = hasBillingPeriod ? `${MONTH_NAMES[billingMonth]} ${billingYear}` : 'Sin datos'
  const attendanceTotal = data?.attendance_distribution?.reduce((acc, i) => acc + i.value, 0) ?? 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Panel de Administración — SIPAD"
        description={activePeriod}
        actions={
          <div className="rounded-xl border bg-card px-4 py-2 sm:text-right">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Período facturación</p>
            <p className="text-base font-semibold tabular-nums text-foreground">{billingPeriodLabel}</p>
          </div>
        }
      />

      {/* Stats Grid */}
      {/* StatCard truncates its text; long values (planilla state, amounts) wrap here instead. */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 [&_p]:whitespace-normal">
        <StatCard
          icon={Users}
          title="Total Docentes"
          value={data?.teacher_count ?? 0}
          subtitle="Docentes registrados"
          tone="primary"
        />
        <StatCard
          icon={BookOpen}
          title="Designaciones Activas"
          value={data?.designation_count ?? 0}
          subtitle="Materias asignadas"
          tone="info"
        />
        <StatCard
          icon={TrendingUp}
          title="Tasa de Asistencia"
          value={
            attendanceRate != null
              ? `${attendanceRate.toFixed(1)}%`
              : 'Sin datos'
          }
          subtitle="Último mes procesado"
          tone="success"
        />
        <StatCard
          icon={DollarSign}
          title="Total a pagar (teoría + asistencial)"
          value={totalPayment > 0 ? formatCurrency(totalPayment) : 'Sin datos'}
          hint={
            paymentBreakdown ? (
              <>
                {paymentBreakdown}
                <span className="block">{billingPeriodLabel}</span>
              </>
            ) : (
              billingPeriodLabel
            )
          }
          tone="primary"
        />
        <StatCard
          icon={ClipboardCheck}
          title="Estado Planilla"
          value={planillaStatusText}
          subtitle={billingPeriodLabel}
          tone={planillaTone}
        />
        <StatCard
          icon={AlertCircle}
          title="Solicitudes Pendientes"
          value={pendingRequests}
          subtitle="Solicitudes por responder"
          tone={pendingRequests > 0 ? 'warning' : 'neutral'}
        />
        <StatCard
          icon={Upload}
          title="Último Upload"
          value={
            lastUpload
              ? `${MONTH_NAMES[lastUpload.month]} ${lastUpload.year}`
              : 'Sin datos'
          }
          subtitle={lastUpload ? `${lastUpload.total_records} registros` : undefined}
          tone="info"
        />
      </div>

      {/* Charts Row 1: Donut + Horizontal Bar */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartCard title="Distribución de Asistencia">
          {data?.attendance_distribution?.length ? (
            <div className="flex flex-col items-center gap-4 sm:flex-row">
              <div className="w-full sm:w-1/2">
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={data.attendance_distribution}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                      stroke="var(--card)"
                    >
                      {data.attendance_distribution.map((entry) => (
                        <Cell key={entry.name} fill={TONE_FILL[distributionTone(entry.name)]} />
                      ))}
                    </Pie>
                    <Tooltip {...CHART_TOOLTIP_PROPS} formatter={(value) => [Number(value), 'registros']} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="w-full space-y-2 sm:w-1/2">
                {data.attendance_distribution.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span aria-hidden="true" className={cn('size-2.5 rounded-full', TONE_DOT[distributionTone(item.name)])} />
                      <span className="text-muted-foreground">{item.name}</span>
                    </div>
                    <span className="font-semibold tabular-nums text-foreground">{item.value}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between border-t pt-2 text-sm">
                  <span className="text-muted-foreground">Total slots</span>
                  <span className="font-semibold tabular-nums text-foreground">{attendanceTotal}</span>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState className="py-8 md:py-8" title="Sin datos de asistencia" />
          )}
        </ChartCard>

        <ChartCard title="Top 10 Docentes por Facturación">
          {data?.top_earners?.length ? (
            <ResponsiveContainer width="100%" height={Math.max(300, data.top_earners.length * 36)}>
              <BarChart data={data.top_earners} layout="vertical" margin={{ left: 0, right: 20, top: 5, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
                <XAxis
                  type="number"
                  tick={AXIS_TICK}
                  tickFormatter={(v: number) => `Bs ${(v / 1000).toFixed(0)}k`}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={150}
                  tick={AXIS_TICK}
                  interval={0}
                  tickFormatter={(v: string) => {
                    // Show only last name + first initial to keep it short
                    const parts = v.split(' ').filter(Boolean)
                    if (parts.length <= 2) return v
                    return parts[0] + ' ' + parts.slice(1).map(p => p[0] + '.').join('')
                  }}
                />
                <Tooltip
                  {...CHART_TOOLTIP_PROPS}
                  cursor={{ fill: 'var(--muted)' }}
                  formatter={(value) => [
                    `Bs ${Number(value).toLocaleString('es-BO', { minimumFractionDigits: 2 })}`,
                    'Facturación',
                  ]}
                />
                <Bar dataKey="payment" fill="var(--color-chart-1)" radius={[0, 4, 4, 0]} barSize={20} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState className="py-8 md:py-8" title="Sin datos de facturación" />
          )}
        </ChartCard>
      </div>

      {/* Charts Row 2: Group dist + Semester dist */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartCard title="Designaciones por Grupo">
          {data?.group_distribution?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.group_distribution.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="group" tick={AXIS_TICK} />
                <YAxis tick={AXIS_TICK} />
                <Tooltip {...CHART_TOOLTIP_PROPS} cursor={{ fill: 'var(--muted)' }} />
                <Bar dataKey="count" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState className="py-8 md:py-8" title="Sin datos de grupos" />
          )}
        </ChartCard>

        <ChartCard title="Designaciones por Semestre">
          {data?.semester_distribution?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.semester_distribution}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="semester" tick={AXIS_TICK} />
                <YAxis tick={AXIS_TICK} />
                <Tooltip {...CHART_TOOLTIP_PROPS} cursor={{ fill: 'var(--muted)' }} />
                <Bar dataKey="count" fill="var(--color-chart-2)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState className="py-8 md:py-8" title="Sin datos de semestres" />
          )}
        </ChartCard>
      </div>

      {/* Bottom Row: Recent Uploads + Quick Actions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {!data?.recent_uploads?.length ? (
            <ChartCard title="Últimas Subidas de Datos">
              <EmptyState className="py-6 md:py-6" icon={Upload} title="No hay subidas recientes" />
            </ChartCard>
          ) : (
            <TableCard title="Últimas Subidas de Datos">
              <TableHeader>
                <TableRow>
                  <TableHead>Archivo</TableHead>
                  <TableHead>Período</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_uploads.slice(0, 5).map((upload) => (
                  <TableRow key={upload.id}>
                    <TableCell className="max-w-[180px] truncate font-medium">{upload.filename}</TableCell>
                    <TableCell>
                      {MONTH_NAMES[upload.month]} {upload.year}
                    </TableCell>
                    <TableCell className="tabular-nums text-muted-foreground">{formatDate(upload.upload_date)}</TableCell>
                    <TableCell>
                      <StatusBadge tone={upload.status === 'PROCESSED' ? 'success' : 'warning'}>
                        {upload.status === 'PROCESSED' ? 'Procesado' : upload.status}
                      </StatusBadge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </TableCard>
          )}
        </div>

        <ChartCard title="Acciones Rápidas">
          <div className="flex flex-col gap-3">
            <Button size="lg" className="w-full justify-start" render={<Link to="/upload" />}>
              <Upload />
              Subir Datos Biométricos
            </Button>
            <Button
              size="lg"
              variant={planillaRejected ? 'destructive-outline' : 'outline'}
              className="w-full justify-start"
              render={<Link to="/planilla" />}
            >
              <TrendingUp />
              {planillaActionText}
            </Button>
            <Button size="lg" variant="outline" className="w-full justify-start" render={<Link to="/attendance" />}>
              <BookOpen />
              Ver Asistencia
            </Button>
            <Button size="lg" variant="outline" className="w-full justify-start" render={<Link to="/requests" />}>
              <ClipboardCheck />
              Solicitudes
              {pendingRequests > 0 && (
                <StatusBadge tone="warning" className="ml-auto tabular-nums">
                  {pendingRequests}
                </StatusBadge>
              )}
            </Button>
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
