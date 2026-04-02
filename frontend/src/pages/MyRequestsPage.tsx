import { useState } from 'react'
import { useMyRequests, useCreateRequest } from '@/api/hooks/useAuth'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { PlusCircle, MessageSquare } from 'lucide-react'

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
    pending: 'En espera',
    approved: 'Aprobada',
    rejected: 'Rechazada',
  }
  return (
    <Badge className={map[status] ?? 'bg-gray-100 text-gray-600 border-gray-200'}>
      {labels[status] ?? status}
    </Badge>
  )
}

function NewRequestDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createReq = useCreateRequest()
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [form, setForm] = useState({
    month: currentMonth,
    year: currentYear,
    request_type: '',
    message: '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.request_type) {
      setError('Seleccioná un tipo de solicitud.')
      return
    }
    setError(null)
    try {
      await createReq.mutateAsync({
        month: form.month,
        year: form.year,
        request_type: form.request_type,
        message: form.message || undefined,
      })
      setForm({ month: currentMonth, year: currentYear, request_type: '', message: '' })
      onClose()
    } catch {
      setError('No se pudo enviar la solicitud. Intentá de nuevo.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle style={{ color: '#003366' }}>Nueva Solicitud</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Mes *</Label>
              <Select
                value={String(form.month)}
                onValueChange={(v) => setForm((f) => ({ ...f, month: Number(v) }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-48">
                  {Object.entries(MONTH_NAMES).map(([num, name]) => (
                    <SelectItem key={num} value={num}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Año *</Label>
              <Input
                type="number"
                value={form.year}
                onChange={(e) => setForm((f) => ({ ...f, year: Number(e.target.value) }))}
                min={2020}
                max={currentYear + 1}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Tipo de Solicitud *</Label>
            <Select
              value={form.request_type}
              onValueChange={(v) => setForm((f) => ({ ...f, request_type: v }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Seleccioná un tipo..." />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(REQUEST_TYPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Mensaje (opcional)</Label>
            <Textarea
              value={form.message}
              onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
              placeholder="Describí tu solicitud o dejá un mensaje para el administrador..."
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
              disabled={createReq.isPending}
              style={{ backgroundColor: '#003366' }}
              className="text-white"
            >
              {createReq.isPending ? 'Enviando...' : 'Enviar Solicitud'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function MyRequestsPage() {
  const { data: requests, isLoading } = useMyRequests()
  const [createOpen, setCreateOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>
            Mis Solicitudes
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {requests?.length ?? 0} solicitud{requests?.length !== 1 ? 'es' : ''} enviada{requests?.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          onClick={() => setCreateOpen(true)}
          className="gap-2 text-white"
          style={{ backgroundColor: '#003366' }}
        >
          <PlusCircle size={16} />
          Nueva Solicitud
        </Button>
      </div>

      {/* Empty state */}
      {!requests?.length ? (
        <div className="py-16 text-center">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ backgroundColor: 'rgba(0,51,102,0.08)' }}
          >
            <MessageSquare size={28} style={{ color: '#003366' }} />
          </div>
          <p className="text-gray-500 font-medium">No tenés solicitudes todavía</p>
          <p className="text-gray-400 text-sm mt-1">
            Podés pedir detalles biométricos, resúmenes de horas o detalle de horario.
          </p>
          <Button
            onClick={() => setCreateOpen(true)}
            className="mt-4 gap-2 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            <PlusCircle size={16} />
            Crear tu primera solicitud
          </Button>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
              Historial de Solicitudes
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ backgroundColor: '#003366' }}>
                    {['Período', 'Tipo', 'Mensaje', 'Estado', 'Respuesta', 'Fecha'].map((h) => (
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
                  {requests.map((req, i) => (
                    <tr
                      key={req.id}
                      className={`border-b last:border-0 hover:bg-blue-50 transition-colors ${
                        i % 2 === 1 ? 'bg-gray-50' : 'bg-white'
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {MONTH_NAMES[req.month]} {req.year}
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {REQUEST_TYPE_LABELS[req.request_type] ?? req.request_type}
                      </td>
                      <td className="px-4 py-3 text-gray-500 max-w-[160px] truncate">
                        {req.message || '—'}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={req.status} />
                      </td>
                      <td className="px-4 py-3 max-w-[200px]">
                        {req.admin_response ? (
                          <span
                            className={`text-xs ${
                              req.status === 'rejected' ? 'text-red-600' : 'text-green-700'
                            }`}
                          >
                            {req.admin_response}
                          </span>
                        ) : (
                          <span className="text-gray-400 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {new Date(req.created_at).toLocaleDateString('es-BO')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <NewRequestDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
