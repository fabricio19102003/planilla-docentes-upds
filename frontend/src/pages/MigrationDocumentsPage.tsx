import { ArrowDown, ArrowUp, FileText } from 'lucide-react'
import { useState } from 'react'

import {
  useDeactivateMigrationDocumentType,
  useMigrationDocumentTypes,
  useSaveMigrationDocumentType,
  type TypeChanges,
} from '@/api/hooks/useMigrationDocuments'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { MAX_NAME_LENGTH, movePosition, typeNameProblem, type MigrationDocumentType } from '@/lib/migrationDocumentsState'
import { apiErrorMessage } from '@/lib/userCredentials'

function NewTypeForm() {
  const save = useSaveMigrationDocumentType()
  const [name, setName] = useState('')
  const [requiresExpiry, setRequiresExpiry] = useState(false)
  const problem = typeNameProblem(name)
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (problem) return
        save.mutate({ changes: { name: name.trim(), requires_expiry: requiresExpiry } }, {
          onSuccess: () => { setName(''); setRequiresExpiry(false) },
        })
      }}
    >
      <div>
        <Label htmlFor="new-document-name">Nombre del documento</Label>
        <Input id="new-document-name" className="w-72" maxLength={MAX_NAME_LENGTH + 20} value={name} aria-invalid={name !== '' && problem !== null}
          onChange={(event) => { save.reset(); setName(event.target.value) }} />
      </div>
      <label className="flex h-9 items-center gap-2 text-sm">
        <input type="checkbox" checked={requiresExpiry} onChange={(event) => setRequiresExpiry(event.target.checked)} />
        Tiene vencimiento
      </label>
      <Button type="submit" disabled={save.isPending || problem !== null}>Agregar documento</Button>
      {problem && name !== '' && <p className="basis-full text-sm text-destructive" role="alert">{problem}</p>}
      {save.isError && <Alert variant="error" role="alert" className="basis-full"><AlertTitle>{apiErrorMessage(save.error, 'No se pudo agregar el documento.')}</AlertTitle></Alert>}
    </form>
  )
}

function TypeRow({ item, types }: { item: MigrationDocumentType; types: MigrationDocumentType[] }) {
  const save = useSaveMigrationDocumentType()
  const deactivate = useDeactivateMigrationDocumentType()
  const [name, setName] = useState(item.name)
  const problem = typeNameProblem(name)
  const change = (changes: TypeChanges) => save.mutate({ id: item.id, changes })
  const up = movePosition(types, item.id, 'up')
  const down = movePosition(types, item.id, 'down')
  const error = save.error ?? deactivate.error

  return (
    <TableRow className={item.active ? undefined : 'opacity-70'}>
      <TableCell className="px-4 py-3">
        <div className="flex items-center gap-2">
          <Input aria-label={`Nombre de ${item.name}`} className="min-w-56" value={name} aria-invalid={problem !== null}
            onChange={(event) => { save.reset(); setName(event.target.value) }} />
          <Button size="sm" variant="outline" disabled={save.isPending || problem !== null || name.trim() === item.name}
            onClick={() => change({ name: name.trim() })}>Renombrar</Button>
        </div>
        {problem && <p className="mt-1 text-xs text-destructive" role="alert">{problem}</p>}
        {error && <p className="mt-1 text-xs text-destructive" role="alert">{apiErrorMessage(error, 'No se pudo guardar el cambio.')}</p>}
      </TableCell>
      <TableCell className="px-4 py-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={item.requires_expiry} disabled={save.isPending}
            onChange={(event) => change({ requires_expiry: event.target.checked })} />
          Tiene vencimiento
        </label>
      </TableCell>
      <TableCell className="px-4 py-3"><Badge variant={item.active ? 'success' : 'outline'}>{item.active ? 'Activo' : 'Inactivo'}</Badge></TableCell>
      <TableCell className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" aria-label={`Subir ${item.name}`} disabled={save.isPending || up === null}
            onClick={() => up !== null && change({ position: up })}><ArrowUp aria-hidden="true" /></Button>
          <Button size="sm" variant="outline" aria-label={`Bajar ${item.name}`} disabled={save.isPending || down === null}
            onClick={() => down !== null && change({ position: down })}><ArrowDown aria-hidden="true" /></Button>
          {item.active
            ? <Button size="sm" variant="outline" disabled={deactivate.isPending} onClick={() => deactivate.mutate(item.id)}>Desactivar</Button>
            : <Button size="sm" variant="outline" disabled={save.isPending} onClick={() => change({ active: true })}>Reactivar</Button>}
        </div>
      </TableCell>
    </TableRow>
  )
}

export function MigrationDocumentsPage() {
  const types = useMigrationDocumentTypes()
  const list = types.data ?? []
  return (
    <div className="space-y-5">
      <PageHeader title="Documentos migratorios" description="Lista de documentos que deben presentar los estudiantes extranjeros. Un estudiante está regularizado cuando tiene todos los documentos activos y ninguno está vencido." />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Nuevo documento</CardTitle>
          <CardDescription>Los documentos desactivados dejan de exigirse pero conservan lo ya registrado.</CardDescription>
        </CardHeader>
        <CardContent><NewTypeForm /></CardContent>
      </Card>
      {types.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(types.error, 'No se pudo cargar la lista de documentos.')}</AlertTitle></Alert>}
      {types.isSuccess && list.length === 0 && (
        <EmptyState illustration="empty-document" icon={FileText} title="Todavía no definiste documentos" description="Agregá los documentos migratorios que se exigen; mientras no haya ninguno activo todos los estudiantes cuentan como regularizados." />
      )}
      {list.length > 0 && (
        <TableCard tableClassName="min-w-[760px]" footer={<p className="text-sm text-muted-foreground">El orden de esta lista es el que se usa al nombrar los documentos pendientes.</p>}>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="px-4">Documento</TableHead>
              <TableHead className="px-4">Vencimiento</TableHead>
              <TableHead className="px-4">Estado</TableHead>
              <TableHead className="px-4">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.map((item) => <TypeRow key={`${item.id}-${item.name}`} item={item} types={list} />)}
          </TableBody>
        </TableCard>
      )}
    </div>
  )
}
