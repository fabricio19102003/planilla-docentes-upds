import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CheckCircle2, CircleHelp, Clock, FileText, DoorOpen, FileUp, Flag, Layers, Plus, UserCheck, X } from 'lucide-react'

import { useDesignationList } from '@/api/hooks/useDesignationAdmin'
import type { DesignationAdminFilters, DesignationAdminItem, DesignationAdminMutation } from '@/api/types'
import { DesignationFormDialog } from '@/components/designations/DesignationFormDialog'
import { DesignationImportWizard } from '@/components/designations/DesignationImportWizard'
import { DesignationRoomImportWizard } from '@/components/designations/DesignationRoomImportWizard'
import { DesignationTable } from '@/components/designations/DesignationListView'
import { DesignationMobileCards } from '@/components/designations/DesignationMobileCards'
import { DeleteDesignationDialog, FinalizeDesignationDialog } from '@/components/designations/DesignationLifecycleDialogs'
import { CountUp } from '@/components/shared/CountUp'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverPopup, PopoverTrigger } from '@/components/ui/popover'
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control'
import { useIsMobile } from '@/hooks/use-media-query'
import {
  SEMESTER_OPTIONS,
  emptyDesignationForm,
  formatDate,
  itemToForm,
  regenerateText,
  type DesignationForm,
} from '@/lib/designationAdminState'
import {
  activeFilterCount,
  designationKpis,
  displayName,
  filterByStatus,
  statusFilterCounts,
  type DesignationStatusFilter,
} from '@/lib/designationListView'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:h-8'

const STATUS_TABS: { value: DesignationStatusFilter; label: string }[] = [
  { value: 'all', label: 'Todas' },
  { value: 'active', label: 'Vigentes' },
  { value: 'finalized', label: 'Finalizadas' },
]

const formatHoursCount = (value: number) => value.toLocaleString('es-BO', { maximumFractionDigits: 1 })

type Editor = { item: DesignationAdminItem | null; form: DesignationForm }
type Notice = { title: string; details: string[] }

function HowItWorks() {
  return (
    <Popover>
      <PopoverTrigger render={<Button variant="ghost" />}>
        <CircleHelp aria-hidden="true" />¿Cómo funciona esta pantalla?
      </PopoverTrigger>
      <PopoverPopup align="end" className="max-w-md">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li><strong className="text-foreground">Nueva designación</strong>: asigná una materia a un docente con su horario y sus horas.</li>
          <li><strong className="text-foreground">Importar archivo</strong>: cargá el Excel del semestre; antes de guardar ves qué filas son nuevas y cuáles cambian.</li>
          <li><strong className="text-foreground">Importar aulas</strong>: cargá el Excel para asignar el aula de cada clase de teoría; solo sirve para marcar el aula como ocupada.</li>
          <li><strong className="text-foreground">Editar</strong>: corregí materia, horario, horas o fechas mientras ese mes no esté pagado.</li>
          <li><strong className="text-foreground">Finalizar</strong>: el docente deja la materia; se le paga hasta el día que elijas y queda en el historial.</li>
          <li><strong className="text-foreground">Eliminar</strong>: solo para designaciones cargadas por error, que nadie usó todavía.</li>
          <li>Si una planilla ya está <strong className="text-foreground">aprobada</strong> o la facturación <strong className="text-foreground">publicada</strong>, los datos de ese mes no se pueden cambiar.</li>
        </ul>
      </PopoverPopup>
    </Popover>
  )
}

