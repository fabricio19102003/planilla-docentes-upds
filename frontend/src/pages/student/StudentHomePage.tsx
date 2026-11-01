import { Link } from 'react-router-dom'

import { useStudentMe, useStudentReenrollment } from '@/api/hooks/useStudentPortal'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { formatBs, requestStatus } from '@/lib/reenrollmentState'

export function StudentHomePage() {
  const me = useStudentMe()
  const view = useStudentReenrollment()
  const data = view.data
  const request = data?.request

  return (
    <>
      <h1 className="text-2xl font-semibold">Hola{me.data ? `, ${me.data.first_names}` : ''}</h1>
      {request?.status === 'observada' && (
        <Alert variant="error" role="alert">
          <AlertTitle>Tu solicitud de rematrícula tiene una observación: {request.observation_label}</AlertTitle>
          <AlertDescription>{request.observation_message} Corregila desde Rematrícula o acercate a Registro.</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rematrícula</CardTitle>
            <CardDescription>
              {data?.window
                ? `${data.window.term_code}: del ${formatDateInBolivia(data.window.starts_on)} al ${formatDateInBolivia(data.window.ends_on)}`
                : 'Todavía no hay una rematrícula programada.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {data?.eligibility.target_semester && <p>Te corresponde cursar el <strong>semestre {data.eligibility.target_semester}</strong>.</p>}
            {request
              ? <p className="flex items-center gap-2">Estado de tu solicitud: <Badge variant={requestStatus(request.status).variant}>{requestStatus(request.status).label}</Badge></p>
              : data?.window?.is_open && <p>Todavía no enviaste tu solicitud.</p>}
            {data?.window?.is_open && <Button render={<Link to="/estudiante/rematricula" />}>{request ? 'Ver o editar mi solicitud' : 'Solicitar rematrícula'}</Button>}
          </CardContent>
        </Card>
        {data && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{data.eligibility.scholarship.label}</CardTitle>
              <CardDescription>
                {data.eligibility.scholarship.average === null
                  ? 'Sin notas finales en tu último período.'
                  : `Promedio de tu último período (${data.eligibility.graded_term}): ${data.eligibility.scholarship.average}`}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <p>Cuota: <strong>{formatBs(data.eligibility.scholarship.cuota)}</strong> × {data.eligibility.scholarship.cuotas} = {formatBs(data.eligibility.scholarship.total)}</p>
              {!data.eligibility.scholarship.never_failed && <p className="text-muted-foreground">Las becas requieren no haber reprobado ninguna materia.</p>}
              <p className="text-xs text-muted-foreground">Montos informativos; el pago se realiza en caja.</p>
            </CardContent>
          </Card>
        )}
      </div>
      {me.data && (
        <Card>
          <CardHeader><CardTitle className="text-base">Mis datos</CardTitle><CardDescription>Si algo está mal, avisá en Registro.</CardDescription></CardHeader>
          <CardContent>
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              {([['Documento', me.data.document_number], ['Plan de estudio', me.data.curriculum_plan], ['Celular', me.data.phone],
                ['Correo académico', me.data.academic_email], ['Correo personal', me.data.personal_email], ['Nacionalidad', me.data.nationality]] as const)
                .map(([label, value]) => (
                  <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd>{value || '—'}</dd></div>
                ))}
            </dl>
          </CardContent>
        </Card>
      )}
    </>
  )
}
