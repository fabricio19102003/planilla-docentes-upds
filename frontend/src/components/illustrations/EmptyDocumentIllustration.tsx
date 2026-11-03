import { cn } from '@/lib/utils'

export function EmptyDocumentIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" fill="none" aria-hidden="true" className={cn('h-auto', className)}>
      <ellipse cx="80" cy="108" rx="40" ry="6" className="fill-muted" />
      <path d="M44 14h44l28 28v58a6 6 0 0 1-6 6H44a6 6 0 0 1-6-6V20a6 6 0 0 1 6-6z" className="fill-card stroke-primary" strokeWidth="3" strokeLinejoin="round" />
      <path d="M88 14v22a6 6 0 0 0 6 6h22" className="fill-primary/20 stroke-primary" strokeWidth="3" strokeLinejoin="round" />
      <path d="M52 62h44M52 76h30M52 90h38" className="stroke-primary/40" strokeWidth="4" strokeLinecap="round" />
      <circle cx="122" cy="84" r="14" className="fill-tone-cyan/25 stroke-tone-cyan" strokeWidth="3" />
      <path d="M116 84h12" className="stroke-tone-cyan" strokeWidth="3" strokeLinecap="round" />
      <circle cx="28" cy="40" r="3.5" className="fill-tone-violet/40" />
    </svg>
  )
}
