import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileUp, GraduationCap, KeyRound } from 'lucide-react'

import { useStudents } from '@/api/hooks/useAcademicRecords'
import { useIssueTemporaryPasswords } from '@/api/hooks/useReenrollment'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { CredentialsDialog } from '@/components/students/CredentialsDialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  LEGACY_ENROLLMENT_STATUSES,
  STUDENT_PAGE_SIZE,
  type NationalityFilter,
  type StudentFilters,
} from '@/lib/academicRecordsState'
import type { TemporaryCredential } from '@/lib/reenrollmentState'
import { apiErrorMessage } from '@/lib/userCredentials'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

export function StudentsPage() {
  const [filters, setFilters] = useState<StudentFilters>({ search: '', status: '', nationality: 'all', page: 1 })
  const students = useStudents(filters)
  const total = students.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / STUDENT_PAGE_SIZE))
  const update = (patch: Partial<StudentFilters>) => setFilters((current) => ({ ...current, page: 1, ...patch }))
  const hasFilters = Boolean(filters.search.trim() || filters.status || filters.nationality !== 'all')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [credentials, setCredentials] = useState<TemporaryCredential[]>([])
  const issue = useIssueTemporaryPasswords()
  const pageIds = students.data?.items.map((student) => student.id) ?? []
  const pageSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id))
  const toggle = (ids: number[], on: boolean) => setSelected((current) => {
    const next = new Set(current)
    ids.forEach((id) => (on ? next.add(id) : next.delete(id)))
    return next
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Estudiantes"
        description="Datos personales e historial académico importados del sistema académico."
        actions={(
          <>
            <Button
              disabled={selected.size === 0 || selected.size > 100 || issue.isPending}
              onClick={() => issue.mutate([...selected], { onSuccess: (issued) => { setCredentials(issued); setSelected(new Set()) } })}
            >
              <KeyRound aria-hidden="true" />
              {selected.size === 0 ? 'Generar claves temporales' : `Generar claves temporales (${selected.size})`}
            </Button>
            <Button variant="outline" render={<Link to="/academic-history-import" />}><FileUp aria-hidden="true" />Importar historial</Button>
          </>
        )}
      />
      {selected.size > 100 && (
        <Alert variant="warning" role="status"><AlertTitle>Podés generar hasta 100 claves por vez; quitá {selected.size - 100} de la selección.</AlertTitle></Alert>
      )}
      {issue.isError && (
        <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(issue.error, 'No se pudieron generar las claves.')}</AlertTitle></Alert>
      )}
      <CredentialsDialog credentials={credentials} onClose={() => setCredentials([])} />

      <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-4" role="search">
        <div className="sm:col-span-2">
          <Label htmlFor="students-search">Buscar por nombre o documento</Label>
          <Input id="students-search" type="search" value={filters.search} onChange={(event) => update({ search: event.target.value })} placeholder="Ej: Paiva o I-11626046" />
        </div>
        <div>
          <Label htmlFor="students-status">Estado de inscripción</Label>
          <select id="students-status" className={selectClass} value={filters.status} onChange={(event) => update({ status: event.target.value })}>
            <option value="">Todos</option>
            {LEGACY_ENROLLMENT_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </div>
        <div>
          <Label htmlFor="students-nationality">Nacionalidad</Label>
          <select id="students-nationality" className={selectClass} value={filters.nationality} onChange={(event) => update({ nationality: event.target.value as NationalityFilter })}>
            <option value="all">Todas</option>
            <option value="national">Bolivianos</option>
            <option value="foreign">Extranjeros</option>
          </select>
        </div>
      </div>

      {students.isError && (
        <Alert variant="error" role="alert">
          <AlertTitle>No se pudieron cargar los estudiantes.</AlertTitle>
          <AlertDescription><Button size="sm" variant="outline" onClick={() => void students.refetch()}>Reintentar</Button></AlertDescription>
        </Alert>
      )}

      {!students.isLoading && !students.isError && total === 0 ? (
        <EmptyState
          icon={GraduationCap}
          title={hasFilters ? 'Ningún estudiante coincide con estos filtros' : 'Todavía no hay estudiantes'}
          description={hasFilters ? 'Probá con otro nombre, documento o filtro.' : 'Importá el CSV de una gestión desde el sistema académico.'}
        />
      ) : (
        <TableCard
          tableClassName="min-w-[760px]"
          footer={(
            <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
              <span>{total} estudiante(s) · página {filters.page} de {pages}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={filters.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>Anterior</Button>
                <Button size="sm" variant="outline" disabled={filters.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>Siguiente</Button>
              </div>
            </div>
          )}
        >
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="w-10 px-4">
                <Checkbox aria-label="Seleccionar la página" checked={pageSelected} onCheckedChange={(on) => toggle(pageIds, Boolean(on))} />
              </TableHead>
              <TableHead className="px-4">Estudiante</TableHead>
              <TableHead className="px-4">Nacionalidad</TableHead>
              <TableHead className="px-4">Estado</TableHead>
              <TableHead className="px-4">Último período</TableHead>
              <TableHead className="px-4 text-right">Materias cursadas</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {students.isLoading && (
              <TableRow><TableCell colSpan={6} role="status" className="px-4 py-10 text-center text-muted-foreground">Cargando estudiantes…</TableCell></TableRow>
            )}
            {students.data?.items.map((student) => (
              <TableRow key={student.id}>
                <TableCell className="px-4 py-3">
                  <Checkbox
                    aria-label={`Seleccionar a ${student.full_name}`}
                    checked={selected.has(student.id)}
                    onCheckedChange={(on) => toggle([student.id], Boolean(on))}
                  />
                </TableCell>
                <TableCell className="px-4 py-3">
                  <Link to={`/students/${student.id}`} className="font-medium text-foreground underline-offset-4 hover:underline">{student.full_name}</Link>
                  <p className="text-xs text-muted-foreground">{student.document_number}</p>
                </TableCell>
                <TableCell className="px-4 py-3">
                  {student.nationality ?? '—'}
                  {student.is_foreign && <Badge variant="warning" size="sm" className="ml-2">Extranjero</Badge>}
                </TableCell>
                <TableCell className="px-4 py-3">{student.legacy_enrollment_status ?? '—'}</TableCell>
                <TableCell className="px-4 py-3">{student.last_term ?? '—'}</TableCell>
                <TableCell className="px-4 py-3 text-right tabular-nums">{student.record_count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </TableCard>
      )}
    </div>
  )
}
