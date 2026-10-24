import { useEffect, useState } from 'react'

import { useAcademicTeacherSearch } from '@/api/hooks/useAcademicManagement'
import { useStartChatConversation } from '@/api/hooks/useChat'
import { TeacherCombobox } from '@/components/academic-management/TeacherCombobox'
import type { TeacherOption } from '@/components/academic-management/TeacherCombobox'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { TEACHER_SEARCH_PAGE_SIZE } from '@/lib/academicManagementState'
import { apiErrorMessage } from '@/lib/chat'

function useDebouncedValue(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

/** Mounted only while the dialog is open, so the search, page and error reset every time. */
function NewChatForm({ onStarted, onCancel }: { onStarted: (conversationId: number) => void; onCancel: () => void }) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [picked, setPicked] = useState<TeacherOption | null>(null)
  const debouncedSearch = useDebouncedValue(search.trim(), 300)
  const teachers = useAcademicTeacherSearch(debouncedSearch, page)
  const start = useStartChatConversation()
  const pageCount = Math.max(1, Math.ceil((teachers.data?.total ?? 0) / TEACHER_SEARCH_PAGE_SIZE))

  const choose = (ci: string, teacher: TeacherOption | undefined) => {
    setPicked(teacher ?? { ci, full_name: ci })
    start.mutate(ci, { onSuccess: (conversation) => onStarted(conversation.id) })
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Nuevo mensaje</DialogTitle>
        <DialogDescription>Elige al docente para abrir su conversación con Administración.</DialogDescription>
      </DialogHeader>
      <DialogPanel className="space-y-3">
        <div>
          <Label htmlFor="chat-new-teacher">Docente</Label>
          <TeacherCombobox
            id="chat-new-teacher"
            teachers={teachers.data?.items ?? []}
            value=""
            onChange={choose}
            search={search}
            onSearchChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            loading={teachers.isLoading || (search.trim() !== debouncedSearch && teachers.isFetching)}
            page={page}
            pageCount={pageCount}
            onPageChange={setPage}
            invalid={start.isError}
            describedBy="chat-new-status"
          />
        </div>
        <div id="chat-new-status" aria-live="polite" className="min-h-5 text-sm">
          {start.isPending && picked && <p role="status" className="text-muted-foreground">Abriendo la conversación con {picked.full_name}…</p>}
          {start.isError && (
            <p role="alert" className="text-destructive-foreground">
              {apiErrorMessage(start.error, 'No se pudo abrir la conversación.')}
            </p>
          )}
        </div>
      </DialogPanel>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
      </DialogFooter>
    </>
  )
}

export function NewChatDialog({
  open,
  onOpenChange,
  onStarted,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onStarted: (conversationId: number) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <NewChatForm
          onStarted={(id) => {
            onOpenChange(false)
            onStarted(id)
          }}
          onCancel={() => onOpenChange(false)}
        />
      </DialogPopup>
    </Dialog>
  )
}
