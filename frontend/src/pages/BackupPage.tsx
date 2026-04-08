import { useState } from 'react'
import { Database, Download, Trash2, Loader2, HardDrive, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useCreateBackup, useBackups, downloadBackup, useDeleteBackup } from '@/api/hooks/useBackup'
import type { BackupEntry } from '@/api/hooks/useBackup'

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
  const { data: backups, isLoading: backupsLoading } = useBackups()
  const deleteBackup = useDeleteBackup()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [lastCreated, setLastCreated] = useState<string | null>(null)

  const handleCreate = () => {
    createBackup.mutate(undefined, {
      onSuccess: (data) => {
        setLastCreated(data.filename)
      },
    })
  }

  const handleDelete = (filename: string) => {
    deleteBackup.mutate(filename, {
      onSuccess: () => {
        if (confirmDelete === filename) setConfirmDelete(null)
        if (lastCreated === filename) setLastCreated(null)
      },
    })
  }

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div
        className="card-3d-static overflow-hidden"
        style={{ borderTop: '4px solid #003366' }}
      >
        <div
          className="px-6 py-5"
          style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
              <Database size={22} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Respaldo de Base de Datos</h2>
              <p className="text-sm text-blue-200 mt-0.5">Creá y gestioná respaldos del sistema</p>
            </div>
          </div>
        </div>
      </div>

      {/* Create Backup Card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Crear Nuevo Respaldo</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Generá un backup completo de la base de datos PostgreSQL
          </p>
        </div>
        <div className="px-6 py-5 flex flex-col gap-4">
          <Button
            onClick={handleCreate}
            disabled={createBackup.isPending}
            className="w-fit gap-2"
            style={{ backgroundColor: '#003366' }}
          >
            {createBackup.isPending ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Creando respaldo...
              </>
            ) : (
              <>
                <HardDrive size={16} />
                Crear Respaldo
              </>
            )}
          </Button>

          {createBackup.isError && (
            <div className="p-3 bg-red-50 rounded-lg border border-red-200 text-sm text-red-700">
              Error al crear el respaldo. Verificá que pg_dump esté disponible y que DATABASE_URL esté configurado.
            </div>
          )}

          {lastCreated && !createBackup.isError && (
            <div className="p-3 bg-green-50 rounded-lg border border-green-200 text-sm text-green-700 flex items-start gap-2">
              <span>✅</span>
              <span>
                Respaldo creado exitosamente: <strong>{lastCreated}</strong>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Info Card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Info size={16} className="text-blue-600" />
          </div>
          <p className="text-sm text-gray-600">
            Los respaldos incluyen toda la información del sistema: docentes, designaciones, asistencia,
            planillas, usuarios y configuración. Los archivos se almacenan en el servidor y pueden
            descargarse en cualquier momento.
          </p>
        </div>
      </div>

      {/* Backups List */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg gradient-stat-navy flex items-center justify-center">
            <Database size={16} className="text-white" />
          </div>
          <div>
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Respaldos Disponibles</h3>
            <p className="text-xs text-gray-500">
              {backups ? `${backups.length} respaldo(s) guardado(s)` : 'Cargando...'}
            </p>
          </div>
        </div>

        {backupsLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 size={24} className="animate-spin text-[#003366]" />
          </div>
        ) : !backups || backups.length === 0 ? (
          <div className="text-center py-10 text-gray-400 text-sm">
            No hay respaldos disponibles. Creá el primero.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                  {['Archivo', 'Tamaño', 'Fecha de creación', 'Acciones'].map((h) => (
                    <th
                      key={h}
                      className="text-left text-white font-semibold text-xs uppercase tracking-wider px-4 py-3 whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {backups.map((backup: BackupEntry, i: number) => (
                  <tr
                    key={backup.filename}
                    className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${
                      i % 2 === 1 ? 'bg-gray-50/60' : 'bg-white'
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Database size={14} className="text-[#0066CC] flex-shrink-0" />
                        <span className="font-mono text-xs text-gray-700">{backup.filename}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {formatFileSize(backup.file_size)}
                    </td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {formatDate(backup.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => void downloadBackup(backup.filename)}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded text-[#0066CC] hover:bg-blue-50 border border-[#0066CC]/30 text-xs font-medium transition-colors"
                          title="Descargar respaldo"
                        >
                          <Download size={12} />
                          Descargar
                        </button>

                        {confirmDelete === backup.filename ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleDelete(backup.filename)}
                              disabled={deleteBackup.isPending}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 text-xs font-medium transition-colors"
                            >
                              {deleteBackup.isPending ? (
                                <Loader2 size={11} className="animate-spin" />
                              ) : (
                                'Confirmar'
                              )}
                            </button>
                            <button
                              onClick={() => setConfirmDelete(null)}
                              className="px-2 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 text-xs transition-colors"
                            >
                              Cancelar
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setConfirmDelete(backup.filename)}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded text-red-500 hover:bg-red-50 border border-red-200 text-xs font-medium transition-colors"
                            title="Eliminar respaldo"
                          >
                            <Trash2 size={12} />
                            Eliminar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
