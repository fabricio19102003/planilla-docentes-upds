import { useState } from 'react'
import { useAllRequests, useRespondRequest } from '@/api/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Check, X, Filter } from 'lucide-react'
import type { DetailRequestInfo } from '@/api/types'

type StatusFilter = 'all' | 'pending' | 'approved' | 'rejected'

const REQUEST_TYPE_LABELS: Record<string, string> = {
  biometric_detail: 'Detalle Biométrico',
  hours_summary: 'Resumen de Horas',
  schedule_detail: 'Detalle de Horario',
}

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    approved: 'bg-green-100 text-green-700 border-green-200',
    rejected: 'bg-red-100 text-red-700 border-red-200',
  }
  const labels: Record<string, string> = {
    pending: 'Pendiente',
    approved: 'Aprobada',
    rejected: 'Rechazada',
  }
  return (
    <Badge className={map[status] ?? 'bg-gray-100 text-gray-600 border-gray-200'}>
      {labels[status] ?? status}
    </Badge>
  )
}

function RespondDialog({
  request,
  action,
  onClose,
}: {
  request: DetailRequestInfo | null
  action: 'approved' | 'rejected' | null
  onClose: () => void
}) {
  const respond = useRespondRequest()
  const [adminResponse, setAdminResponse] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!request || !action) return
    setError(null)
    try {
      await respond.mutateAsync({
        id: request.id,
        data: {
          status: action,
          admin_response: adminResponse || undefined,
        },
      })
      setAdminResponse('')
      onClose()
    } catch {
      setError('No se pudo procesar la solicitud.')
    }
  }

  if (!request || !action) return null

  return (
    <Dialog open={Boolean(request)} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle style={{ color: '#003366' }}>
            {action === 'approved' ? 'Aprobar Solicitud' : 'Rechazar Solicitud'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="bg-gray-50 rounded-lg p-3 space-y-1.5 text-sm">
            <p>
              <span className="text-gray-500">Docente:</span>{' '}
              <span className="font-medium">{request.teacher_name ?? request.teacher_ci}</span>
            </p>
            <p>
              <span className="text-gray-500">Solicitud:</span>{' '}
              <span className="font-medium">
                {REQUEST_TYPE_LABELS[request.request_type] ?? request.request_type}
              </span>
            </p>
            <p>
              <span className="text-gray-500">Período:</span>{' '}
              <span className="font-medium">
                {MONTH_NAMES[request.month]} {request.year}
              </span>
            </p>
            {request.message && (
              <p>
                <span className="text-gray-500">Mensaje:</span>{' '}
                <span className="text-gray-700 italic">"{request.message}"</span>
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Respuesta al docente (opcional)</Label>
            <Textarea
              value={adminResponse}
              onChange={(e) => setAdminResponse(e.target.value)}
              placeholder="Ingresá una respuesta para el docente..."
              rows={3}
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={respond.isPending}
              className={action === 'approved' ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-red-600 hover:bg-red-700 text-white'}
            >
              {respond.isPending
                ? 'Procesando...'
                : action === 'approved'
                ? 'Aprobar'
                : 'Rechazar'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function AdminRequestsPage() {
  const { data: requests, isLoading } = useAllRequests()
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [respondTarget, setRespondTarget] = useState<DetailRequestInfo | null>(null)
  const [respondAction, setRespondAction] = useState<'approved' | 'rejected' | null>(null)

  const handleRespond = (req: DetailRequestInfo, action: 'approved' | 'rejected') => {
    setRespondTarget(req)
    setRespondAction(action)
  }

  const handleClose = () => {
    setRespondTarget(null)
    setRespondAction(null)
  }

  const filtered = requests?.filter((r) => {
    if (filter === 'all') return true
    return r.status === filter
  })

  const pendingCount = requests?.filter((r) => r.status === 'pending').length ?? 0

  const filterButtons: { key: StatusFilter; label: string }[] = [
    { key: 'all', label: 'Todas' },
    { key: 'pending', label: 'Pendientes' },
    { key: 'approved', label: 'Aprobadas' },
    { key: 'rejected', label: 'Rechazadas' },
  ]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>
            Solicitudes de Docentes
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {pendingCount > 0
              ? `${pendingCount} solicitud${pendingCount !== 1 ? 'es' : ''} pendiente${pendingCount !== 1 ? 's' : ''}`
              : 'Sin solicitudes pendientes'}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter size={15} className="text-gray-400" />
        {filterButtons.map((btn) => (
          <button
            key={btn.key}
            onClick={() => setFilter(btn.key)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === btn.key
                ? 'text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            style={filter === btn.key ? { backgroundColor: '#003366' } : undefined}
          >
            {btn.label}
            {btn.key === 'pending' && pendingCount > 0 && (
              <span className="ml-1.5 bg-yellow-400 text-yellow-900 text-xs font-bold rounded-full px-1.5">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
            {filtered?.length ?? 0} solicitud{filtered?.length !== 1 ? 'es' : ''}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: '#003366' }}>
                  {['Docente', 'Período', 'Tipo de Solicitud', 'Mensaje', 'Estado', 'Fecha', 'Acciones'].map((h) => (
                    <th
                      key={h}
                      className="text-left text-white font-semibold text-xs uppercase tracking-wider px-4 py-3"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!filtered?.length ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-gray-400">
                      No hay solicitudes para mostrar
                    </td>
                  </tr>
                ) : (
                  filtered.map((req, i) => (
                    <tr
                      key={req.id}
                      className={`border-b last:border-0 hover:bg-blue-50 transition-colors ${
                        i % 2 === 1 ? 'bg-gray-50' : 'bg-white'
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {req.teacher_name ?? req.teacher_ci}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {MONTH_NAMES[req.month]} {req.year}
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {REQUEST_TYPE_LABELS[req.request_type] ?? req.request_type}
                      </td>
                      <td className="px-4 py-3 text-gray-500 max-w-[200px] truncate">
                        {req.message || '—'}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={req.status} />
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {new Date(req.created_at).toLocaleDateString('es-BO')}
                      </td>
                      <td className="px-4 py-3">
                        {req.status === 'pending' ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleRespond(req, 'approved')}
                              className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-green-100 text-green-700 hover:bg-green-200 transition-colors"
                            >
                              <Check size={12} />
                              Aprobar
                            </button>
                            <button
                              onClick={() => handleRespond(req, 'rejected')}
                              className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                            >
                              <X size={12} />
                              Rechazar
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">
                            {req.admin_response ? `"${req.admin_response.slice(0, 30)}..."` : 'Sin respuesta'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <RespondDialog request={respondTarget} action={respondAction} onClose={handleClose} />
    </div>
  )
}
