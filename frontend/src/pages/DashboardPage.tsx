import { Link } from 'react-router-dom'
import { Users, BookOpen, Upload, TrendingUp } from 'lucide-react'
import { useDashboard } from '@/api/hooks/useDashboard'
import { StatCard } from '@/components/shared/StatCard'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          icon={Users}
          title="Total Docentes"
          value={data?.teacher_count ?? 0}
          subtitle="Docentes registrados"
          color="#003366"
        />
        <StatCard
          icon={BookOpen}
          title="Designaciones Activas"
          value={data?.designation_count ?? 0}
          subtitle="Materias asignadas"
          color="#0066CC"
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
          color="#4DA8DA"
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
          color="#16a34a"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Uploads */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
                Últimas Subidas de Datos
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!data?.recent_uploads?.length ? (
                <p className="text-gray-400 text-sm py-6 text-center">
                  No hay subidas recientes
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Archivo</th>
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Período</th>
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Fecha</th>
                        <th className="text-left py-2 px-3 text-gray-500 font-medium text-xs uppercase">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_uploads.slice(0, 5).map((upload) => (
                        <tr key={upload.id} className="border-b last:border-0 hover:bg-gray-50">
                          <td className="py-2 px-3 font-medium text-gray-700 max-w-[180px] truncate">
                            {upload.filename}
                          </td>
                          <td className="py-2 px-3 text-gray-600">
                            {MONTH_NAMES[upload.month]} {upload.year}
                          </td>
                          <td className="py-2 px-3 text-gray-500">
                            {formatDate(upload.upload_date)}
                          </td>
                          <td className="py-2 px-3">
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
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
                Acciones Rápidas
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <Link to="/upload" className="block">
                  <Button
                    className="w-full justify-start gap-2 h-11"
                    style={{ backgroundColor: '#003366' }}
                  >
                    <Upload size={16} />
                    Subir Datos Biométricos
                  </Button>
                </Link>
                <Link to="/planilla" className="block">
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2 h-11 border-[#0066CC] text-[#0066CC] hover:bg-blue-50"
                  >
                    <TrendingUp size={16} />
                    Generar Planilla
                  </Button>
                </Link>
                <Link to="/attendance" className="block">
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2 h-11"
                  >
                    <BookOpen size={16} />
                    Ver Asistencia
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