export function DesignationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const teacherCi = searchParams.get('teacher') ?? ''
  const [period, setPeriod] = useState('')
  const [search, setSearch] = useState('')
  const [semester, setSemester] = useState('')
  const [type, setType] = useState<'' | 'regular' | 'practice'>('')
  const [status, setStatus] = useState<'all' | 'active' | 'finalized'>('all')
  const [editor, setEditor] = useState<Editor | null>(null)
  const [finalizing, setFinalizing] = useState<DesignationAdminItem | null>(null)
  const [deleting, setDeleting] = useState<DesignationAdminItem | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [roomsOpen, setRoomsOpen] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)

  const isMobile = useIsMobile()

  // The list always asks for every status: the quick filter narrows it here so the counts and KPIs stay complete.
  const filters: DesignationAdminFilters = {
    academic_period: period || undefined,
    q: search.trim() || undefined,
    semester: semester || undefined,
    designation_type: type || undefined,
    status: 'all',
    teacher_ci: teacherCi || undefined,
  }
  const list = useDesignationList(filters)
  const allItems = useMemo(() => list.data?.items ?? [], [list.data])
  const items = useMemo(() => filterByStatus(allItems, status), [allItems, status])
  const kpis = useMemo(() => designationKpis(allItems), [allItems])
  const counts = useMemo(() => statusFilterCounts(allItems), [allItems])
  const currentPeriod = list.data?.academic_period ?? period
  const subjects = useMemo(() => [...new Set(allItems.map((item) => item.subject))].sort(), [allItems])
  const teacherRaw = teacherCi ? allItems.find((item) => item.teacher_ci === teacherCi)?.teacher_name : undefined
  const teacherName = teacherCi ? (teacherRaw ? displayName(teacherRaw) : teacherCi) : ''
  const filterCount = activeFilterCount({ search, period, semester, type, status }, teacherCi)
  const loading = list.isLoading
  const clearFilters = () => {
    setSearch(''); setPeriod(''); setSemester(''); setType(''); setStatus('all')
    if (teacherCi) setSearchParams({})
  }

  const openCreate = (form?: Partial<DesignationForm>) =>
    setEditor({ item: null, form: { ...emptyDesignationForm(currentPeriod), teacherCi, ...form } })
  const openEdit = (item: DesignationAdminItem) => setEditor({ item, form: itemToForm(item) })
  const finalizeInstead = (item: DesignationAdminItem) => { setEditor(null); setDeleting(null); setFinalizing(item) }

  const saved = (result: DesignationAdminMutation, title: string) => {
    setNotice({ title, details: [...result.warnings, regenerateText(result.regenerate)].filter(Boolean) })
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Designaciones"
        description="Las materias asignadas a cada docente: horario, horas que se pagan y fechas de contrato."
        actions={(
          <>
            <HowItWorks />
            <Button variant="outline" onClick={() => setImportOpen(true)}><FileUp aria-hidden="true" />Importar archivo</Button>
            <Button variant="outline" onClick={() => setRoomsOpen(true)}><DoorOpen aria-hidden="true" />Importar aulas</Button>
            <Button onClick={() => openCreate()}><Plus aria-hidden="true" />Nueva designación</Button>
          </>
        )}
      />

      {notice && (
        <Alert variant="success" role="status">
          <CheckCircle2 aria-hidden="true" />
          <AlertTitle className="flex items-center justify-between gap-2">
            {notice.title}
            <Button type="button" size="icon" variant="ghost" aria-label="Cerrar aviso" onClick={() => setNotice(null)}><X aria-hidden="true" /></Button>
          </AlertTitle>
          {notice.details.length > 0 && (
            <AlertDescription><ul className="list-disc pl-4">{notice.details.map((text) => <li key={text}>{text}</li>)}</ul></AlertDescription>
          )}
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        <StatCard icon={Layers} tone="primary" title="Designaciones" value={loading ? '—' : <CountUp value={kpis.total} />} hint="Con los filtros actuales" />
        <StatCard icon={UserCheck} tone="success" title="Vigentes" value={loading ? '—' : <CountUp value={kpis.active} />} hint="Dando clases hoy" />
        <StatCard icon={Flag} tone="warning" title="Finalizadas" value={loading ? '—' : <CountUp value={kpis.finalized} />} hint="Ya en el historial" />
        <StatCard icon={Clock} tone="violet" title="Horas al mes" value={loading ? '—' : <CountUp value={kpis.monthlyHours} format={formatHoursCount} />} hint="Suma de las horas mensuales" />
        <StatCard icon={FileText} tone="info" title="Con contrato" value={loading ? '—' : <CountUp value={kpis.withContract} />} hint="Contrato ya emitido" />
      </div>

      <div className="flex flex-col gap-3 rounded-lg border bg-card p-3 lg:flex-row lg:flex-wrap lg:items-center" role="search">
        <div className="min-w-0 flex-1 lg:min-w-60">
          <Label htmlFor="designations-search" className="sr-only">Buscar docente o materia</Label>
          <Input id="designations-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar docente o materia: Pérez, Anatomía…" />
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:flex lg:items-center">
          <div>
            <Label htmlFor="designations-period" className="sr-only">Período</Label>
            <select id="designations-period" className={selectClass} value={currentPeriod} onChange={(event) => setPeriod(event.target.value)}>
              {(list.data?.periods ?? (currentPeriod ? [currentPeriod] : [])).map((value) => <option key={value} value={value}>Período {value}</option>)}
            </select>
          </div>
          <div>
            <Label htmlFor="designations-semester" className="sr-only">Semestre</Label>
            <select id="designations-semester" className={selectClass} value={semester} onChange={(event) => setSemester(event.target.value)}>
              <option value="">Todos los semestres</option>
              {SEMESTER_OPTIONS.map((value) => <option key={value} value={value}>{value.charAt(0) + value.slice(1).toLowerCase()}</option>)}
            </select>
          </div>
          <div>
            <Label htmlFor="designations-type" className="sr-only">Tipo</Label>
            <select id="designations-type" className={selectClass} value={type} onChange={(event) => setType(event.target.value as typeof type)}>
              <option value="">Teoría y práctica</option>
              <option value="regular">Teoría</option>
              <option value="practice">Práctica</option>
            </select>
          </div>
        </div>
        <SegmentedControl aria-label="Estado de la designación" className="max-w-full overflow-x-auto">
          {STATUS_TABS.map((tab) => (
            <SegmentedControlItem
              key={tab.value}
              aria-pressed={status === tab.value}
              data-pressed={status === tab.value ? '' : undefined}
              onClick={() => setStatus(tab.value)}
            >
              {tab.label}
              <span className="tabular-nums text-xs text-muted-foreground">{loading ? '' : counts[tab.value]}</span>
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
        {filterCount > 0 && (
          <Button type="button" variant="ghost" size="sm" onClick={clearFilters}>
            <X aria-hidden="true" />Limpiar filtros ({filterCount})
          </Button>
        )}
      </div>

      {teacherCi && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Badge variant="outline" className="gap-1">
            Docente: {teacherName}
            <button type="button" aria-label="Quitar filtro de docente" onClick={() => setSearchParams({})}><X className="size-3" aria-hidden="true" /></button>
          </Badge>
        </div>
      )}

      {list.isError && (
        <Alert variant="error" role="alert">
          <AlertTitle>No se pudieron cargar las designaciones.</AlertTitle>
          <AlertDescription><Button size="sm" variant="outline" onClick={() => void list.refetch()}>Reintentar</Button></AlertDescription>
        </Alert>
      )}

      {!loading && !list.isError && items.length === 0 ? (
        <EmptyState
          illustration="empty-search"
          title={`No hay designaciones${currentPeriod ? ` en ${currentPeriod}` : ''} con estos filtros`}
          description="Creá una designación o importá el Excel del semestre."
          action={filterCount > 0 ? <Button variant="outline" onClick={clearFilters}><X aria-hidden="true" />Limpiar filtros</Button> : undefined}
        />
      ) : isMobile ? (
        <DesignationMobileCards items={items} loading={loading} onEdit={openEdit} onFinalize={setFinalizing} onDelete={setDeleting} />
      ) : (
        <DesignationTable items={items} loading={loading} onEdit={openEdit} onFinalize={setFinalizing} onDelete={setDeleting} />
      )}

      {editor && (
        <DesignationFormDialog
          open
          onOpenChange={(open) => { if (!open) setEditor(null) }}
          item={editor.item}
          initialForm={editor.form}
          subjects={subjects}
          onSaved={(result, mode) => { setEditor(null); saved(result, mode === 'create' ? 'Designación creada.' : 'Cambios guardados.') }}
          onFinalizeInstead={finalizeInstead}
        />
      )}
      {finalizing && (
        <FinalizeDesignationDialog
          item={finalizing}
          onClose={() => setFinalizing(null)}
          onDone={(result) => { setFinalizing(null); saved(result, `Designación finalizada el ${formatDate(result.contract_end_date)}.`) }}
        />
      )}
      {deleting && (
        <DeleteDesignationDialog
          item={deleting}
          onClose={() => setDeleting(null)}
          onDone={() => { setDeleting(null); setNotice({ title: 'Designación eliminada.', details: [] }) }}
          onFinalizeInstead={finalizeInstead}
        />
      )}
      <Dialog open={roomsOpen} onOpenChange={setRoomsOpen}>
        <DialogPopup className="sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>Importar aulas</DialogTitle>
            <DialogDescription>Cargá el Excel de designaciones para asignar el aula de cada clase de teoría. Antes de aplicar ves qué cambia.</DialogDescription>
          </DialogHeader>
          <DialogPanel>
            <DesignationRoomImportWizard onApplied={() => setRoomsOpen(false)} />
          </DialogPanel>
        </DialogPopup>
      </Dialog>
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogPopup className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Importar designaciones</DialogTitle>
            <DialogDescription>Cargá el Excel del semestre. Antes de guardar vas a ver qué filas son nuevas, cuáles cambian y cuáles quedan igual.</DialogDescription>
          </DialogHeader>
          <DialogPanel>
            <DesignationImportWizard periods={list.data?.periods ?? []} />
          </DialogPanel>
        </DialogPopup>
      </Dialog>
    </div>
  )
}
