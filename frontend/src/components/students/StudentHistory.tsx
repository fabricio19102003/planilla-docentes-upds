import { EmptyState } from '@/components/shared/EmptyState'
import { TableCard } from '@/components/shared/TableCard'
import { Badge } from '@/components/ui/badge'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatGrade, recordStatus, termAverage, type StudentDetail } from '@/lib/academicRecordsState'

/** Subject history grouped by term, newest first; shared by the admin detail and the student portal. */
export function StudentHistory({ history }: { history: StudentDetail['history'] }) {
  return (
    <>
    <h2 className="text-lg font-semibold">Historial académico</h2>
    {history.length === 0 && <EmptyState title="Sin materias registradas" description="Este estudiante no tiene materias en los archivos importados." />}
    {history.map(({ term, records }) => {
      const average = termAverage(records)
      return (
        <TableCard
          key={term.code}
          title={(
            <span className="flex flex-wrap items-center gap-2">
              {term.name}
              {term.is_intensive && <Badge variant="info" size="sm">Curso intensivo</Badge>}
            </span>
          )}
          description={`${records.length} materia(s)${average === null ? '' : ` · promedio del período ${average}`}`}
          tableClassName="min-w-[720px]"
        >
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="px-4">Materia</TableHead>
              <TableHead className="px-4">Grupo</TableHead>
              <TableHead className="px-4">Docente</TableHead>
              <TableHead className="px-4">Estado</TableHead>
              <TableHead className="px-4 text-right">Nota</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.map((record) => {
              const status = recordStatus(record.status)
              return (
                <TableRow key={record.legacy_registration_id}>
                  <TableCell className="min-w-56 px-4 py-3 whitespace-normal">
                    <p className="font-medium text-foreground">{record.subject_name}</p>
                    <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                      {record.subject_code}
                      {!record.in_curriculum && <Badge variant="warning" size="sm">Fuera de malla</Badge>}
                    </p>
                  </TableCell>
                  <TableCell className="px-4 py-3">{[record.group_code, record.shift].filter(Boolean).join(' · ') || '—'}</TableCell>
                  <TableCell className="px-4 py-3 whitespace-normal">{record.teacher_name ?? '—'}</TableCell>
                  <TableCell className="px-4 py-3"><Badge variant={status.variant}>{status.label}</Badge></TableCell>
                  <TableCell className="px-4 py-3 text-right tabular-nums">{formatGrade(record.grade)}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </TableCard>
      )
    })}
    </>
  )
}
