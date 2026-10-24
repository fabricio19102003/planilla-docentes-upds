import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogPanel,
  DialogPopup,
  DialogTitle,
} from '@/components/ui/dialog'
import type { ConfirmSummary } from '@/lib/planillaGenerationGuard'

import { ConfirmSummaryDetails } from './ConfirmSummaryDetails'

interface ConfirmActionDialogProps {
  summary: ConfirmSummary | null
  pending?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmActionDialog({ summary, pending = false, onConfirm, onCancel }: ConfirmActionDialogProps) {
  const destructive = summary?.tone === 'destructive'

  return (
    <Dialog open={summary !== null} onOpenChange={(open) => { if (!open) onCancel() }}>
      <DialogPopup className="max-w-md">
        {summary && (
          <>
            <DialogHeader>
              <DialogTitle>{summary.title}</DialogTitle>
              <DialogDescription>Revisá el resumen antes de continuar.</DialogDescription>
            </DialogHeader>

            <DialogPanel>
              <ConfirmSummaryDetails rows={summary.rows} warning={summary.warning} consequence={summary.consequence} />
            </DialogPanel>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
                Cancelar
              </Button>
              <Button
                type="button"
                variant={destructive ? 'destructive' : 'default'}
                onClick={onConfirm}
                disabled={pending}
              >
                {summary.confirmLabel}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogPopup>
    </Dialog>
  )
}
