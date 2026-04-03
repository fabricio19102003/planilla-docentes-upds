import { Link } from 'react-router-dom'
import { Users, BookOpen, Upload, TrendingUp } from 'lucide-react'
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

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="gradient-navy rounded-xl p-6 text-white animate-fade-in">
        <h2 className="text-2xl font-bold">Bienvenido al Panel de Administración</h2>
        <p className="text-white/70 mt-1">UPDS — Sistema de Planilla Docentes</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
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
        <div className="animate-fade-in-up stagger-4">
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
      </div>

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
                        <tr key={upload.id} className="border-b border-gray-50 last:border-0 hover:bg-blue-50/40 transition-colors duration-150">
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
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
