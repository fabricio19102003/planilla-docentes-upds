import { useStudentHistory } from '@/api/hooks/useStudentPortal'
import { StudentHistory } from '@/components/students/StudentHistory'
import { Alert, AlertTitle } from '@/components/ui/alert'

export function StudentHistoryPage() {
  const history = useStudentHistory()
  if (history.isError) return <Alert variant="error" role="alert"><AlertTitle>No se pudo cargar tu historial.</AlertTitle></Alert>
  if (!history.data) return <p role="status" className="text-sm text-muted-foreground">Cargando historial…</p>
  return <StudentHistory history={history.data} />
}
