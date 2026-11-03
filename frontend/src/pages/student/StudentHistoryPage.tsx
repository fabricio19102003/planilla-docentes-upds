import { History } from 'lucide-react'

import { useStudentHistory } from '@/api/hooks/useStudentPortal'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StudentHistoryTimeline } from '@/components/students/StudentHistoryTimeline'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'

export function StudentHistoryPage() {
  const history = useStudentHistory()
  return (
    <>
      <h1 className="sr-only">Portal del estudiante: Historial académico</h1>
      <PageHeader title="Historial académico" description="Tus materias por período, con la nota final y el avance de tu carrera." />
      {history.isError && <Alert variant="error" role="alert"><AlertTitle>No se pudo cargar tu historial.</AlertTitle></Alert>}
      {!history.isError && !history.data && (
        <div role="status" aria-label="Cargando historial" className="space-y-4">
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      )}
      {history.data?.length === 0 && (
        <EmptyState illustration="empty-box" icon={History} title="Sin materias registradas" description="Todavía no tenés materias en tu historial académico." />
      )}
      {history.data && history.data.length > 0 && <StudentHistoryTimeline history={history.data} />}
    </>
  )
}
