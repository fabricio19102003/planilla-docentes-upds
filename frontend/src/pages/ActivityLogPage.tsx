import { useState } from 'react'
import {
  Activity,
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
import { StatCard } from '@/components/shared/StatCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

// ------------------------------------------------------------------
// Constants
// ------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  auth: 'Autenticación',
  upload: 'Subidas',
  planilla: 'Planilla',
  billing: 'Facturación',
  reports: 'Reportes',
  users: 'Usuarios',
  requests: 'Solicitudes',
  profile: 'Perfil',
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  auth: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  upload: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  planilla: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  billing: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  reports: { bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
  users: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  requests: { bg: 'bg-pink-50', text: 'text-pink-700', border: 'border-pink-200' },
  profile: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
}

const STATUS_COLORS: Record<string, string> = {
  success: 'bg-green-100 text-green-700 border-green-200',
  error: 'bg-red-100 text-red-700 border-red-200',
  denied: 'bg-orange-100 text-orange-700 border-orange-200',
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

function formatDateTime(isoStr: string): string {
  const d = new Date(isoStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ------------------------------------------------------------------
// Sub-components
// ------------------------------------------------------------------

function CategoryBadge({ category }: { category: string }) {
  const colors = CATEGORY_COLORS[category] ?? { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' }
  const label = CATEGORY_LABELS[category] ?? category
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${colors.bg} ${colors.text} ${colors.border}`}>
      {label}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge className={STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-600 border-gray-200'}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  )
}

function ActivityRow({ entry }: { entry: ActivityLogEntry }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = entry.details && Object.keys(entry.details).length > 0

  return (
    <>
      <tr
        className="border-b border-gray-100 hover:bg-blue-50/30 transition-colors cursor-pointer"
        onClick={() => hasDetails && setExpanded((v) => !v)}
      >
        <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap font-mono">
          {formatDateTime(entry.created_at)}
        </td>
        <td className="px-4 py-3">
          <div className="text-sm font-medium text-gray-800">{entry.user_name ?? '—'}</div>
          {entry.user_ci && (
            <div className="text-xs text-gray-400 font-mono">{entry.user_ci}</div>
          )}
        </td>
        <td className="px-4 py-3">
          {entry.user_role ? (
            <span
              className="text-xs font-semibold px-1.5 py-0.5 rounded"
              style={
                entry.user_role === 'admin'
                  ? { backgroundColor: '#1d4ed8', color: '#bfdbfe' }
                  : { backgroundColor: '#15803d', color: '#bbf7d0' }
              }
            >
              {ROLE_LABELS[entry.user_role] ?? entry.user_role}
            </span>
          ) : (
            <span className="text-gray-400 text-xs">—</span>
          )}
        </td>
        <td className="px-4 py-3">
          <CategoryBadge category={entry.category} />
        </td>
        <td className="px-4 py-3 max-w-xs">
          <p className="text-sm text-gray-700 truncate" title={entry.description}>
            {entry.description}
          </p>
        </td>
        <td className="px-4 py-3">
          <StatusBadge status={entry.status} />
        </td>
        <td className="px-4 py-3 text-xs text-gray-400 font-mono">
          {entry.ip_address ?? '—'}
        </td>
        <td className="px-4 py-3 text-center">
          {hasDetails ? (
            expanded ? <ChevronDown size={14} className="text-gray-400 mx-auto" /> : <ChevronRight size={14} className="text-gray-400 mx-auto" />
          ) : null}
        </td>
      </tr>
      {expanded && hasDetails && (
        <tr className="bg-blue-50/40">
          <td colSpan={8} className="px-6 py-3">
            <div className="text-xs font-semibold text-gray-500 mb-1">Detalles</div>
            <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded p-3 overflow-x-auto max-h-32">
              {JSON.stringify(entry.details, null, 2)}
            </pre>
          </td>
        </tr>
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

  const { data: logsData, isLoading: logsLoading } = useActivityLogs(filters)
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
  const topCategoryLabel = topCategory ? (CATEGORY_LABELS[topCategory.category] ?? topCategory.category) : '—'

  // Filter rows by status client-side (status filter not in backend yet is fine)
  const displayItems = logsData?.items ?? []
  const filteredItems = localStatus
    ? displayItems.filter((r) => r.status === localStatus)
    : displayItems

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Registro de Actividad</h1>
        <p className="text-gray-500 text-sm mt-1">
          Auditoría completa de acciones realizadas en el sistema
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Activity}
          title="Total de Registros"
          value={(stats?.total_logs ?? 0).toLocaleString()}
          subtitle="En toda la historia"
          color="#003366"
        />
        <StatCard
          icon={Clock}
          title="Registros Hoy"
          value={stats?.logs_today ?? 0}
          subtitle={new Date().toLocaleDateString('es-BO')}
          color="#0066CC"
        />
        <StatCard
          icon={BarChart3}
          title="Categoría Más Activa"
          value={topCategoryLabel}
          subtitle={topCategory ? `${topCategory.count} acciones` : ''}
          color="#4DA8DA"
        />
        <StatCard
          icon={LogIn}
          title="Últimos Logins"
          value={stats?.recent_logins?.length ?? 0}
          subtitle="Últimos 10 ingresos"
          color="#16a34a"
        />
      </div>

      {/* Filters + table */}
      <div className="card-3d-static">
        {/* Gradient header */}
        <div
          className="px-6 py-4 rounded-t-xl"
          style={{ background: 'linear-gradient(135deg, #003366 0%, #0066CC 100%)' }}
        >
          <h2 className="text-white font-semibold text-lg flex items-center gap-2">
            <Activity size={20} />
            Historial de Actividad
          </h2>
        </div>

        {/* Filters bar */}
        <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex flex-wrap gap-3 items-end">
            {/* User CI search */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">CI / Usuario</label>
              <input
                type="text"
                placeholder="Buscar por CI..."
                value={localCi}
                onChange={(e) => setLocalCi(e.target.value)}
                className="h-8 px-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 w-36"
              />
            </div>

            {/* Category filter */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Categoría</label>
              <select
                value={localCategory}
                onChange={(e) => setLocalCategory(e.target.value)}
                className="h-8 px-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 bg-white"
              >
                <option value="">Todas</option>
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>

            {/* Status filter */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Estado</label>
              <select
                value={localStatus}
                onChange={(e) => setLocalStatus(e.target.value)}
                className="h-8 px-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 bg-white"
              >
                <option value="">Todos</option>
                <option value="success">Exitoso</option>
                <option value="error">Error</option>
                <option value="denied">Denegado</option>
              </select>
            </div>

            {/* Date range */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Desde</label>
              <input
                type="date"
                value={localStartDate}
                onChange={(e) => setLocalStartDate(e.target.value)}
                className="h-8 px-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Hasta</label>
              <input
                type="date"
                value={localEndDate}
                onChange={(e) => setLocalEndDate(e.target.value)}
                className="h-8 px-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            </div>

            {/* Action buttons */}
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={applyFilters}
                className="h-8 text-white"
                style={{ backgroundColor: '#003366' }}
              >
                <Filter size={14} className="mr-1" />
                Filtrar
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={clearFilters}
                className="h-8"
              >
                <X size={14} className="mr-1" />
                Limpiar
              </Button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          {logsLoading ? (
            <div className="py-16 flex justify-center items-center">
              <div className="w-8 h-8 border-4 border-[#0066CC] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="py-16 text-center text-gray-400">
              <Activity size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">No se encontraron registros de actividad</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 whitespace-nowrap">Fecha / Hora</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Usuario</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Rol</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Categoría</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Descripción</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Estado</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">IP</th>
                  <th className="px-4 py-3 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((entry) => (
                  <ActivityRow key={entry.id} entry={entry} />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {logsData && logsData.total > 0 && (
          <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between">
            <p className="text-xs text-gray-500">
              Mostrando {((filters.page ?? 1) - 1) * (filters.per_page ?? 50) + 1}–
              {Math.min((filters.page ?? 1) * (filters.per_page ?? 50), logsData.total)} de{' '}
              {logsData.total.toLocaleString()} registros
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setFilters((f) => ({ ...f, page: Math.max(1, (f.page ?? 1) - 1) }))}
                disabled={(filters.page ?? 1) <= 1}
                className="h-8"
              >
                Anterior
              </Button>
              <span className="flex items-center px-3 text-xs text-gray-600">
                Pág. {filters.page ?? 1} / {totalPages}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setFilters((f) => ({ ...f, page: Math.min(totalPages, (f.page ?? 1) + 1) }))}
                disabled={(filters.page ?? 1) >= totalPages}
                className="h-8"
              >
                Siguiente
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Most active users section */}
      {stats && stats.most_active_users.length > 0 && (
        <div className="card-3d-static">
          <div
            className="px-6 py-4 rounded-t-xl"
            style={{ background: 'linear-gradient(135deg, #003366 0%, #0066CC 100%)' }}
          >
            <h2 className="text-white font-semibold text-base">Usuarios Más Activos</h2>
          </div>
          <div className="p-6">
            <div className="space-y-3">
              {stats.most_active_users.map((u, idx) => {
                const maxCount = stats.most_active_users[0].count
                const pct = Math.round((u.count / maxCount) * 100)
                return (
                  <div key={u.user_ci} className="flex items-center gap-3">
                    <span className="w-5 text-right text-xs font-bold text-gray-400">{idx + 1}.</span>
                    <div className="flex-1">
                      <div className="flex justify-between items-center mb-0.5">
                        <span className="text-sm font-medium text-gray-800">{u.user_name}</span>
                        <span className="text-xs text-gray-500 font-semibold">{u.count} acciones</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #003366, #0066CC)' }}
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
