import { BookOpen } from 'lucide-react'

import { useCurricula, useCurriculum, useLoadDefaultCurriculum } from '@/api/hooks/useAcademicRecords'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { apiErrorMessage } from '@/lib/userCredentials'

export function CurriculumPage() {
  const plans = useCurricula()
  const planId = plans.data?.[0]?.id
  const plan = useCurriculum(planId)
  const load = useLoadDefaultCurriculum()

  const loadButton = (
    <Button onClick={() => load.mutate()} disabled={load.isPending}>
      {load.isPending ? 'Cargando…' : 'Cargar malla Medicina 510-01'}
    </Button>
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title="Malla curricular"
        description={plan.data ? `${plan.data.name} · ${plan.data.total_semesters} semestres` : 'Materias de cada semestre con su carga horaria y créditos.'}
      />

      {(plans.isError || plan.isError) && (
        <Alert variant="error" role="alert">
          <AlertTitle>No se pudo cargar la malla curricular.</AlertTitle>
          <AlertDescription><Button size="sm" variant="outline" onClick={() => void plans.refetch()}>Reintentar</Button></AlertDescription>
        </Alert>
      )}
      {load.isError && (
        <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(load.error, 'No se pudo cargar la malla.')}</AlertTitle></Alert>
      )}

      {plans.isLoading && <p role="status" className="text-sm text-muted-foreground">Cargando malla curricular…</p>}

      {plans.data && plans.data.length === 0 && (
        <EmptyState
          icon={BookOpen}
          title="Todavía no hay una malla cargada"
          description="Cargá la malla de Medicina 510-01. También se carga sola la primera vez que importás el historial académico."
          action={loadButton}
        />
      )}

      {plan.data && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {plan.data.semesters.map((semester) => {
            const credits = semester.subjects.reduce((sum, subject) => sum + subject.credits, 0)
            const hours = semester.subjects.reduce((sum, subject) => sum + subject.theory_hours + subject.practice_hours, 0)
            return (
              <Card key={semester.semester}>
                <CardHeader>
                  <CardTitle className="text-base">Semestre {semester.semester}</CardTitle>
                  <CardDescription>{semester.subjects.length} materias · {hours} horas · {credits} créditos</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="divide-y text-sm">
                    {semester.subjects.map((subject) => (
                      <li key={subject.id} className="flex items-start justify-between gap-3 py-2">
                        <div className="min-w-0">
                          <p className="font-medium text-foreground">{subject.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {subject.is_elective ? <Badge variant="info" size="sm">Electiva</Badge> : subject.code}
                          </p>
                        </div>
                        <p className="shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                          HT {subject.theory_hours} · HP {subject.practice_hours}<br />{subject.credits} créditos
                        </p>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
