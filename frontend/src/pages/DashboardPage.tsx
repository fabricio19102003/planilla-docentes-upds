import { Link } from 'react-router-dom'
import { Users, BookOpen, Upload, TrendingUp, DollarSign, AlertCircle, ClipboardCheck } from 'lucide-react'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { useDashboard } from '@/api/hooks/useDashboard'
import { StatCard } from '@/components/shared/StatCard'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
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
  const { data, isLoading, error } = useDashboard()

  if (isLoading) return <LoadingPage />

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-600 font-medium">Error al cargar el dashboard</p>
        <p className="text-red-400 text-sm mt-1">Verificá que el servidor esté en línea</p>
      </div>
    )
  }

  const attendanceRate = data?.latest_attendance_summary?.attendance_rate
  const lastUpload = data?.recent_uploads?.[0]
  const totalPayment = data?.total_monthly_payment ?? 0
  const pendingRequests = data?.pending_requests ?? 0

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="gradient-navy rounded-xl p-6 text-white animate-fade-in">
        <h2 className="text-2xl font-bold">Bienvenido al Panel de Administración</h2>
        <p className="text-white/70 mt-1">SIPAD — Sistema Integrado de Pago Docente</p>
      </div>

      {/* Stats Grid — 6 cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <div className="animate-fade-in-up stagger-1">
          <StatCard
            icon={Users}
            title="Total Docentes"
            value={data?.teacher_count ?? 0}
            subtitle="Docentes registrados"
            color="#003366"
          />
        </div>
        <div className="animate-fade-in-up stagger-2">
          <StatCard
            icon={BookOpen}
            title="Designaciones Activas"
            value={data?.designation_count ?? 0}
            subtitle="Materias asignadas"
            color="#0066CC"
          />
        </div>
        <div className="animate-fade-in-up stagger-3">
          <StatCard
            icon={TrendingUp}
            title="Tasa de Asistencia"
            value={
              attendanceRate != null
                ? `${attendanceRate.toFixed(1)}%`
                : 'Sin datos'
            }
            subtitle="Último mes procesado"
            color="#16a34a"
          />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <StatCard
            icon={DollarSign}
            title="Total Facturación"
            value={totalPayment > 0 ? formatCurrency(totalPayment) : 'Sin datos'}
            subtitle="Período actual"
            color="#7c3aed"
          />
        </div>
        <div className="animate-fade-in-up stagger-5">
          <StatCard
            icon={AlertCircle}
            title="Solicitudes Pendientes"
            value={pendingRequests}
            subtitle="Solicitudes por responder"
            color={pendingRequests > 0 ? '#d97706' : '#6b7280'}
          />
        </div>
        <div className="animate-fade-in-up stagger-5">
          <StatCard
            icon={Upload}
            title="Último Upload"
            value={
              lastUpload
                ? `${MONTH_NAMES[lastUpload.month]} ${lastUpload.year}`
                : 'Sin datos'
            }
            subtitle={lastUpload ? `${lastUpload.total_records} registros` : undefined}
            color="#4DA8DA"
          />
        </div>
      </div>

      {/* Charts Row 1: Donut + Horizontal Bar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Donut — Attendance Distribution */}
        <div className="animate-fade-in-up stagger-2">
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Distribución de Asistencia
              </h3>
            </div>
            <div className="p-5">
              {data?.attendance_distribution?.length ? (
                <div className="flex items-center gap-4">
                  <div className="w-1/2">
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
                        >
                          {data.attendance_distribution.map((entry, i) => (
                            <Cell key={i} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value: number) => [value, 'registros']} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="w-1/2 space-y-2">
                    {data.attendance_distribution.map((item) => (
                      <div key={item.name} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                          <span className="text-gray-600">{item.name}</span>
                        </div>
                        <span className="font-semibold text-gray-800">{item.value}</span>
                      </div>
                    ))}
                    <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-sm">
                      <span className="text-gray-500">Total slots</span>
                      <span className="font-bold text-gray-700">
                        {data.attendance_distribution.reduce((acc, i) => acc + i.value, 0)}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 text-sm py-8 text-center">Sin datos de asistencia</p>
              )}
            </div>
          </div>
        </div>

        {/* Horizontal Bar — Top 10 Earners */}
        <div className="animate-fade-in-up stagger-3">
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Top 10 Docentes por Facturación
              </h3>
            </div>
            <div className="p-5">
              {data?.top_earners?.length ? (
                <ResponsiveContainer width="100%" height={Math.max(300, data.top_earners.length * 36)}>
                  <BarChart data={data.top_earners} layout="vertical" margin={{ left: 0, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 9 }}
                      tickFormatter={(v: number) => `Bs ${(v / 1000).toFixed(0)}k`}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={160}
                      tick={{ fontSize: 8 }}
                      interval={0}
                      tickFormatter={(v: string) => {
                        // Show only last name + first initial to keep it short
                        const parts = v.split(' ').filter(Boolean)
                        if (parts.length <= 2) return v
                        return parts[0] + ' ' + parts.slice(1).map(p => p[0] + '.').join('')
                      }}
                    />
                    <Tooltip
                      formatter={(value: number) => [
                        `Bs ${value.toLocaleString('es-BO', { minimumFractionDigits: 2 })}`,
                        'Facturación',
                      ]}
                      labelFormatter={(name: string) => name}
                    />
                    <Bar dataKey="payment" fill="#003366" radius={[0, 4, 4, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-400 text-sm py-8 text-center">Sin datos de facturación</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row 2: Group dist + Semester dist */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Vertical Bar — Designaciones por Grupo */}
        <div className="animate-fade-in-up stagger-4">
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Designaciones por Grupo
              </h3>
            </div>
            <div className="p-5">
              {data?.group_distribution?.length ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={data.group_distribution.slice(0, 10)}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="group" tick={{ fontSize: 9 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#0066CC" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-400 text-sm py-8 text-center">Sin datos de grupos</p>
              )}
            </div>
          </div>
        </div>

        {/* Vertical Bar — Designaciones por Semestre */}
        <div className="animate-fade-in-up stagger-5">
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Designaciones por Semestre
              </h3>
            </div>
            <div className="p-5">
              {data?.semester_distribution?.length ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={data.semester_distribution}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="semester" tick={{ fontSize: 9 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#4DA8DA" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-400 text-sm py-8 text-center">Sin datos de semestres</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Row: Recent Uploads + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Uploads */}
        <div className="lg:col-span-2 animate-fade-in-up stagger-3">
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Últimas Subidas de Datos
              </h3>
            </div>
            <div className="p-5">
              {!data?.recent_uploads?.length ? (
                <p className="text-gray-400 text-sm py-6 text-center">
                  No hay subidas recientes
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100">
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Archivo</th>
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Período</th>
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Fecha</th>
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_uploads.slice(0, 5).map((upload) => (
                        <tr
                          key={upload.id}
                          className="border-b border-gray-50 last:border-0 hover:bg-blue-50/40 transition-colors duration-150"
                        >
                          <td className="py-2.5 px-3 font-medium text-gray-700 max-w-[180px] truncate">
                            {upload.filename}
                          </td>
                          <td className="py-2.5 px-3 text-gray-600">
                            {MONTH_NAMES[upload.month]} {upload.year}
                          </td>
                          <td className="py-2.5 px-3 text-gray-500">
                            {formatDate(upload.upload_date)}
                          </td>
                          <td className="py-2.5 px-3">
                            <Badge
                              className={
                                upload.status === 'PROCESSED'
                                  ? 'bg-green-100 text-green-700 border-green-200'
                                  : 'bg-yellow-100 text-yellow-700 border-yellow-200'
                              }
                            >
                              {upload.status === 'PROCESSED' ? 'Procesado' : upload.status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="animate-fade-in-up stagger-4">
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Acciones Rápidas
              </h3>
            </div>
            <div className="p-5">
              <div className="space-y-3">
                <Link to="/upload" className="block">
                  <Button
                    className="w-full justify-start gap-2 h-11 text-white transition-all duration-200 hover:opacity-90 hover:-translate-y-0.5 shadow-md"
                    style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}
                  >
                    <Upload size={16} />
                    Subir Datos Biométricos
                  </Button>
                </Link>
                <Link to="/planilla" className="block">
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2 h-11 border-[#0066CC] text-[#0066CC] hover:bg-blue-50 transition-all duration-200"
                  >
                    <TrendingUp size={16} />
                    Generar Planilla
                  </Button>
                </Link>
                <Link to="/attendance" className="block">
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2 h-11 transition-all duration-200"
                  >
                    <BookOpen size={16} />
                    Ver Asistencia
                  </Button>
                </Link>
                <Link to="/requests" className="block">
                  <Button
                    variant="outline"
                    className={`w-full justify-start gap-2 h-11 transition-all duration-200 ${
                      pendingRequests > 0
                        ? 'border-amber-400 text-amber-600 hover:bg-amber-50'
                        : ''
                    }`}
                  >
                    <ClipboardCheck size={16} />
                    Solicitudes
                    {pendingRequests > 0 && (
                      <Badge className="ml-auto bg-amber-100 text-amber-700 border-amber-200 text-xs">
                        {pendingRequests}
                      </Badge>
                    )}
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
