import { Award, CalendarCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useStudentMe, useStudentMigrationDocuments, useStudentReenrollment } from '@/api/hooks/useStudentPortal'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { pendingLabels, regularizadoBadge } from '@/lib/migrationDocumentsState'
import { formatBs, requestStatus } from '@/lib/reenrollmentState'

export function StudentHomePage() {
  const me = useStudentMe()
  const view = useStudentReenrollment()
  const migration = useStudentMigrationDocuments().data
  const migrationBadge = migration ? regularizadoBadge(migration) : null
  const data = view.data
  const request = data?.request

  return (
    <>
      <section className="bg-brand-soft relative overflow-hidden rounded-2xl border p-5 shadow-xs/5 sm:p-6">
        <span aria-hidden="true" className="bg-brand-line absolute inset-x-0 top-0 h-1" />
        <h1 className="text-2xl font-semibold text-brand">Hola{me.data ? `, ${me.data.first_names}` : ''}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Te damos la bienvenida: tu rematrícula, tu historial y tu horario en un solo lugar.</p>
        {(data?.eligibility.target_semester || me.data?.curriculum_plan) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {data?.eligibility.target_semester && <Badge variant="info">Semestre {data.eligibility.target_semester}</Badge>}
            {data && <Badge variant="success">{data.eligibility.scholarship.label}</Badge>}
            {me.data?.curriculum_plan && <Badge variant="outline">Plan {me.data.curriculum_plan}</Badge>}
          </div>
        )}
      </section>
      {request?.status === 'observada' && (
        <Alert variant="error" role="alert">
          <AlertTitle>Tu solicitud de rematrícula tiene una observación: {request.observation_label}</AlertTitle>
          <AlertDescription>{request.observation_message} Corregila desde Rematrícula o acercate a Registro.</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="overflow-hidden">
          <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-primary" />
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-md shadow-primary/30"><CalendarCheck className="size-4" aria-hidden="true" /></span>
              Rematrícula
            </CardTitle>
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
          <Card className="overflow-hidden">
            <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-success" />
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="flex size-8 items-center justify-center rounded-lg bg-success text-primary-foreground shadow-md shadow-success/30"><Award className="size-4" aria-hidden="true" /></span>
                {data.eligibility.scholarship.label}
              </CardTitle>
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
      {migration?.applies && migrationBadge && (
        <Card>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center gap-2 text-base">Documentos migratorios <Badge variant={migrationBadge.variant}>{migrationBadge.label}</Badge></CardTitle>
            <CardDescription>
              {migration.regularizado ? 'Tenés todos tus documentos migratorios al día.' : 'Te faltan documentos o alguno está vencido.'}
            </CardDescription>
          </CardHeader>
          {!migration.regularizado && (
            <CardContent className="space-y-2 text-sm">
              <ul className="list-disc pl-5">
                {pendingLabels(migration).map((label) => <li key={label}>{label}</li>)}
              </ul>
              <p className="text-muted-foreground">Presentalos en Registro para poder completar tu rematrícula.</p>
            </CardContent>
          )}
        </Card>
      )}
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
