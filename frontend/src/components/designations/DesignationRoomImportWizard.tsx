import { useState } from 'react'
import { ChevronDown, TriangleAlert } from 'lucide-react'

import { useApplyDesignationRooms, useDesignationRoomPreview } from '@/api/hooks/useDesignationAdmin'
import { FileUploader } from '@/components/shared/FileUploader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toastManager } from '@/components/ui/toast'
import {
  applyRoomsLabel,
  canApplyRooms,
  roomImportError,
  roomLabel,
  roomPreviewSections,
  roomSectionTabs,
  type DesignationRoomPreview,
  type RoomPreviewMatch,
  type RoomSectionKey,
} from '@/lib/designationRoomImport'

const SUMMARY_TILES: { key: keyof DesignationRoomPreview['summary']; label: string }[] = [
  { key: 'changed', label: 'se asignan' },
  { key: 'matched', label: 'designaciones con fila' },
  { key: 'unknown_rooms', label: 'aulas no reconocidas' },
  { key: 'unmatched_rows', label: 'filas sin designación' },
  { key: 'designations_without_row', label: 'designaciones sin fila' },
]

const MATCH_HEAD = ['Docente', 'Materia', 'Sem. / Grupo', 'Aula actual', 'Aula nueva']

function Empty({ cols }: { cols: number }) {
  return <TableRow><TableCell colSpan={cols} className="py-6 text-center text-muted-foreground">No hay filas en este grupo.</TableCell></TableRow>
}

function MatchRows({ rows, withNew = true }: { rows: RoomPreviewMatch[]; withNew?: boolean }) {
  return rows.map((row) => (
    <TableRow key={row.designation_id}>
      <TableCell>{row.teacher_name}</TableCell>
      <TableCell className="font-medium">{row.subject}</TableCell>
      <TableCell>{row.semester} · {row.group_code}</TableCell>
      <TableCell className={row.current_classroom ? '' : 'text-muted-foreground'}>{roomLabel(row.current_classroom)}</TableCell>
      {withNew && <TableCell className="font-medium">{roomLabel(row.new_classroom)}</TableCell>}
    </TableRow>
  ))
}

