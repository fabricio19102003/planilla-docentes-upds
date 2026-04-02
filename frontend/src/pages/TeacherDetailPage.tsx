import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, User } from 'lucide-react'
import { useTeacherDetail } from '@/api/hooks/useTeachers'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { DataTable } from '@/components/shared/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { Designation, ScheduleSlot } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

function formatSchedule(schedule: ScheduleSlot[]): string {
  if (!schedule || schedule.length === 0) return '—'
  return schedule
    .map((slot) => {
      const day = slot.day ?? slot.dia ?? ''
      const start = slot.start_time ?? slot.hora_inicio ?? ''
      const end = slot.end_time ?? slot.hora_fin ?? ''
      const hours = slot.hours_academicas ?? slot.horas_academicas ?? ''
      const parts = [day, start && end ? `${start}-${end}` : '', hours ? `${hours}h` : ''].filter(Boolean)
      return parts.join(' ')
    })
    .filter(Boolean)
    .join('; ')
}

const designationColumns: Column<Designation>[] = [
  {
    key: 'subject',
    header: 'Materia',
    render: (item) => <span className="font-medium">{item.subject}</span>,
  },
  { key: 'semester', header: 'Semestre' },
  { key: 'group_code', header: 'Grupo' },
  {
    key: 'schedule_json',
    header: 'Horario',
    render: (item) => (
      <span className="text-xs text-gray-600">{formatSchedule(item.schedule_json)}</span>
    ),
  },
  {
    key: 'weekly_hours',
    header: 'Hs Semanales',
    render: (item) => {
      const h = item.weekly_hours ?? item.weekly_hours_calculated
      return h != null ? `${h}h` : '—'
    },
  },
  {
    key: 'monthly_hours',
    header: 'Hs Mensuales',
    render: (item) => item.monthly_hours != null ? `${item.monthly_hours}h` : '—',
  },
]

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-800 font-medium">{value ?? '—'}</dd>
    </div>
  )
}

export function TeacherDetailPage() {
  const { ci } = useParams<{ ci: string }>()
  const navigate = useNavigate()
  const { data: teacher, isLoading, error } = useTeacherDetail(ci)

  if (isLoading) return <LoadingPage />

  if (error || !teacher) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-400 font-medium">No se encontró el docente con C.I.: {ci}</p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => navigate('/teachers')}
        >
          <ArrowLeft size={14} className="mr-2" />
          Volver a Docentes
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Button
        variant="outline"
        onClick={() => navigate('/teachers')}
        className="gap-2"
      >
        <ArrowLeft size={14} />
        Volver a Docentes
      </Button>

      {/* Teacher Info Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center text-white flex-shrink-0"
              style={{ backgroundColor: '#003366' }}
            >
              <User size={26} />
            </div>
            <div>
              <CardTitle className="text-xl" style={{ color: '#003366' }}>
                {teacher.full_name}
              </CardTitle>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-gray-500 text-sm">C.I.: {teacher.ci}</span>
                {teacher.external_permanent && (
                  <Badge className="bg-blue-100 text-blue-700">
                    {teacher.external_permanent === 'EXTERNO' ? 'Externo' : 'Permanente'}
                  </Badge>
                )}
                {teacher.gender && (
                  <Badge variant="outline">{teacher.gender}</Badge>
                )}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <InfoRow label="Correo Electrónico" value={teacher.email} />
            <InfoRow label="Teléfono" value={teacher.phone} />
            <InfoRow label="Profesión" value={teacher.profession} />
            <InfoRow label="Especialidad" value={teacher.specialty} />
            <InfoRow label="Nivel Académico" value={teacher.academic_level} />
            <InfoRow label="Banco" value={teacher.bank} />
            <InfoRow label="Nro. de Cuenta" value={teacher.account_number} />
            <InfoRow label="Código SAP" value={teacher.sap_code} />
          </dl>
        </CardContent>
      </Card>

      {/* Attendance Summary */}
      {teacher.attendance_summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base" style={{ color: '#003366' }}>
              Resumen de Asistencia
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-800">
                  {teacher.attendance_summary.total_records}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">Total Registros</p>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-700">
                  {teacher.attendance_summary.attended}
                </p>
                <p className="text-xs text-green-500 mt-0.5">Asistencias</p>
              </div>
              <div className="text-center p-3 bg-yellow-50 rounded-lg">
                <p className="text-2xl font-bold text-yellow-700">
                  {teacher.attendance_summary.late}
                </p>
                <p className="text-xs text-yellow-500 mt-0.5">Tardanzas</p>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-lg">
                <p className="text-2xl font-bold text-red-700">
                  {teacher.attendance_summary.absent}
                </p>
                <p className="text-xs text-red-500 mt-0.5">Ausencias</p>
              </div>
              <div className="text-center p-3 bg-orange-50 rounded-lg">
                <p className="text-2xl font-bold text-orange-700">
                  {teacher.attendance_summary.no_exit}
                </p>
                <p className="text-xs text-orange-500 mt-0.5">Sin Salida</p>
              </div>
            </div>
            {teacher.attendance_summary.total_academic_hours > 0 && (
              <p className="text-sm text-gray-500 mt-3">
                Total horas académicas: <strong>{teacher.attendance_summary.total_academic_hours}h</strong>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Designations */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base" style={{ color: '#003366' }}>
            Designaciones ({teacher.designations.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {teacher.designations.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-8">
              Este docente no tiene designaciones registradas
            </p>
          ) : (
            <DataTable
              columns={designationColumns}
              data={teacher.designations}
              emptyMessage="Sin designaciones"
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
