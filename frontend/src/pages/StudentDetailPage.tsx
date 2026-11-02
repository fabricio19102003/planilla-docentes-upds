import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

import { useStudent } from '@/api/hooks/useAcademicRecords'
import { PortalAccountCard } from '@/components/students/PortalAccountCard'
import { StudentHistory } from '@/components/students/StudentHistory'
import { PageHeader } from '@/components/shared/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { StudentDetail } from '@/lib/academicRecordsState'
import { apiErrorMessage } from '@/lib/userCredentials'

function formatBirthDate(value: string | null) {
  if (!value) return '—'
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

function PersonalData({ student }: { student: StudentDetail['student'] }) {
  const fields: [string, string | null][] = [
    ['Documento', `${student.document_number} (${student.document_type})`],
    ['Fecha de nacimiento', formatBirthDate(student.birth_date)],
    ['Género', student.gender],
    ['Nacionalidad', student.nationality],
    ['País de nacimiento', student.birth_country],
    ['Celular', student.phone],
    ['Correo personal', student.personal_email],
    ['Correo académico', student.academic_email],
    ['Colegio', student.school],
    ['Domicilio', student.address],
    ['Plan de estudio', student.curriculum_plan],
    ['Estado de inscripción', student.legacy_enrollment_status],
  ]
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Datos personales</CardTitle></CardHeader>
      <CardContent>
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {fields.map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="break-words text-foreground">{value || '—'}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

export function StudentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const detail = useStudent(Number(id))
  const back = <Button variant="outline" render={<Link to="/students" />}><ArrowLeft aria-hidden="true" />Volver a estudiantes</Button>

  if (detail.isError) {
    return (
      <div className="space-y-5">
        <PageHeader title="Estudiante" actions={back} />
        <Alert variant="error" role="alert">
          <AlertTitle>{apiErrorMessage(detail.error, 'No se pudo cargar el estudiante.')}</AlertTitle>
          <AlertDescription><Button size="sm" variant="outline" onClick={() => void detail.refetch()}>Reintentar</Button></AlertDescription>
        </Alert>
      </div>
    )
  }
  if (!detail.data) {
    return <p role="status" className="text-sm text-muted-foreground">Cargando estudiante…</p>
  }

  const { student, history } = detail.data
  return (
    <div className="space-y-5">
      <PageHeader
        title={student.full_name}
        description={(
          <span className="flex flex-wrap items-center gap-2">
            {student.document_number}
            {student.is_foreign && <Badge variant="warning">Extranjero</Badge>}
          </span>
        )}
        actions={back}
      />

      <PersonalData student={student} />
      <PortalAccountCard studentId={student.id} account={detail.data.account ?? null} />

      <StudentHistory history={history} />
    </div>
  )
}
