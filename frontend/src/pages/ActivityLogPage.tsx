import { useState } from 'react'
import {
  Activity,
  AlertCircle,
  Clock,
  BarChart3,
  LogIn,
  ChevronDown,
  ChevronRight,
  X,
  Filter,
} from 'lucide-react'
import {
  useActivityLogs,
  useActivityStats,
  type ActivityLogEntry,
  type ActivityLogFilters,
} from '@/api/hooks/useActivityLog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import type { Tone } from '@/components/shared/tones'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardPanel, CardTitle } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Progress, ProgressIndicator, ProgressTrack } from '@/components/ui/progress'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ACTIVITY_CATEGORY_LABELS, resolveActivityCategoryLabel } from '@/lib/displayFormat'

// ------------------------------------------------------------------
// Constants
// ------------------------------------------------------------------

const CATEGORY_TONES: Record<string, Tone> = {
  auth: 'info',
  upload: 'primary',
  planilla: 'primary',
  billing: 'success',
  reports: 'info',
  users: 'warning',
  requests: 'neutral',
  profile: 'neutral',
}

const STATUS_TONES: Record<string, Tone> = {
  success: 'success',
  error: 'destructive',
  denied: 'warning',
}

const STATUS_LABELS: Record<string, string> = {
  success: 'Exitoso',
  error: 'Error',
  denied: 'Denegado',
}

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  docente: 'Docente',
}

const ALL = 'all'

const CATEGORY_ITEMS = [
  { value: ALL, label: 'Todas' },
  ...Object.entries(ACTIVITY_CATEGORY_LABELS).map(([value, label]) => ({ value, label })),
]

const STATUS_ITEMS = [
  { value: ALL, label: 'Todos' },
  { value: 'success', label: 'Exitoso' },
  { value: 'error', label: 'Error' },
  { value: 'denied', label: 'Denegado' },
]

const TABLE_HEADERS = ['Fecha / Hora', 'Usuario', 'Rol', 'Categoría', 'Descripción', 'Estado', 'IP']

