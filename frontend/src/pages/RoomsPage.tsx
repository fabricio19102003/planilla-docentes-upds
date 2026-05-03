import { useState, useMemo } from 'react'
import {
  Building2,
  Monitor,
  Wrench,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  AlertTriangle,
  Users,
  ChevronDown,
  ChevronUp,
  X,
} from 'lucide-react'
import {
  useRoomTypes,
  useCreateRoomType,
  useUpdateRoomType,
  useDeleteRoomType,
  useEquipment,
  useCreateEquipment,
  useUpdateEquipment,
  useDeleteEquipment,
  useRooms,
  useRoom,
  useCreateRoom,
  useUpdateRoom,
  useDeleteRoom,
  useAddRoomEquipment,
  useRemoveRoomEquipment,
} from '@/api/hooks/useScheduling'
import type { RoomType, EquipmentItem, Room, RoomEquipment } from '@/api/hooks/useScheduling'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ErrorBanner({ error }: { error: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
      <AlertTriangle size={14} />
      {error}
    </div>
  )
}

function extractAxiosError(err: unknown, fallback: string): string {
  const axiosErr = err as { response?: { data?: { detail?: string } } }
  return axiosErr?.response?.data?.detail ?? fallback
}

// ─── Room Type Dialogs ────────────────────────────────────────────────────────

function CreateRoomTypeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateRoomType()
  const [form, setForm] = useState({ code: '', name: '', description: '' })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim() || !form.name.trim()) {
      setError('Codigo y nombre son obligatorios.')
      return
    }
    setError(null)
    try {
      await create.mutateAsync({
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      setForm({ code: '', name: '', description: '' })
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo crear el tipo de sala.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Building2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nuevo Tipo de Sala</h2>
              <p className="text-white/60 text-sm">Registrar un nuevo tipo</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Codigo *</Label>
              <Input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="AUL"
                className="uppercase"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Aula"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Descripcion</Label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Descripcion opcional..."
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent resize-none"
              rows={2}
            />
          </div>
          {error && <ErrorBanner error={error} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={create.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {create.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Crear Tipo
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EditRoomTypeDialog({
  open,
  onClose,
  roomType,
}: {
  open: boolean
  onClose: () => void
  roomType: RoomType
}) {
  const update = useUpdateRoomType()
  const [form, setForm] = useState({
    name: roomType.name,
    description: roomType.description ?? '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre es obligatorio.')
      return
    }
    setError(null)
    try {
      await update.mutateAsync({
        id: roomType.id,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo actualizar el tipo de sala.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Edit2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Editar Tipo de Sala</h2>
              <p className="text-white/60 text-sm">{roomType.code}</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Nombre *</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Descripcion</Label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent resize-none"
              rows={2}
            />
          </div>
          {error && <ErrorBanner error={error} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={update.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {update.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Equipment Dialogs ────────────────────────────────────────────────────────

function CreateEquipmentDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateEquipment()
  const [form, setForm] = useState({ code: '', name: '', description: '' })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim() || !form.name.trim()) {
      setError('Codigo y nombre son obligatorios.')
      return
    }
    setError(null)
    try {
      await create.mutateAsync({
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      setForm({ code: '', name: '', description: '' })
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo crear el equipamiento.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Monitor size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nuevo Equipamiento</h2>
              <p className="text-white/60 text-sm">Registrar un nuevo equipo</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Codigo *</Label>
              <Input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="PROJ"
                className="uppercase"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Proyector"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Descripcion</Label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Descripcion opcional..."
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent resize-none"
              rows={2}
            />
          </div>
          {error && <ErrorBanner error={error} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={create.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {create.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Crear Equipo
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EditEquipmentDialog({
  open,
  onClose,
  equipment,
}: {
  open: boolean
  onClose: () => void
  equipment: EquipmentItem
}) {
  const update = useUpdateEquipment()
  const [form, setForm] = useState({
    name: equipment.name,
    description: equipment.description ?? '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre es obligatorio.')
      return
    }
    setError(null)
    try {
      await update.mutateAsync({
        id: equipment.id,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo actualizar el equipamiento.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Edit2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Editar Equipamiento</h2>
              <p className="text-white/60 text-sm">{equipment.code}</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Nombre *</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Descripcion</Label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent resize-none"
              rows={2}
            />
          </div>
          {error && <ErrorBanner error={error} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={update.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {update.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Room Dialogs ─────────────────────────────────────────────────────────────

function CreateRoomDialog({
  open,
  onClose,
  roomTypes,
  equipmentList,
}: {
  open: boolean
  onClose: () => void
  roomTypes: RoomType[]
  equipmentList: EquipmentItem[]
}) {
  const create = useCreateRoom()
  const [form, setForm] = useState({
    code: '',
    name: '',
    building: '',
    floor: '',
    capacity: '',
    room_type_id: '',
    description: '',
  })
  const [equipmentItems, setEquipmentItems] = useState<
    { equipment_id: string; quantity: string; notes: string }[]
  >([])
  const [error, setError] = useState<string | null>(null)

  const addEquipmentRow = () => {
    setEquipmentItems((prev) => [...prev, { equipment_id: '', quantity: '1', notes: '' }])
  }

  const removeEquipmentRow = (index: number) => {
    setEquipmentItems((prev) => prev.filter((_, i) => i !== index))
  }

  const updateEquipmentRow = (
    index: number,
    field: 'equipment_id' | 'quantity' | 'notes',
    value: string,
  ) => {
    setEquipmentItems((prev) => prev.map((item, i) => (i === index ? { ...item, [field]: value } : item)))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (
      !form.code.trim() ||
      !form.name.trim() ||
      !form.building.trim() ||
      !form.floor.trim() ||
      !form.capacity ||
      !form.room_type_id
    ) {
      setError('Todos los campos marcados con * son obligatorios.')
      return
    }
    setError(null)
    try {
      const equipment = equipmentItems
        .filter((eq) => eq.equipment_id)
        .map((eq) => ({
          equipment_id: Number(eq.equipment_id),
          quantity: Number(eq.quantity) || 1,
          notes: eq.notes.trim() || undefined,
        }))

      await create.mutateAsync({
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        building: form.building.trim(),
        floor: form.floor.trim(),
        capacity: Number(form.capacity),
        room_type_id: Number(form.room_type_id),
        description: form.description.trim() || undefined,
        equipment: equipment.length > 0 ? equipment : undefined,
      })
      setForm({
        code: '',
        name: '',
        building: '',
        floor: '',
        capacity: '',
        room_type_id: '',
        description: '',
      })
      setEquipmentItems([])
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo crear la sala.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl p-0 overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Building2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nueva Sala</h2>
              <p className="text-white/60 text-sm">Registrar una nueva sala</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Codigo *</Label>
              <Input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="A-101"
                className="uppercase"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Aula 101"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Edificio *</Label>
              <Input
                value={form.building}
                onChange={(e) => setForm((f) => ({ ...f, building: e.target.value }))}
                placeholder="Bloque A"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Piso *</Label>
              <Input
                value={form.floor}
                onChange={(e) => setForm((f) => ({ ...f, floor: e.target.value }))}
                placeholder="1"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Capacidad *</Label>
              <Input
                type="number"
                min="1"
                value={form.capacity}
                onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))}
                placeholder="40"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Tipo de Sala *</Label>
              <Select
                value={form.room_type_id}
                onValueChange={(v) => setForm((f) => ({ ...f, room_type_id: v }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Seleccionar tipo" />
                </SelectTrigger>
                <SelectContent>
                  {roomTypes.map((rt) => (
                    <SelectItem key={rt.id} value={String(rt.id)}>
                      {rt.name} ({rt.code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Descripcion</Label>
              <Input
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Opcional"
              />
            </div>
          </div>

          {/* Equipment section */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-3">
              <Label className="text-sm font-semibold">Equipamiento (opcional)</Label>
              <Button type="button" variant="outline" size="sm" onClick={addEquipmentRow} className="gap-1 text-xs">
                <Plus size={12} />
                Agregar Equipo
              </Button>
            </div>
            {equipmentItems.map((item, idx) => (
              <div key={idx} className="flex items-center gap-2 mb-2">
                <Select
                  value={item.equipment_id}
                  onValueChange={(v) => updateEquipmentRow(idx, 'equipment_id', v)}
                >
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Equipo" />
                  </SelectTrigger>
                  <SelectContent>
                    {equipmentList.map((eq) => (
                      <SelectItem key={eq.id} value={String(eq.id)}>
                        {eq.name} ({eq.code})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  min="1"
                  className="w-20"
                  value={item.quantity}
                  onChange={(e) => updateEquipmentRow(idx, 'quantity', e.target.value)}
                  placeholder="Cant"
                />
                <Input
                  className="w-32"
                  value={item.notes}
                  onChange={(e) => updateEquipmentRow(idx, 'notes', e.target.value)}
                  placeholder="Notas"
                />
                <button
                  type="button"
                  onClick={() => removeEquipmentRow(idx)}
                  className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>

          {error && <ErrorBanner error={error} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={create.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {create.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Crear Sala
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EditRoomDialog({
  open,
  onClose,
  room,
  roomTypes,
}: {
  open: boolean
  onClose: () => void
  room: Room
  roomTypes: RoomType[]
}) {
  const update = useUpdateRoom()
  const [form, setForm] = useState({
    name: room.name,
    building: room.building,
    floor: room.floor,
    capacity: String(room.capacity),
    room_type_id: String(room.room_type_id),
    description: room.description ?? '',
    is_active: room.is_active,
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.building.trim() || !form.floor.trim() || !form.capacity) {
      setError('Nombre, edificio, piso y capacidad son obligatorios.')
      return
    }
    setError(null)
    try {
      await update.mutateAsync({
        id: room.id,
        name: form.name.trim(),
        building: form.building.trim(),
        floor: form.floor.trim(),
        capacity: Number(form.capacity),
        room_type_id: Number(form.room_type_id),
        description: form.description.trim() || undefined,
        is_active: form.is_active,
      })
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo actualizar la sala.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Edit2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Editar Sala</h2>
              <p className="text-white/60 text-sm">{room.code}</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Tipo de Sala *</Label>
              <Select
                value={form.room_type_id}
                onValueChange={(v) => setForm((f) => ({ ...f, room_type_id: v }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roomTypes.map((rt) => (
                    <SelectItem key={rt.id} value={String(rt.id)}>
                      {rt.name} ({rt.code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Edificio *</Label>
              <Input
                value={form.building}
                onChange={(e) => setForm((f) => ({ ...f, building: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Piso *</Label>
              <Input
                value={form.floor}
                onChange={(e) => setForm((f) => ({ ...f, floor: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Capacidad *</Label>
              <Input
                type="number"
                min="1"
                value={form.capacity}
                onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-sm">Descripcion</Label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent resize-none"
              rows={2}
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="rounded border-gray-300"
            />
            <span className="text-sm text-gray-700">Sala activa</span>
          </label>

          {error && <ErrorBanner error={error} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={update.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {update.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Add Equipment to Room Dialog ─────────────────────────────────────────────

function AddRoomEquipmentDialog({
  open,
  onClose,
  roomId,
  equipmentList,
  existingEquipment,
}: {
  open: boolean
  onClose: () => void
  roomId: number
  equipmentList: EquipmentItem[]
  existingEquipment: RoomEquipment[]
}) {
  const addEquipment = useAddRoomEquipment()
  const [form, setForm] = useState({ equipment_id: '', quantity: '1', notes: '' })
  const [error, setError] = useState<string | null>(null)

  const existingIds = new Set(existingEquipment.map((eq) => eq.equipment_id))
  const available = equipmentList.filter((eq) => !existingIds.has(eq.id))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.equipment_id) {
      setError('Selecciona un equipo.')
      return
    }
    setError(null)
    try {
      await addEquipment.mutateAsync({
        roomId,
        equipment_id: Number(form.equipment_id),
        quantity: Number(form.quantity) || 1,
        notes: form.notes.trim() || undefined,
      })
      setForm({ equipment_id: '', quantity: '1', notes: '' })
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo agregar el equipo.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Wrench size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Agregar Equipo</h2>
              <p className="text-white/60 text-sm">Asignar equipamiento a la sala</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Equipo *</Label>
            <Select
              value={form.equipment_id}
              onValueChange={(v) => setForm((f) => ({ ...f, equipment_id: v }))}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Seleccionar equipo" />
              </SelectTrigger>
              <SelectContent>
                {available.map((eq) => (
                  <SelectItem key={eq.id} value={String(eq.id)}>
                    {eq.name} ({eq.code})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {available.length === 0 && (
              <p className="text-xs text-gray-400">No hay equipos disponibles para agregar.</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Cantidad</Label>
              <Input
                type="number"
                min="1"
                value={form.quantity}
                onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Notas</Label>
              <Input
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                placeholder="Opcional"
              />
            </div>
          </div>
          {error && <ErrorBanner error={error} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={addEquipment.isPending || available.length === 0}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {addEquipment.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Agregar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Room Detail (expanded) ───────────────────────────────────────────────────

function RoomDetail({
  roomId,
  onClose,
  roomTypes,
  equipmentList,
}: {
  roomId: number
  onClose: () => void
  roomTypes: RoomType[]
  equipmentList: EquipmentItem[]
}) {
  const { data: room, isLoading } = useRoom(roomId)
  const removeEquipment = useRemoveRoomEquipment()
  const deleteRoom = useDeleteRoom()
  const [editOpen, setEditOpen] = useState(false)
  const [addEquipOpen, setAddEquipOpen] = useState(false)
  const [removingId, setRemovingId] = useState<number | null>(null)

  const handleRemoveEquipment = async (equipmentId: number) => {
    if (!window.confirm('Quitar este equipo de la sala?')) return
    setRemovingId(equipmentId)
    try {
      await removeEquipment.mutateAsync({ roomId, equipmentId })
    } finally {
      setRemovingId(null)
    }
  }

  const handleDeactivate = async () => {
    if (!room) return
    if (!window.confirm(`Desactivar la sala "${room.name}"?`)) return
    await deleteRoom.mutateAsync(room.id)
    onClose()
  }

  if (isLoading) return <LoadingPage />
  if (!room) return null

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onClose}
              className="text-sm text-[#0066CC] hover:underline font-medium"
            >
              Salas
            </button>
            <span className="text-gray-300">/</span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>
                  {room.name}
                </h2>
                <span className="text-xs font-mono px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                  {room.code}
                </span>
                <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-medium">
                  {room.room_type_name}
                </span>
                {room.is_active ? (
                  <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">
                    Activa
                  </span>
                ) : (
                  <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
                    Inactiva
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-0.5">
                {room.building} - Piso {room.floor} | Capacidad: {room.capacity}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditOpen(true)} className="gap-1">
              <Edit2 size={14} />
              Editar
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDeactivate}
              disabled={deleteRoom.isPending}
              className="gap-1 text-red-600 border-red-200 hover:bg-red-50"
            >
              {deleteRoom.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Trash2 size={14} />
              )}
              Desactivar
            </Button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Edificio</p>
          <p className="text-sm font-bold mt-1" style={{ color: '#003366' }}>
            {room.building}
          </p>
        </div>
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Piso</p>
          <p className="text-sm font-bold mt-1" style={{ color: '#003366' }}>
            {room.floor}
          </p>
        </div>
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Capacidad</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#003366' }}>
            {room.capacity}
          </p>
        </div>
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Equipos</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#003366' }}>
            {room.equipment_items?.length ?? 0}
          </p>
        </div>
      </div>

      {/* Equipment list */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wrench size={16} className="text-gray-500" />
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
              Equipamiento de la Sala
            </h3>
          </div>
          <Button
            size="sm"
            onClick={() => setAddEquipOpen(true)}
            className="gap-1 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            <Plus size={14} />
            Agregar Equipo
          </Button>
        </div>
        <div className="p-5">
          {!room.equipment_items?.length ? (
            <div className="py-8 text-center">
              <Wrench size={32} className="mx-auto text-gray-300 mb-2" />
              <p className="text-sm text-gray-400">No hay equipamiento asignado a esta sala</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Codigo
                    </th>
                    <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Equipo
                    </th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Cantidad
                    </th>
                    <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Notas
                    </th>
                    <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {room.equipment_items.map((eq) => (
                    <tr key={eq.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-3 py-2 text-gray-600 font-mono text-xs">
                        {eq.equipment_code}
                      </td>
                      <td className="px-3 py-2 text-gray-800 font-medium">{eq.equipment_name}</td>
                      <td className="px-3 py-2 text-center text-gray-600">{eq.quantity}</td>
                      <td className="px-3 py-2 text-gray-500 text-xs">{eq.notes ?? '—'}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => handleRemoveEquipment(eq.equipment_id)}
                          disabled={removingId === eq.equipment_id}
                          className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                          title="Quitar"
                        >
                          {removingId === eq.equipment_id ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <Trash2 size={14} />
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {editOpen && (
        <EditRoomDialog
          open={editOpen}
          onClose={() => setEditOpen(false)}
          room={room}
          roomTypes={roomTypes}
        />
      )}
      {addEquipOpen && (
        <AddRoomEquipmentDialog
          open={addEquipOpen}
          onClose={() => setAddEquipOpen(false)}
          roomId={room.id}
          equipmentList={equipmentList}
          existingEquipment={room.equipment_items ?? []}
        />
      )}
    </div>
  )
}

// ─── Tab: Room Types ──────────────────────────────────────────────────────────

function RoomTypesTab() {
  const { data: roomTypes, isLoading } = useRoomTypes()
  const deleteRoomType = useDeleteRoomType()
  const [createOpen, setCreateOpen] = useState(false)
  const [editItem, setEditItem] = useState<RoomType | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const handleDelete = async (id: number) => {
    if (!window.confirm('Eliminar este tipo de sala?')) return
    setDeletingId(id)
    try {
      await deleteRoomType.mutateAsync(id)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
              Tipos de Sala
            </h3>
            {roomTypes && (
              <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full font-medium">
                {roomTypes.length}
              </span>
            )}
          </div>
          <Button
            size="sm"
            onClick={() => setCreateOpen(true)}
            className="gap-1 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            <Plus size={14} />
            Nuevo Tipo
          </Button>
        </div>

        <div className="p-5">
          {isLoading ? (
            <LoadingPage />
          ) : !roomTypes?.length ? (
            <div className="py-12 text-center">
              <Building2 size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">No hay tipos de sala registrados</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Codigo
                    </th>
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Nombre
                    </th>
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Descripcion
                    </th>
                    <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Salas
                    </th>
                    <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {roomTypes.map((rt) => (
                    <tr key={rt.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">{rt.code}</td>
                      <td className="px-4 py-3 font-medium text-gray-800">{rt.name}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {rt.description ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-medium">
                          {rt.room_count}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setEditItem(rt)}
                            className="p-1.5 rounded-md hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
                            title="Editar"
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            onClick={() => handleDelete(rt.id)}
                            disabled={deletingId === rt.id || rt.room_count > 0}
                            className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-30"
                            title={rt.room_count > 0 ? 'No se puede eliminar: tiene salas asignadas' : 'Eliminar'}
                          >
                            {deletingId === rt.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <Trash2 size={14} />
                            )}
                          </button>
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

      {createOpen && (
        <CreateRoomTypeDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      )}
      {editItem && (
        <EditRoomTypeDialog
          open={!!editItem}
          onClose={() => setEditItem(null)}
          roomType={editItem}
        />
      )}
    </div>
  )
}

// ─── Tab: Equipment ───────────────────────────────────────────────────────────

function EquipmentTab() {
  const { data: equipment, isLoading } = useEquipment()
  const deleteEquipment = useDeleteEquipment()
  const [createOpen, setCreateOpen] = useState(false)
  const [editItem, setEditItem] = useState<EquipmentItem | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const handleDelete = async (id: number) => {
    if (!window.confirm('Eliminar este equipo?')) return
    setDeletingId(id)
    try {
      await deleteEquipment.mutateAsync(id)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
              Equipamiento
            </h3>
            {equipment && (
              <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full font-medium">
                {equipment.length}
              </span>
            )}
          </div>
          <Button
            size="sm"
            onClick={() => setCreateOpen(true)}
            className="gap-1 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            <Plus size={14} />
            Nuevo Equipo
          </Button>
        </div>

        <div className="p-5">
          {isLoading ? (
            <LoadingPage />
          ) : !equipment?.length ? (
            <div className="py-12 text-center">
              <Monitor size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">No hay equipamiento registrado</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Codigo
                    </th>
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Nombre
                    </th>
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Descripcion
                    </th>
                    <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {equipment.map((eq) => (
                    <tr key={eq.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">{eq.code}</td>
                      <td className="px-4 py-3 font-medium text-gray-800">{eq.name}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {eq.description ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setEditItem(eq)}
                            className="p-1.5 rounded-md hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
                            title="Editar"
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            onClick={() => handleDelete(eq.id)}
                            disabled={deletingId === eq.id}
                            className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                            title="Eliminar"
                          >
                            {deletingId === eq.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <Trash2 size={14} />
                            )}
                          </button>
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

      {createOpen && (
        <CreateEquipmentDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      )}
      {editItem && (
        <EditEquipmentDialog
          open={!!editItem}
          onClose={() => setEditItem(null)}
          equipment={editItem}
        />
      )}
    </div>
  )
}

// ─── Tab: Rooms ───────────────────────────────────────────────────────────────

function RoomsTab() {
  const { data: roomTypes } = useRoomTypes()
  const { data: equipmentList } = useEquipment()

  // Filters
  const [filterBuilding, setFilterBuilding] = useState<string>('')
  const [filterFloor, setFilterFloor] = useState<string>('')
  const [filterType, setFilterType] = useState<string>('')
  const [filterActive, setFilterActive] = useState(true)

  const params = useMemo(
    () => ({
      building: filterBuilding || undefined,
      floor: filterFloor || undefined,
      room_type_id: filterType ? Number(filterType) : undefined,
      active_only: filterActive || undefined,
    }),
    [filterBuilding, filterFloor, filterType, filterActive],
  )

  const { data: rooms, isLoading } = useRooms(params)
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null)

  // Extract unique buildings and floors for filter dropdowns
  const allRooms = useRooms()
  const buildings = useMemo(() => {
    const set = new Set<string>()
    allRooms.data?.forEach((r) => set.add(r.building))
    return Array.from(set).sort()
  }, [allRooms.data])

  const floors = useMemo(() => {
    const set = new Set<string>()
    allRooms.data?.forEach((r) => set.add(r.floor))
    return Array.from(set).sort()
  }, [allRooms.data])

  // Room detail view
  if (selectedRoomId !== null) {
    return (
      <RoomDetail
        roomId={selectedRoomId}
        onClose={() => setSelectedRoomId(null)}
        roomTypes={roomTypes ?? []}
        equipmentList={equipmentList ?? []}
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="card-3d-static p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500 whitespace-nowrap">Edificio</Label>
            <Select value={filterBuilding} onValueChange={setFilterBuilding}>
              <SelectTrigger className="w-36 h-8 text-xs">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Todos</SelectItem>
                {buildings.map((b) => (
                  <SelectItem key={b} value={b}>
                    {b}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500 whitespace-nowrap">Piso</Label>
            <Select value={filterFloor} onValueChange={setFilterFloor}>
              <SelectTrigger className="w-28 h-8 text-xs">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Todos</SelectItem>
                {floors.map((f) => (
                  <SelectItem key={f} value={f}>
                    {f}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500 whitespace-nowrap">Tipo</Label>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-40 h-8 text-xs">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Todos</SelectItem>
                {(roomTypes ?? []).map((rt) => (
                  <SelectItem key={rt.id} value={String(rt.id)}>
                    {rt.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={filterActive}
              onChange={(e) => setFilterActive(e.target.checked)}
              className="rounded border-gray-300"
            />
            <span className="text-xs text-gray-600">Solo activas</span>
          </label>
        </div>
      </div>

      {/* Room list */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
              Salas Registradas
            </h3>
            {rooms && (
              <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full font-medium">
                {rooms.length}
              </span>
            )}
          </div>
          <Button
            size="sm"
            onClick={() => setCreateOpen(true)}
            disabled={!roomTypes?.length}
            className="gap-1 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            <Plus size={14} />
            Nueva Sala
          </Button>
        </div>

        <div className="p-5">
          {isLoading ? (
            <LoadingPage />
          ) : !rooms?.length ? (
            <div className="py-12 text-center">
              <Building2 size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">No hay salas registradas</p>
              <p className="text-sm text-gray-400 mt-1">
                {!roomTypes?.length
                  ? 'Primero registra al menos un tipo de sala en la pestana "Tipos de Sala".'
                  : 'Crea una nueva sala para comenzar.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {rooms.map((room) => (
                <RoomCard key={room.id} room={room} onSelect={setSelectedRoomId} />
              ))}
            </div>
          )}
        </div>
      </div>

      {createOpen && roomTypes && (
        <CreateRoomDialog
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          roomTypes={roomTypes}
          equipmentList={equipmentList ?? []}
        />
      )}
    </div>
  )
}

// ─── Room Card ────────────────────────────────────────────────────────────────

function RoomCard({ room, onSelect }: { room: Room; onSelect: (id: number) => void }) {
  return (
    <button
      onClick={() => onSelect(room.id)}
      className={`card-3d-static p-5 text-left hover:shadow-md transition-shadow w-full ${
        !room.is_active ? 'opacity-60' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: room.is_active ? '#003366' : '#9ca3af' }}
          >
            <Building2 size={20} className="text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-800">{room.name}</p>
            <p className="text-xs font-mono text-gray-500">{room.code}</p>
          </div>
        </div>
        <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-medium">
          {room.room_type_name}
        </span>
      </div>
      <div className="flex items-center gap-4 mt-4">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Building2 size={14} />
          <span>
            {room.building} - P{room.floor}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Users size={14} />
          <span>Cap. {room.capacity}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Wrench size={14} />
          <span>
            {room.equipment_items?.length ?? 0} equipo
            {(room.equipment_items?.length ?? 0) !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
      <div className="mt-3">
        {room.is_active ? (
          <span className="text-[10px] px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">
            Activa
          </span>
        ) : (
          <span className="text-[10px] px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
            Inactiva
          </span>
        )}
      </div>
    </button>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function RoomsPage() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ backgroundColor: '#003366' }}
        >
          <Building2 size={22} className="text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: '#003366' }}>
            Gestion de Salas
          </h1>
          <p className="text-sm text-gray-500">Salas, tipos de sala y equipamiento</p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="rooms">
        <TabsList className="bg-gray-100 p-1 rounded-lg">
          <TabsTrigger value="rooms" className="gap-1.5 px-4">
            <Building2 size={14} />
            Salas
          </TabsTrigger>
          <TabsTrigger value="room-types" className="gap-1.5 px-4">
            <Monitor size={14} />
            Tipos de Sala
          </TabsTrigger>
          <TabsTrigger value="equipment" className="gap-1.5 px-4">
            <Wrench size={14} />
            Equipamiento
          </TabsTrigger>
        </TabsList>

        <TabsContent value="rooms" className="mt-4">
          <RoomsTab />
        </TabsContent>
        <TabsContent value="room-types" className="mt-4">
          <RoomTypesTab />
        </TabsContent>
        <TabsContent value="equipment" className="mt-4">
          <EquipmentTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
