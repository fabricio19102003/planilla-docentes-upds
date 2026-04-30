import { type FormEvent, useMemo, useState } from 'react'
import { Calendar, Plus, ArrowUpRight, Loader2 } from 'lucide-react'
import { useAcademicPeriods, useCreateAcademicPeriod, useActivateAcademicPeriod, useRoomTypes, useCreateRoomType, useEquipment, useCreateEquipment, useRooms, useCreateRoom } from '@/api/hooks/useScheduling'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('es-BO', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  })
}

function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-9 h-9 rounded-xl bg-slate-900/10 text-slate-900 flex items-center justify-center">
          <Calendar size={18} />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          <p className="text-sm text-slate-500">{description}</p>
        </div>
      </div>
    </div>
  )
}

function InputRow({ label, value, onChange, type = 'text', placeholder = '' }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs font-semibold text-slate-600">{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  )
}

export function SchedulingPage() {
  const { data: periods, isLoading: loadingPeriods } = useAcademicPeriods()
  const createPeriod = useCreateAcademicPeriod()
  const activatePeriod = useActivateAcademicPeriod()
  const { data: roomTypes, isLoading: loadingRoomTypes } = useRoomTypes()
  const createRoomType = useCreateRoomType()
  const { data: equipment, isLoading: loadingEquipment } = useEquipment()
  const createEquipment = useCreateEquipment()
  const { data: rooms, isLoading: loadingRooms } = useRooms()
  const createRoom = useCreateRoom()

  const roomTypeMap = useMemo(() => {
    return new Map<number, string>(roomTypes?.map((type) => [type.id, type.name]) ?? [])
  }, [roomTypes])

  const [periodForm, setPeriodForm] = useState({
    code: '',
    name: '',
    start_date: '',
    end_date: '',
    status: 'planning',
    is_active: false,
  })
  const [periodError, setPeriodError] = useState<string | null>(null)

  const [roomTypeForm, setRoomTypeForm] = useState({ code: '', name: '', description: '' })
  const [roomTypeError, setRoomTypeError] = useState<string | null>(null)

  const [equipmentForm, setEquipmentForm] = useState({ code: '', name: '', description: '' })
  const [equipmentError, setEquipmentError] = useState<string | null>(null)

  const [roomForm, setRoomForm] = useState({ code: '', name: '', building: '', floor: '', capacity: '30', room_type_id: '', description: '' })
  const [roomError, setRoomError] = useState<string | null>(null)

  const activePeriod = useMemo(() => periods?.find((period) => period.is_active), [periods])

  const handleCreatePeriod = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPeriodError(null)
    if (!periodForm.code || !periodForm.name || !periodForm.start_date || !periodForm.end_date) {
      setPeriodError('Completa todos los campos obligatorios')
      return
    }

    try {
      await createPeriod.mutateAsync({
        code: periodForm.code.trim(),
        name: periodForm.name.trim(),
        start_date: periodForm.start_date,
        end_date: periodForm.end_date,
        status: periodForm.status,
        is_active: periodForm.is_active,
      })
      setPeriodForm({ code: '', name: '', start_date: '', end_date: '', status: 'planning', is_active: false })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      setPeriodError(err?.response?.data?.detail ?? 'Error al crear el período académico')
    }
  }

  const handleCreateRoomType = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setRoomTypeError(null)
    if (!roomTypeForm.code || !roomTypeForm.name) {
      setRoomTypeError('Código y nombre son obligatorios')
      return
    }

    try {
      await createRoomType.mutateAsync({
        code: roomTypeForm.code.trim(),
        name: roomTypeForm.name.trim(),
        description: roomTypeForm.description.trim() || undefined,
      })
      setRoomTypeForm({ code: '', name: '', description: '' })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      setRoomTypeError(err?.response?.data?.detail ?? 'Error al crear el tipo de sala')
    }
  }

  const handleCreateEquipment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setEquipmentError(null)
    if (!equipmentForm.code || !equipmentForm.name) {
      setEquipmentError('Código y nombre son obligatorios')
      return
    }

    try {
      await createEquipment.mutateAsync({
        code: equipmentForm.code.trim(),
        name: equipmentForm.name.trim(),
        description: equipmentForm.description.trim() || undefined,
      })
      setEquipmentForm({ code: '', name: '', description: '' })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      setEquipmentError(err?.response?.data?.detail ?? 'Error al crear el equipo')
    }
  }

  const handleCreateRoom = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setRoomError(null)
    if (!roomForm.code || !roomForm.name || !roomForm.building || !roomForm.floor || !roomForm.capacity || !roomForm.room_type_id) {
      setRoomError('Completa todos los campos obligatorios')
      return
    }
    if (Number(roomForm.capacity) <= 0) {
      setRoomError('La capacidad debe ser un número mayor a 0')
      return
    }

    try {
      await createRoom.mutateAsync({
        code: roomForm.code.trim(),
        name: roomForm.name.trim(),
        building: roomForm.building.trim(),
        floor: roomForm.floor.trim(),
        capacity: Number(roomForm.capacity),
        room_type_id: Number(roomForm.room_type_id),
        description: roomForm.description.trim() || undefined,
      })
      setRoomForm({ code: '', name: '', building: '', floor: '', capacity: '30', room_type_id: '', description: '' })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      setRoomError(err?.response?.data?.detail ?? 'Error al crear la sala')
    }
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Configuración de Horario</h1>
          <p className="text-sm text-slate-500 mt-1">
            Administra períodos académicos activos y la infraestructura de aulas.
          </p>
        </div>
        {activePeriod ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 shadow-sm">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Período activo</p>
            <p className="text-lg font-semibold text-slate-900">{activePeriod.name}</p>
            <p className="text-sm text-slate-600">
              {activePeriod.code} · {formatDate(activePeriod.start_date)} — {formatDate(activePeriod.end_date)}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 shadow-sm">
            <p className="text-xs uppercase tracking-[0.18em] text-amber-700">Sin período activo</p>
            <p className="text-sm text-amber-900">
              Configurá un período académico y activalo para que los cálculos usen el período actual.
            </p>
          </div>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="space-y-5">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <SectionHeader
              title="Períodos Académicos"
              description="Crea y activa períodos académicos para el módulo de horarios."
            />

            <form onSubmit={handleCreatePeriod} className="grid gap-4 sm:grid-cols-2">
              <InputRow label="Código" value={periodForm.code} onChange={(value) => setPeriodForm((prev) => ({ ...prev, code: value }))} placeholder="I/2026" />
              <InputRow label="Nombre" value={periodForm.name} onChange={(value) => setPeriodForm((prev) => ({ ...prev, name: value }))} placeholder="Primer Semestre 2026" />
              <InputRow label="Inicio" value={periodForm.start_date} onChange={(value) => setPeriodForm((prev) => ({ ...prev, start_date: value }))} type="date" />
              <InputRow label="Fin" value={periodForm.end_date} onChange={(value) => setPeriodForm((prev) => ({ ...prev, end_date: value }))} type="date" />
              <div className="space-y-1">
                <Label className="text-xs font-semibold text-slate-600">Estado</Label>
                <select
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none"
                  value={periodForm.status}
                  onChange={(e) => setPeriodForm((prev) => ({ ...prev, status: e.target.value }))}
                >
                  <option value="planning">Planning</option>
                  <option value="active">Active</option>
                  <option value="closed">Closed</option>
                </select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs font-semibold text-slate-600">Activar al crear</Label>
                <div className="flex items-center gap-2">
                  <input
                    id="activate-period"
                    type="checkbox"
                    checked={periodForm.is_active}
                    onChange={(e) => setPeriodForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                    className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                  />
                  <label htmlFor="activate-period" className="text-sm text-slate-600">
                    Activar este período
                  </label>
                </div>
              </div>
              <div className="sm:col-span-2">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  {periodError ? <p className="text-sm text-rose-600">{periodError}</p> : null}
                  <Button type="submit" disabled={createPeriod.status === 'pending'} className="ml-auto">
                    {createPeriod.status === 'pending' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus size={16} />}
                    Crear Período
                  </Button>
                </div>
              </div>
            </form>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Lista de Períodos</h3>
                <p className="text-sm text-slate-500">Activa un período para cambiar el contexto actual.</p>
              </div>
              <Badge variant="secondary">{periods?.length ?? 0} períodos</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm text-left text-slate-700 border-collapse">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="px-3 py-3 font-semibold">Código</th>
                    <th className="px-3 py-3 font-semibold">Nombre</th>
                    <th className="px-3 py-3 font-semibold">Fechas</th>
                    <th className="px-3 py-3 font-semibold">Estado</th>
                    <th className="px-3 py-3 font-semibold">Activo</th>
                    <th className="px-3 py-3 font-semibold">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingPeriods ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-slate-500">
                        Cargando períodos...
                      </td>
                    </tr>
                  ) : periods?.length ? (
                    periods.map((period) => (
                      <tr key={period.id} className="border-b border-slate-100 hover:bg-slate-50/80">
                        <td className="px-3 py-3 font-medium text-slate-900">{period.code}</td>
                        <td className="px-3 py-3">{period.name}</td>
                        <td className="px-3 py-3">{formatDate(period.start_date)} – {formatDate(period.end_date)}</td>
                        <td className="px-3 py-3 capitalize">{period.status}</td>
                        <td className="px-3 py-3">{period.is_active ? <Badge variant="secondary">Activo</Badge> : '—'}</td>
                        <td className="px-3 py-3">
                          {!period.is_active ? (
                            <Button
                              size="sm"
                              onClick={() => activatePeriod.mutateAsync(period.id)}
                              disabled={activatePeriod.status === 'pending'}
                              className="gap-2"
                            >
                              <ArrowUpRight size={14} /> Activar
                            </Button>
                          ) : (
                            <span className="text-xs text-slate-500">Actual</span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-slate-500">
                        No hay períodos configurados.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <SectionHeader title="Tipos de Aula" description="Define tipos de sala para clasificar la infraestructura." />
            <form onSubmit={handleCreateRoomType} className="space-y-4">
              <InputRow label="Código" value={roomTypeForm.code} onChange={(value) => setRoomTypeForm((prev) => ({ ...prev, code: value }))} placeholder="AULA" />
              <InputRow label="Nombre" value={roomTypeForm.name} onChange={(value) => setRoomTypeForm((prev) => ({ ...prev, name: value }))} placeholder="Aula Común" />
              <InputRow label="Descripción" value={roomTypeForm.description} onChange={(value) => setRoomTypeForm((prev) => ({ ...prev, description: value }))} placeholder="Opcional" />
              {roomTypeError ? <p className="text-sm text-rose-600">{roomTypeError}</p> : null}
              <Button type="submit" disabled={createRoomType.status === 'pending'} className="w-full">
                {createRoomType.status === 'pending' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus size={16} />}
                Agregar Tipo
              </Button>
            </form>
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-sm text-left text-slate-700">
                <thead className="border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-3 font-semibold">Código</th>
                    <th className="px-3 py-3 font-semibold">Nombre</th>
                    <th className="px-3 py-3 font-semibold">Descripción</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingRoomTypes ? (
                    <tr><td colSpan={3} className="px-3 py-6 text-center text-slate-500">Cargando tipos...</td></tr>
                  ) : roomTypes?.length ? (
                    roomTypes.map((type) => (
                      <tr key={type.id} className="border-b border-slate-100 hover:bg-slate-50/80">
                        <td className="px-3 py-3 font-medium text-slate-900">{type.code}</td>
                        <td className="px-3 py-3">{type.name}</td>
                        <td className="px-3 py-3">{type.description ?? '—'}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={3} className="px-3 py-6 text-center text-slate-500">No hay tipos configurados.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <SectionHeader title="Equipamiento" description="Registra equipos disponibles para las salas." />
            <form onSubmit={handleCreateEquipment} className="space-y-4">
              <InputRow label="Código" value={equipmentForm.code} onChange={(value) => setEquipmentForm((prev) => ({ ...prev, code: value }))} placeholder="PROY" />
              <InputRow label="Nombre" value={equipmentForm.name} onChange={(value) => setEquipmentForm((prev) => ({ ...prev, name: value }))} placeholder="Proyector" />
              <InputRow label="Descripción" value={equipmentForm.description} onChange={(value) => setEquipmentForm((prev) => ({ ...prev, description: value }))} placeholder="Opcional" />
              {equipmentError ? <p className="text-sm text-rose-600">{equipmentError}</p> : null}
              <Button type="submit" disabled={createEquipment.status === 'pending'} className="w-full">
                {createEquipment.status === 'pending' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus size={16} />}
                Agregar Equipo
              </Button>
            </form>
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-sm text-left text-slate-700">
                <thead className="border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-3 font-semibold">Código</th>
                    <th className="px-3 py-3 font-semibold">Nombre</th>
                    <th className="px-3 py-3 font-semibold">Descripción</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingEquipment ? (
                    <tr><td colSpan={3} className="px-3 py-6 text-center text-slate-500">Cargando equipamiento...</td></tr>
                  ) : equipment?.length ? (
                    equipment.map((item) => (
                      <tr key={item.id} className="border-b border-slate-100 hover:bg-slate-50/80">
                        <td className="px-3 py-3 font-medium text-slate-900">{item.code}</td>
                        <td className="px-3 py-3">{item.name}</td>
                        <td className="px-3 py-3">{item.description ?? '—'}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={3} className="px-3 py-6 text-center text-slate-500">No hay equipos registrados.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <SectionHeader title="Salas" description="Registra salas físicas y asócialas a un tipo de aula." />
            <form onSubmit={handleCreateRoom} className="grid gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <InputRow label="Código" value={roomForm.code} onChange={(value) => setRoomForm((prev) => ({ ...prev, code: value }))} placeholder="A-101" />
                <InputRow label="Nombre" value={roomForm.name} onChange={(value) => setRoomForm((prev) => ({ ...prev, name: value }))} placeholder="Aula 101" />
                <InputRow label="Edificio" value={roomForm.building} onChange={(value) => setRoomForm((prev) => ({ ...prev, building: value }))} placeholder="Edificio Central" />
                <InputRow label="Piso" value={roomForm.floor} onChange={(value) => setRoomForm((prev) => ({ ...prev, floor: value }))} placeholder="1" />
                <InputRow label="Capacidad" value={roomForm.capacity} onChange={(value) => setRoomForm((prev) => ({ ...prev, capacity: value }))} type="number" placeholder="30" />
                <div className="space-y-1">
                  <Label className="text-xs font-semibold text-slate-600">Tipo de Sala</Label>
                  <select
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none"
                    value={roomForm.room_type_id}
                    onChange={(e) => setRoomForm((prev) => ({ ...prev, room_type_id: e.target.value }))}
                  >
                    <option value="">Seleccionar...</option>
                    {roomTypes?.map((type) => (
                      <option key={type.id} value={type.id}>{type.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <InputRow label="Descripción" value={roomForm.description} onChange={(value) => setRoomForm((prev) => ({ ...prev, description: value }))} placeholder="Opcional" />
              {roomError ? <p className="text-sm text-rose-600">{roomError}</p> : null}
              <Button type="submit" disabled={createRoom.status === 'pending'} className="w-full">
                {createRoom.status === 'pending' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus size={16} />}
                Crear Sala
              </Button>
            </form>
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-sm text-left text-slate-700">
                <thead className="border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-3 font-semibold">Código</th>
                    <th className="px-3 py-3 font-semibold">Nombre</th>
                    <th className="px-3 py-3 font-semibold">Tipo</th>
                    <th className="px-3 py-3 font-semibold">Edificio</th>
                    <th className="px-3 py-3 font-semibold">Capacidad</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingRooms ? (
                    <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-500">Cargando salas...</td></tr>
                  ) : rooms?.length ? (
                    rooms.map((room) => (
                      <tr key={room.id} className="border-b border-slate-100 hover:bg-slate-50/80">
                        <td className="px-3 py-3 font-medium text-slate-900">{room.code}</td>
                        <td className="px-3 py-3">{room.name}</td>
                        <td className="px-3 py-3">{roomTypeMap.get(room.room_type_id) ?? `Tipo ${room.room_type_id}`}</td>
                        <td className="px-3 py-3">{room.building}</td>
                        <td className="px-3 py-3">{room.capacity}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-500">No hay salas registradas.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
