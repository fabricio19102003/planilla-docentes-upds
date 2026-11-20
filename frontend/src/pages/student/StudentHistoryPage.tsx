import { GraduationCap, History } from 'lucide-react'

import { useStudentHistory } from '@/api/hooks/useStudentPortal'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StudentHistoryTimeline } from '@/components/students/StudentHistoryTimeline'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Eyebrow } from '@/components/student/Eyebrow'
import '@/styles/student/history.css'

export function StudentHistoryPage() {
  const history = useStudentHistory()
  return (
    <>
      <PageHeader as="h1" className="sp-hist-head"
        breadcrumb={<Eyebrow icon={<GraduationCap />}>Tu carrera</Eyebrow>}
        title="Historial académico"
        description="Tus materias por período, con la nota final y el avance de tu carrera."
      />
      {history.isError && <Alert variant="error" role="alert"><AlertTitle>No se pudo cargar tu historial.</AlertTitle></Alert>}
      {!history.isError && !history.data && (
        <div role="status" aria-label="Cargando historial" className="space-y-4">
          <Skeleton className="h-56 w-full rounded-3xl" />
          <Skeleton className="ml-12 h-[4.5rem] w-auto rounded-3xl" />
          <Skeleton className="ml-12 h-[4.5rem] w-auto rounded-3xl" />
        </div>
      )}
      {history.data?.length === 0 && (
        <EmptyState illustration="empty-box" icon={History} title="Sin materias registradas" description="Todavía no tenés materias en tu historial académico." />
      )}
      {history.data && history.data.length > 0 && <StudentHistoryTimeline history={history.data} />}
    </>
  )
}