function formatDateTime(isoStr: string): string {
  const d = new Date(isoStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ------------------------------------------------------------------
// Sub-components
// ------------------------------------------------------------------

function CategoryBadge({ category }: { category: string }) {
  return <StatusBadge tone={CATEGORY_TONES[category] ?? 'neutral'}>{resolveActivityCategoryLabel(category)}</StatusBadge>
}

function EntryStatusBadge({ status }: { status: string }) {
  return <StatusBadge tone={STATUS_TONES[status] ?? 'neutral'}>{STATUS_LABELS[status] ?? status}</StatusBadge>
}

function ActivityRow({ entry }: { entry: ActivityLogEntry }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = entry.details && Object.keys(entry.details).length > 0
  const toggle = () => {
    if (hasDetails) setExpanded((v) => !v)
  }

  return (
    <>
      <TableRow
        className={hasDetails ? 'cursor-pointer' : undefined}
        onClick={toggle}
        onKeyDown={(e) => {
          if (hasDetails && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            toggle()
          }
        }}
        tabIndex={hasDetails ? 0 : undefined}
        aria-expanded={hasDetails ? expanded : undefined}
      >
        <TableCell className="px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
          {formatDateTime(entry.created_at)}
        </TableCell>
        <TableCell className="px-4 py-3">
          <div className="text-sm font-medium text-foreground">{entry.user_name ?? '—'}</div>
          {entry.user_ci && <div className="font-mono text-xs text-muted-foreground">{entry.user_ci}</div>}
        </TableCell>
        <TableCell className="px-4 py-3">
          {entry.user_role ? (
            <StatusBadge tone={entry.user_role === 'admin' ? 'info' : 'success'}>
              {ROLE_LABELS[entry.user_role] ?? entry.user_role}
            </StatusBadge>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </TableCell>
        <TableCell className="px-4 py-3">
          <CategoryBadge category={entry.category} />
        </TableCell>
        <TableCell className="max-w-xs px-4 py-3">
          <p className="truncate text-sm text-foreground" title={entry.description}>
            {entry.description}
          </p>
        </TableCell>
        <TableCell className="px-4 py-3">
          <EntryStatusBadge status={entry.status} />
        </TableCell>
        <TableCell className="px-4 py-3 font-mono text-xs text-muted-foreground">{entry.ip_address ?? '—'}</TableCell>
        <TableCell className="w-8 px-4 py-3 text-center">
          {hasDetails ? (
            expanded ? (
              <ChevronDown size={14} className="mx-auto text-muted-foreground" aria-hidden="true" />
            ) : (
              <ChevronRight size={14} className="mx-auto text-muted-foreground" aria-hidden="true" />
            )
          ) : null}
        </TableCell>
      </TableRow>
      {expanded && hasDetails && (
        <TableRow className="bg-muted/40 hover:bg-muted/40">
          <TableCell colSpan={8} className="px-6 py-3">
            <div className="mb-1 text-xs font-semibold text-muted-foreground">Detalles</div>
            <pre className="max-h-32 overflow-x-auto rounded-md border bg-background p-3 text-xs text-foreground">
              {JSON.stringify(entry.details, null, 2)}
            </pre>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

// ------------------------------------------------------------------
// Main page
// ------------------------------------------------------------------

export function ActivityLogPage() {
  const [filters, setFilters] = useState<ActivityLogFilters>({
    page: 1,
    per_page: 50,
  })
  const [localCi, setLocalCi] = useState('')
  const [localCategory, setLocalCategory] = useState('')
  const [localStatus, setLocalStatus] = useState('')
  const [localStartDate, setLocalStartDate] = useState('')
  const [localEndDate, setLocalEndDate] = useState('')

  const { data: logsData, isLoading: logsLoading, error: logsError, refetch } = useActivityLogs(filters)
  const { data: stats } = useActivityStats()

  const totalPages = logsData ? Math.ceil(logsData.total / (filters.per_page ?? 50)) : 1

  function applyFilters() {
    setFilters((prev) => ({
      ...prev,
      page: 1,
      user_ci: localCi || undefined,
      category: localCategory || undefined,
      status: undefined, // status filter applied client side for now
      start_date: localStartDate || undefined,
      end_date: localEndDate || undefined,
    }))
  }

  function clearFilters() {
    setLocalCi('')
    setLocalCategory('')
    setLocalStatus('')
    setLocalStartDate('')
    setLocalEndDate('')
    setFilters({ page: 1, per_page: 50 })
  }

  // Find most active category
  const topCategory = stats?.actions_by_category?.[0]
  const topCategoryLabel = topCategory ? resolveActivityCategoryLabel(topCategory.category) : '—'

  // Filter rows by status client-side (status filter not in backend yet is fine)
  const displayItems = logsData?.items ?? []
  const filteredItems = localStatus
    ? displayItems.filter((r) => r.status === localStatus)
    : displayItems

  return (
    <div className="space-y-6">
      <PageHeader
        title="Registro de Actividad"
        description="Auditoría completa de acciones realizadas en el sistema"
      />

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Activity}
          title="Total de Registros"
          value={(stats?.total_logs ?? 0).toLocaleString()}
          subtitle="En toda la historia"
          tone="primary"
        />
        <StatCard
          icon={Clock}
          title="Registros Hoy"
          value={stats?.logs_today ?? 0}
          subtitle={new Date().toLocaleDateString('es-BO')}
          tone="info"
        />
        <StatCard
          icon={BarChart3}
          title="Categoría Más Activa"
          value={topCategoryLabel}
          subtitle={topCategory ? `${topCategory.count} acciones` : ''}
          tone="warning"
        />
        <StatCard
          icon={LogIn}
          title="Últimos Logins"
          value={stats?.recent_logins?.length ?? 0}
          subtitle="Últimos 10 ingresos"
          tone="success"
        />
      </div>

      {/* Filters bar */}
      <Card className="p-5">
        <div className="flex flex-wrap items-end gap-3">
          {/* User CI search */}
          <Field className="w-40">
            <FieldLabel htmlFor="activity-ci">CI / Usuario</FieldLabel>
            <Input
              id="activity-ci"
              type="text"
              placeholder="Buscar por CI..."
              value={localCi}
              onChange={(e) => setLocalCi(e.target.value)}
            />
          </Field>

          {/* Category filter */}
          <Field className="w-44">
            <FieldLabel htmlFor="activity-category">Categoría</FieldLabel>
            <Select
              value={localCategory || ALL}
              items={CATEGORY_ITEMS}
              onValueChange={(value) => setLocalCategory(!value || value === ALL ? '' : value)}
            >
              <SelectTrigger id="activity-category">
                <SelectValue />
              </SelectTrigger>
              <SelectPopup>
                {CATEGORY_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                ))}
              </SelectPopup>
            </Select>
          </Field>

          {/* Status filter */}
          <Field className="w-40">
            <FieldLabel htmlFor="activity-status">Estado</FieldLabel>
            <Select
              value={localStatus || ALL}
              items={STATUS_ITEMS}
              onValueChange={(value) => setLocalStatus(!value || value === ALL ? '' : value)}
            >
              <SelectTrigger id="activity-status">
                <SelectValue />
              </SelectTrigger>
              <SelectPopup>
                {STATUS_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                ))}
              </SelectPopup>
            </Select>
          </Field>

          {/* Date range */}
          <Field className="w-40">
            <FieldLabel htmlFor="activity-start">Desde</FieldLabel>
            <Input
              id="activity-start"
              type="date"
              value={localStartDate}
              onChange={(e) => setLocalStartDate(e.target.value)}
            />
          </Field>
          <Field className="w-40">
            <FieldLabel htmlFor="activity-end">Hasta</FieldLabel>
            <Input
              id="activity-end"
              type="date"
              value={localEndDate}
              onChange={(e) => setLocalEndDate(e.target.value)}
            />
          </Field>

          {/* Action buttons */}
          <div className="flex gap-2">
            <Button onClick={applyFilters}>
              <Filter aria-hidden="true" />
              Filtrar
            </Button>
            <Button variant="outline" onClick={clearFilters}>
              <X aria-hidden="true" />
              Limpiar
            </Button>
          </div>
        </div>
      </Card>

      {logsError && (
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>No se pudo cargar el registro de actividad</AlertTitle>
          <AlertDescription>Revisá tu conexión e intentá nuevamente.</AlertDescription>
          <AlertAction>
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              Reintentar
            </Button>
          </AlertAction>
        </Alert>
      )}

      {/* Table */}
      <TableCard
        title={
          <span className="flex items-center gap-2">
            <Activity size={18} aria-hidden="true" />
            Historial de Actividad
          </span>
        }
        footer={
          logsData && logsData.total > 0 ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground tabular-nums">
                Mostrando {((filters.page ?? 1) - 1) * (filters.per_page ?? 50) + 1}–
                {Math.min((filters.page ?? 1) * (filters.per_page ?? 50), logsData.total)} de{' '}
                {logsData.total.toLocaleString()} registros
              </p>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setFilters((f) => ({ ...f, page: Math.max(1, (f.page ?? 1) - 1) }))}
                  disabled={(filters.page ?? 1) <= 1}
                >
                  Anterior
                </Button>
                <span className="px-3 text-xs text-muted-foreground tabular-nums">
                  Pág. {filters.page ?? 1} / {totalPages}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setFilters((f) => ({ ...f, page: Math.min(totalPages, (f.page ?? 1) + 1) }))}
                  disabled={(filters.page ?? 1) >= totalPages}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          ) : undefined
        }
      >
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            {TABLE_HEADERS.map((h) => (
              <TableHead key={h} className="h-10 px-4 text-xs font-medium uppercase tracking-wider">
                {h}
              </TableHead>
            ))}
            <TableHead className="w-8 px-4" aria-label="Detalles" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {logsLoading ? (
            Array.from({ length: 6 }, (_, rowIndex) => (
              <TableRow key={rowIndex}>
                {Array.from({ length: TABLE_HEADERS.length + 1 }, (_, cellIndex) => (
                  <TableCell key={cellIndex} className="px-4 py-3">
                    <Skeleton className="h-4 w-full max-w-28" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : filteredItems.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={TABLE_HEADERS.length + 1} className="p-0 whitespace-normal">
                <EmptyState icon={Activity} title="No se encontraron registros de actividad" />
              </TableCell>
            </TableRow>
          ) : (
            filteredItems.map((entry) => <ActivityRow key={entry.id} entry={entry} />)
          )}
        </TableBody>
      </TableCard>

      {/* Most active users section */}
      {stats && stats.most_active_users.length > 0 && (
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-base">Usuarios Más Activos</CardTitle>
          </CardHeader>
          <CardPanel>
            <div className="space-y-3">
              {stats.most_active_users.map((u, idx) => {
                const maxCount = stats.most_active_users[0].count
                const pct = Math.round((u.count / maxCount) * 100)
                return (
                  <div key={u.user_ci} className="flex items-center gap-3">
                    <span className="w-5 text-right text-xs font-bold text-muted-foreground tabular-nums">{idx + 1}.</span>
                    <div className="flex-1">
                      <div className="mb-1 flex items-center justify-between">
                        <span className="text-sm font-medium text-foreground">{u.user_name}</span>
                        <span className="text-xs font-semibold text-muted-foreground tabular-nums">{u.count} acciones</span>
                      </div>
                      <Progress value={pct} aria-label={`Actividad de ${u.user_name}`}>
                        <ProgressTrack>
                          <ProgressIndicator />
                        </ProgressTrack>
                      </Progress>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardPanel>
        </Card>
      )}
    </div>
  )
}
