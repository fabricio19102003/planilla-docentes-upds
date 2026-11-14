import { ClinicNotFound } from '@/components/student'

/**
 * Unknown /estudiante/* paths. The 404 is contained: a fixed one would cover the brand band and the
 * mobile bottom bar, so it fills this positioned box and the shell stays usable around it.
 */
export function StudentNotFoundPage() {
  return (
    <div className="relative h-[clamp(26rem,65dvh,40rem)] overflow-hidden rounded-2xl border border-border">
      <ClinicNotFound contained />
    </div>
  )
}