function SectionTable({ head, empty, children }: { head: string[]; empty: boolean; children: React.ReactNode }) {
  return (
    <div className="max-h-72 overflow-auto rounded-md border">
      <Table>
        <TableHeader><TableRow>{head.map((name) => <TableHead key={name}>{name}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {children}
          {empty && <Empty cols={head.length} />}
        </TableBody>
      </Table>
    </div>
  )
}

function PreviewSections({ preview }: { preview: DesignationRoomPreview }) {
  const sections = roomPreviewSections(preview)
  const tabs = roomSectionTabs(preview)
  const firstWithRows = tabs.find((tab) => tab.count > 0)
  const [active, setActive] = useState<RoomSectionKey>(firstWithRows ? firstWithRows.key : 'assign')
  return (
    <div className="flex flex-col gap-2">
      <div role="tablist" aria-label="Qué revisar" className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <Button key={tab.key} type="button" role="tab" aria-selected={active === tab.key} size="sm" variant={active === tab.key ? 'default' : 'outline'} onClick={() => setActive(tab.key)}>
            {tab.label} ({tab.count})
          </Button>
        ))}
      </div>
      {active === 'assign' && (
        <SectionTable head={MATCH_HEAD} empty={!sections.assign.length}><MatchRows rows={sections.assign} /></SectionTable>
      )}
      {active === 'unknown' && (
        <SectionTable head={['Fila', 'Docente', 'Materia', 'Grupo', 'AULA', 'Motivo']} empty={!sections.unknown.length}>
          {sections.unknown.map((row) => (
            <TableRow key={row.row}>
              <TableCell className="tabular-nums">{row.row}</TableCell>
              <TableCell>{row.teacher}</TableCell>
              <TableCell className="font-medium">{row.subject}</TableCell>
              <TableCell>{row.group_code}</TableCell>
              <TableCell>{row.aula}</TableCell>
              <TableCell className="whitespace-normal">{row.reason}</TableCell>
            </TableRow>
          ))}
        </SectionTable>
      )}
      {active === 'unmatched' && (
        <SectionTable head={['Fila', 'Docente', 'Materia', 'Sem. / Grupo', 'AULA']} empty={!sections.unmatched.length}>
          {sections.unmatched.map((row) => (
            <TableRow key={row.row}>
              <TableCell className="tabular-nums">{row.row}</TableCell>
              <TableCell>{row.teacher}</TableCell>
              <TableCell className="font-medium">{row.subject}</TableCell>
              <TableCell>{row.semester} · {row.group_code}</TableCell>
              <TableCell>{row.aula}</TableCell>
            </TableRow>
          ))}
        </SectionTable>
      )}
      {active === 'withoutRow' && (
        <SectionTable head={['Docente', 'Materia', 'Grupo']} empty={!sections.withoutRow.length}>
          {sections.withoutRow.map((row) => (
            <TableRow key={row.designation_id}>
              <TableCell>{row.teacher_name}</TableCell>
              <TableCell className="font-medium">{row.subject}</TableCell>
              <TableCell>{row.group_code}</TableCell>
            </TableRow>
          ))}
        </SectionTable>
      )}
      <Collapsible>
        <CollapsibleTrigger render={<Button type="button" variant="ghost" size="sm" />}>
          <ChevronDown aria-hidden="true" />Sin cambios ({sections.unchanged.length})
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SectionTable head={MATCH_HEAD.slice(0, 4)} empty={!sections.unchanged.length}>
            <MatchRows rows={sections.unchanged} withNew={false} />
          </SectionTable>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

/**
 * Load each theory designation's classroom from the designation workbook (AULA column):
 * read the preview, then apply. Applying only sets the classroom; nothing else changes.
 */
export function DesignationRoomImportWizard({ onApplied }: { onApplied?: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<DesignationRoomPreview | null>(null)
  const [progress, setProgress] = useState(0)
  const previewRooms = useDesignationRoomPreview()
  const applyRooms = useApplyDesignationRooms()
  const failure = previewRooms.error ?? applyRooms.error
  const problem = failure ? roomImportError(failure, 'Verificá el archivo e intentá de nuevo.') : null

  const reset = () => { setPreview(null); previewRooms.reset(); applyRooms.reset() }

  const generate = () => {
    if (!file) return
    reset()
    setProgress(0)
    previewRooms.mutate({ file, onProgress: setProgress }, { onSuccess: setPreview })
  }

  const apply = () => {
    if (!file || !preview) return
    applyRooms.mutate({ file, previewDigest: preview.preview_digest }, {
      onSuccess: (result) => {
        toastManager.add({
          type: 'success',
          title: 'Aulas asignadas',
          description: `${result.changed_designation_ids.length} designaciones de ${result.academic_period} tienen aula nueva.`,
        })
        onApplied?.()
      },
    })
  }

  const stale = Boolean(applyRooms.error) && roomImportError(applyRooms.error, '').stale

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-3">
        <FileUploader
          accept=".xlsx"
          label="Seleccioná el Excel de designaciones"
          description="Hoja DOCENTES TEORICOS con la columna AULA. Se usa el período activo."
          onFileSelect={(selected) => { setFile(selected); reset() }}
          progress={previewRooms.isPending ? progress : null}
        />
        <Button onClick={generate} disabled={!file || previewRooms.isPending || applyRooms.isPending}>
          {previewRooms.isPending ? 'Revisando el archivo…' : 'Generar vista previa'}
        </Button>
      </section>

      {problem && (
        <Alert variant="error" role="alert">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>{stale ? 'La vista previa cambió' : 'No se pudo leer o aplicar el archivo'}</AlertTitle>
          <AlertDescription>
            <p>{problem.message}</p>
            {stale && (
              <Button type="button" size="sm" variant="outline" className="mt-2" onClick={generate}>Volver a generar la vista previa</Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {preview && (
        <section className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">Período {preview.academic_period}. Todavía no se guardó nada.</p>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {SUMMARY_TILES.map((tile) => (
              <div key={tile.key} className="rounded-md border p-3">
                <p className="text-2xl font-semibold tabular-nums">{preview.summary[tile.key]}</p>
                <p className="text-xs text-muted-foreground">{tile.label}</p>
              </div>
            ))}
          </div>
          <PreviewSections preview={preview} />
          <p className="text-xs text-muted-foreground">Aplicar solo cambia el aula de cada designación; no toca horas, planilla ni contratos.</p>
          <Button onClick={apply} disabled={!canApplyRooms(preview) || applyRooms.isPending}>
            {applyRooms.isPending ? 'Aplicando…' : applyRoomsLabel(preview)}
          </Button>
        </section>
      )}
    </div>
  )
}
