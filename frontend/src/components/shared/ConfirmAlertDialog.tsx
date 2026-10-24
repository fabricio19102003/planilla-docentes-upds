import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogPopup,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

import { ConfirmSummaryDetails, type ConfirmDetails } from './ConfirmSummaryDetails'

/** `ConfirmSummary` from `@/lib/planillaGenerationGuard` is assignable to this type. */
export interface ConfirmAlertSummary extends ConfirmDetails {
  title: string
  confirmLabel: string
  /** `destructive` paints the confirm button in the destructive variant. */
  tone?: 'default' | 'destructive'
}

export interface ConfirmAlertDialogProps {
  /** The dialog is open while a summary is set; pass `null` to close it. */
  summary: ConfirmAlertSummary | null
  /** Disables both buttons and ignores dismissal while the action runs. */
  pending?: boolean
  /** Muted line under the title. Defaults to a generic review prompt. */
  description?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

/**
 * AlertDialog confirmation for irreversible or payroll-changing actions (S11).
 * It does not close itself on confirm: clear `summary` when the action settles.
 *
 * @example
 * <ConfirmAlertDialog
 *   summary={pending ? { title: 'Eliminar usuario', confirmLabel: 'Eliminar', tone: 'destructive',
 *     rows: [{ label: 'Usuario', value: user.full_name }], consequence: 'No se puede deshacer.' } : null}
 *   pending={mutation.isPending}
 *   onConfirm={() => mutation.mutate(user.id)}
 *   onCancel={() => setPending(false)}
 * />
 */
export function ConfirmAlertDialog({
  summary,
  pending = false,
  description = 'Revisá el resumen antes de continuar.',
  cancelLabel = 'Cancelar',
  onConfirm,
  onCancel,
}: ConfirmAlertDialogProps) {
  const destructive = summary?.tone === 'destructive'

  return (
    <AlertDialog
      open={summary !== null}
      onOpenChange={(open) => {
        if (!open && !pending) onCancel()
      }}
    >
      <AlertDialogPopup className="max-w-md">
        {summary && (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>{summary.title}</AlertDialogTitle>
              <AlertDialogDescription>{description}</AlertDialogDescription>
            </AlertDialogHeader>

            <div className="px-6 pb-6">
              <ConfirmSummaryDetails rows={summary.rows} warning={summary.warning} consequence={summary.consequence} />
            </div>

            <AlertDialogFooter>
              <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
                {cancelLabel}
              </Button>
              <Button
                type="button"
                variant={destructive ? 'destructive' : 'default'}
                onClick={onConfirm}
                loading={pending}
              >
                {summary.confirmLabel}
              </Button>
            </AlertDialogFooter>
          </>
        )}
      </AlertDialogPopup>
    </AlertDialog>
  )
}
