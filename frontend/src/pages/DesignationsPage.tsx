import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CheckCircle2, CircleHelp, FileUp, Pencil, Plus, Square, Trash2, X } from 'lucide-react'

import { useDesignationList } from '@/api/hooks/useDesignationAdmin'
import type { DesignationAdminFilters, DesignationAdminItem, DesignationAdminMutation } from '@/api/types'
import { DesignationFormDialog } from '@/components/designations/DesignationFormDialog'
import { DesignationImportWizard } from '@/components/designations/DesignationImportWizard'
import { DeleteDesignationDialog, FinalizeDesignationDialog } from '@/components/designations/DesignationLifecycleDialogs'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  SEMESTER_OPTIONS,
  emptyDesignationForm,
  formatDate,
  formatSlots,
  itemToForm,
  regenerateText,
  type DesignationForm,
} from '@/lib/designationAdminState'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

type Editor = { item: DesignationAdminItem | null; form: DesignationForm }
type Notice = { title: string; details: string[] }

function contractText(item: DesignationAdminItem) {
  if (!item.contract_start_date && !item.contract_end_date) return 'Todo el período'
  return `${formatDate(item.contract_start_date) || 'Inicio del período'} – ${formatDate(item.contract_end_date) || 'fin del período'}`
}

function HowItWorks() {
  return (
    <details className="rounded-lg border bg-muted/30 px-4 py-3 text-sm">
      <summary className="flex cursor-pointer items-center gap-2 font-medium">
        <CircleHelp className="size-4" aria-hidden="true" />¿Cómo funciona esta pantalla?
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
        <li><strong className="text-foreground">Nueva designación</strong>: asigná una materia a un docente con su horario y sus horas.</li>
        <li><strong className="text-foreground">Importar archivo</strong>: cargá el Excel del semestre; antes de guardar ves qué filas son nuevas y cuáles cambian.</li>
        <li><strong className="text-foreground">Editar</strong>: corregí materia, horario, horas o fechas mientras ese mes no esté pagado.</li>
        <li><strong className="text-foreground">Finalizar</strong>: el docente deja la materia; se le paga hasta el día que elijas y queda en el historial.</li>
        <li><strong className="text-foreground">Eliminar</strong>: solo para designaciones cargadas por error, que nadie usó todavía.</li>
        <li>Si una planilla ya está <strong className="text-foreground">aprobada</strong> o la facturación <strong className="text-foreground">publicada</strong>, los datos de ese mes no se pueden cambiar.</li>
      </ul>
    </details>
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
  const [notice, setNotice] = useState<Notice | null>(null)

  const filters: DesignationAdminFilters = {
    academic_period: period || undefined,
    q: search.trim() || undefined,
    semester: semester || undefined,
    designation_type: type || undefined,
    status,
    teacher_ci: teacherCi || undefined,
  }
  const list = useDesignationList(filters)
  const items = useMemo(() => list.data?.items ?? [], [list.data])
  const currentPeriod = list.data?.academic_period ?? period
  const subjects = useMemo(() => [...new Set(items.map((item) => item.subject))].sort(), [items])
  const activeCount = items.filter((item) => item.status === 'active').length
  const teacherName = teacherCi ? items.find((item) => item.teacher_ci === teacherCi)?.teacher_name ?? teacherCi : ''

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
            <Button variant="outline" onClick={() => setImportOpen(true)}><FileUp aria-hidden="true" />Importar archivo</Button>
            <Button onClick={() => openCreate()}><Plus aria-hidden="true" />Nueva designación</Button>
          </>
        )}
      />

      <HowItWorks />

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

      <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-6" role="search">
        <div className="sm:col-span-2">
          <Label htmlFor="designations-search">Buscar docente o materia</Label>
          <Input id="designations-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Ej: Pérez o Anatomía" />
        </div>
        <div>
          <Label htmlFor="designations-period">Período</Label>
          <select id="designations-period" className={selectClass} value={currentPeriod} onChange={(event) => setPeriod(event.target.value)}>
            {(list.data?.periods ?? (currentPeriod ? [currentPeriod] : [])).map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
        <div>
          <Label htmlFor="designations-semester">Semestre</Label>
          <select id="designations-semester" className={selectClass} value={semester} onChange={(event) => setSemester(event.target.value)}>
            <option value="">Todos</option>
            {SEMESTER_OPTIONS.map((value) => <option key={value} value={value}>{value.charAt(0) + value.slice(1).toLowerCase()}</option>)}
          </select>
        </div>
        <div>
          <Label htmlFor="designations-type">Tipo</Label>
          <select id="designations-type" className={selectClass} value={type} onChange={(event) => setType(event.target.value as typeof type)}>
            <option value="">Teoría y práctica</option>
            <option value="regular">Teoría</option>
            <option value="practice">Práctica</option>
          </select>
        </div>
        <div>
          <Label htmlFor="designations-status">Estado</Label>
          <select id="designations-status" className={selectClass} value={status} onChange={(event) => setStatus(event.target.value as typeof status)}>
            <option value="all">Todas</option>
            <option value="active">Vigentes</option>
            <option value="finalized">Finalizadas</option>
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>{items.length} designación(es) · {activeCount} vigente(s) · {items.length - activeCount} finalizada(s)</span>
        {teacherCi && (
          <Badge variant="outline" className="gap-1">
            Docente: {teacherName}
            <button type="button" aria-label="Quitar filtro de docente" onClick={() => setSearchParams({})}><X className="size-3" aria-hidden="true" /></button>
          </Badge>
        )}
      </div>

      {list.isError && (
        <Alert variant="error" role="alert">
          <AlertTitle>No se pudieron cargar las designaciones.</AlertTitle>
          <AlertDescription><Button size="sm" variant="outline" onClick={() => void list.refetch()}>Reintentar</Button></AlertDescription>
        </Alert>
      )}

      {!list.isLoading && !list.isError && items.length === 0 ? (
        <EmptyState
          title={`No hay designaciones${currentPeriod ? ` en ${currentPeriod}` : ''} con estos filtros`}
          description="Creá una designación o importá el Excel del semestre."
        />
      ) : (
        <TableCard tableClassName="min-w-[820px]">
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="px-4">Docente</TableHead>
              <TableHead className="px-4">Materia</TableHead>
              <TableHead className="px-4">Horario</TableHead>
              <TableHead className="px-4 text-right">Horas<br />sem. / mes</TableHead>
              <TableHead className="px-4">Estado y contrato</TableHead>
              <TableHead className="px-4 text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.isLoading && (
              <TableRow><TableCell colSpan={6} role="status" className="px-4 py-10 text-center text-muted-foreground">Cargando designaciones…</TableCell></TableRow>
            )}
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="px-4 py-3">
                  <p className="font-medium text-foreground">{item.teacher_name}</p>
                  <p className="text-xs text-muted-foreground">CI {item.teacher_ci}</p>
                </TableCell>
                <TableCell className="min-w-48 px-4 py-3 whitespace-normal">
                  <p className="font-medium text-foreground">{item.subject}</p>
                  <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                    <Badge variant={item.designation_type === 'practice' ? 'info' : 'secondary'} size="sm">
                      {item.designation_type === 'practice' ? 'Práctica' : 'Teoría'}
                    </Badge>
                    {item.semester} · Grupo {item.group_code}
                  </p>
                </TableCell>
                <TableCell className="px-4 py-3 text-xs">
                  {formatSlots(item.schedule_json).split(' · ').map((slot) => <p key={slot} className="whitespace-nowrap">{slot}</p>)}
                </TableCell>
                <TableCell className="px-4 py-3 text-right tabular-nums">{item.weekly_hours ?? item.weekly_hours_calculated ?? '—'} / {item.monthly_hours ?? '—'}</TableCell>
                <TableCell className="px-4 py-3 text-xs">
                  <Badge variant={item.status === 'active' ? 'success' : 'outline'}>{item.status === 'active' ? 'Vigente' : 'Finalizada'}</Badge>
                  <p className="mt-1">{contractText(item)}</p>
                  {item.has_contract && <p className="text-muted-foreground">Contrato emitido</p>}
                </TableCell>
                <TableCell className="px-4 py-3">
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="outline" onClick={() => openEdit(item)}><Pencil aria-hidden="true" />Editar</Button>
                    <Button size="sm" variant="outline" disabled={!item.actions.finalize.allowed} title={item.actions.finalize.reason ?? undefined} onClick={() => setFinalizing(item)}>
                      <Square aria-hidden="true" />Finalizar
                    </Button>
                    <Button size="icon" variant="ghost" aria-label={`Eliminar ${item.subject} ${item.group_code}`} title="Eliminar (solo si se cargó por error)" onClick={() => setDeleting(item)}>
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </TableCard>
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
