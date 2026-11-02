import { useState } from 'react'

import {
  useRemoveStudentDocument,
  useSaveStudentDocument,
  useStudentMigrationDocuments,
} from '@/api/hooks/useMigrationDocuments'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  MAX_NOTES_LENGTH,
  documentBadge,
  documentFormProblem,
  documentPayload,
  formatExpiry,
  regularizadoBadge,
  type StudentDocumentRow,
} from '@/lib/migrationDocumentsState'
import { apiErrorMessage } from '@/lib/userCredentials'

function DocumentForm({ studentId, row, onDone }: { studentId: number; row: StudentDocumentRow; onDone: () => void }) {
  const save = useSaveStudentDocument(studentId)
  const [expiresOn, setExpiresOn] = useState(row.expires_on ?? '')
  const [notes, setNotes] = useState(row.notes ?? '')
  const problem = documentFormProblem(row.requires_expiry, expiresOn, notes)
  const id = `document-${row.type_id}`
  return (
    <form
      className="mt-3 grid gap-3 sm:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (problem) return
        save.mutate({ typeId: row.type_id, payload: documentPayload(row.requires_expiry, expiresOn, notes) }, { onSuccess: onDone })
      }}
    >
      {row.requires_expiry && (
        <div>
          <Label htmlFor={`${id}-expiry`}>Vence el</Label>
          <Input id={`${id}-expiry`} type="date" value={expiresOn} onChange={(event) => { save.reset(); setExpiresOn(event.target.value) }} />
        </div>
      )}
      <div className={row.requires_expiry ? undefined : 'sm:col-span-2'}>
        <Label htmlFor={`${id}-notes`}>Notas (opcional)</Label>
        <Textarea id={`${id}-notes`} maxLength={MAX_NOTES_LENGTH + 50} value={notes} onChange={(event) => { save.reset(); setNotes(event.target.value) }} />
      </div>
      {problem && (expiresOn !== '' || notes !== '') && <p className="text-sm text-destructive sm:col-span-2" role="alert">{problem}</p>}
      {save.isError && <Alert variant="error" role="alert" className="sm:col-span-2"><AlertTitle>{apiErrorMessage(save.error, 'No se pudo guardar el documento.')}</AlertTitle></Alert>}
      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" size="sm" disabled={save.isPending || problem !== null}>Guardar</Button>
        <Button type="button" size="sm" variant="outline" onClick={onDone}>Cancelar</Button>
      </div>
    </form>
  )
}

function DocumentItem({ studentId, row }: { studentId: number; row: StudentDocumentRow }) {
  const remove = useRemoveStudentDocument(studentId)
  const [editing, setEditing] = useState(false)
  const badge = documentBadge(row.state)
  const recorded = row.state !== 'missing' || row.expires_on !== null || row.notes !== null
  return (
    <li className="px-3 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="space-y-0.5">
          <p className="flex flex-wrap items-center gap-2 font-medium">
            {row.name} <Badge variant={badge.variant} size="sm">{badge.label}</Badge>
          </p>
          {row.requires_expiry && <p className="text-xs text-muted-foreground">Vence: {formatExpiry(row.expires_on)}</p>}
          {row.notes && <p className="text-xs text-muted-foreground">{row.notes}</p>}
        </div>
        {!editing && (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>{recorded ? 'Editar' : 'Registrar'}</Button>
            {recorded && <Button size="sm" variant="outline" disabled={remove.isPending} onClick={() => remove.mutate(row.type_id)}>Quitar</Button>}
          </div>
        )}
      </div>
      {remove.isError && <p className="mt-1 text-xs text-destructive" role="alert">{apiErrorMessage(remove.error, 'No se pudo quitar el documento.')}</p>}
      {editing && <DocumentForm studentId={studentId} row={row} onDone={() => setEditing(false)} />}
    </li>
  )
}

/** Migration documents of a foreign student: what is presented, missing or expired, and the overall status. */
export function MigrationDocumentsCard({ studentId }: { studentId: number }) {
  const query = useStudentMigrationDocuments(studentId)
  const data = query.data
  const badge = data ? regularizadoBadge(data) : null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          Documentos migratorios {badge && <Badge variant={badge.variant}>{badge.label}</Badge>}
        </CardTitle>
        <CardDescription>Un estudiante extranjero está regularizado cuando presentó todos los documentos requeridos y ninguno está vencido.</CardDescription>
      </CardHeader>
      <CardContent>
        {query.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(query.error, 'No se pudieron cargar los documentos.')}</AlertTitle></Alert>}
        {!data && !query.isError && <p role="status" className="text-sm text-muted-foreground">Cargando documentos…</p>}
        {data && data.documents.length === 0 && <p className="text-sm text-muted-foreground">No hay documentos requeridos activos. Se definen en Documentos migratorios.</p>}
        {data && data.documents.length > 0 && (
          <ul className="divide-y rounded-lg border">
            {data.documents.map((row) => <DocumentItem key={row.type_id} studentId={studentId} row={row} />)}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
