import { useState } from 'react'
import { AlertCircle, CheckCircle2, Database, Download, Trash2, HardDrive, Info } from 'lucide-react'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardPanel, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { useCreateBackup, useBackups, downloadBackup, useDeleteBackup } from '@/api/hooks/useBackup'
import type { BackupEntry } from '@/api/hooks/useBackup'
import { apiErrorMessage } from '@/lib/userCredentials'

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('es-BO', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function BackupPage() {
  const createBackup = useCreateBackup()
  const { data: backups, isLoading: backupsLoading, error: backupsError, refetch } = useBackups()
  const deleteBackup = useDeleteBackup()
  const [confirmDelete, setConfirmDelete] = useState<BackupEntry | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [lastCreated, setLastCreated] = useState<string | null>(null)

  const handleCreate = () => {
    createBackup.mutate(undefined, {
      onSuccess: (data) => {
        setLastCreated(data.filename)
      },
    })
  }

  const handleDelete = (backup: BackupEntry) => {
    setDeleteError(null)
    deleteBackup.mutate(backup.filename, {
      onSuccess: () => {
        setConfirmDelete(null)
        if (lastCreated === backup.filename) setLastCreated(null)
      },
      onError: (err) => setDeleteError(apiErrorMessage(err, 'No se pudo eliminar el respaldo.')),
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Respaldo de Base de Datos"
        description="Creá y gestioná respaldos del sistema"
      />

      {/* Create Backup Card */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Crear Nuevo Respaldo</CardTitle>
          <CardDescription>Generá un backup completo de la base de datos PostgreSQL</CardDescription>
        </CardHeader>
        <CardPanel className="flex flex-col gap-4">
          <Button onClick={handleCreate} loading={createBackup.isPending} className="w-fit">
            {createBackup.isPending ? (
              'Creando respaldo...'
            ) : (
              <>
                <HardDrive aria-hidden="true" />
                Crear Respaldo
              </>
            )}
          </Button>

          {createBackup.isError && (
            <Alert variant="error">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>
                Error al crear el respaldo. Verificá que pg_dump esté disponible y que DATABASE_URL esté configurado.
              </AlertDescription>
            </Alert>
          )}

          {lastCreated && !createBackup.isError && (
            <Alert variant="success">
              <CheckCircle2 aria-hidden="true" />
              <AlertDescription>
                Respaldo creado exitosamente: <strong className="text-foreground">{lastCreated}</strong>
              </AlertDescription>
            </Alert>
          )}
        </CardPanel>
      </Card>

      {/* Info */}
      <Alert variant="info">
        <Info aria-hidden="true" />
        <AlertDescription>
          Los respaldos incluyen toda la información del sistema: docentes, designaciones, asistencia,
          planillas, usuarios y configuración. Los archivos se almacenan en el servidor y pueden
          descargarse en cualquier momento.
        </AlertDescription>
      </Alert>

      {backupsError && (
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>No se pudieron cargar los respaldos</AlertTitle>
          <AlertDescription>Revisá tu conexión e intentá nuevamente.</AlertDescription>
          <AlertAction>
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              Reintentar
            </Button>
          </AlertAction>
        </Alert>
      )}

      {/* Backups List */}
      <TableCard
        title="Respaldos Disponibles"
        description={backups ? `${backups.length} respaldo(s) guardado(s)` : 'Cargando...'}
      >
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="h-10 px-4 text-xs font-medium uppercase tracking-wider">Archivo</TableHead>
            <TableHead className="h-10 px-4 text-right text-xs font-medium uppercase tracking-wider">Tamaño</TableHead>
            <TableHead className="h-10 px-4 text-xs font-medium uppercase tracking-wider">Fecha de creación</TableHead>
            <TableHead className="h-10 px-4 text-xs font-medium uppercase tracking-wider">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {backupsLoading ? (
            Array.from({ length: 3 }, (_, rowIndex) => (
              <TableRow key={rowIndex}>
                {Array.from({ length: 4 }, (_, cellIndex) => (
                  <TableCell key={cellIndex} className="px-4 py-3">
                    <Skeleton className="h-4 w-full max-w-32" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : !backups || backups.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={4} className="p-0 whitespace-normal">
                <EmptyState icon={Database} title="No hay respaldos disponibles" description="Creá el primero." />
              </TableCell>
            </TableRow>
          ) : (
            backups.map((backup: BackupEntry) => (
              <TableRow key={backup.filename}>
                <TableCell className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Database size={14} className="shrink-0 text-primary" aria-hidden="true" />
                    <span className="font-mono text-xs text-foreground">{backup.filename}</span>
                  </div>
                </TableCell>
                <TableCell className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {formatFileSize(backup.file_size)}
                </TableCell>
                <TableCell className="px-4 py-3 tabular-nums text-muted-foreground">{formatDate(backup.created_at)}</TableCell>
                <TableCell className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => void downloadBackup(backup.filename)}
                      title="Descargar respaldo"
                    >
                      <Download aria-hidden="true" />
                      Descargar
                    </Button>
                    <Button
                      variant="destructive-outline"
                      size="xs"
                      onClick={() => {
                        setDeleteError(null)
                        setConfirmDelete(backup)
                      }}
                      title="Eliminar respaldo"
                    >
                      <Trash2 aria-hidden="true" />
                      Eliminar
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </TableCard>

      <ConfirmAlertDialog
        summary={
          confirmDelete
            ? {
                title: 'Eliminar respaldo',
                confirmLabel: 'Eliminar respaldo',
                tone: 'destructive',
                rows: [
                  { label: 'Archivo', value: confirmDelete.filename },
                  { label: 'Tamaño', value: formatFileSize(confirmDelete.file_size) },
                  { label: 'Creado', value: formatDate(confirmDelete.created_at) },
                ],
                consequence: 'El archivo se borra del servidor y no se puede recuperar.',
              }
            : null
        }
        pending={deleteBackup.isPending}
        description={deleteError ?? undefined}
        onConfirm={() => confirmDelete && handleDelete(confirmDelete)}
        onCancel={() => {
          setConfirmDelete(null)
          setDeleteError(null)
        }}
      />
    </div>
  )
}
