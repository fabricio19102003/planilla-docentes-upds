import { cn } from '@/lib/utils'

export function EmptyInboxIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" fill="none" aria-hidden="true" className={cn('h-auto', className)}>
      <ellipse cx="80" cy="106" rx="50" ry="7" className="fill-muted" />
      <path d="M30 66 44 34a8 8 0 0 1 7-4h58a8 8 0 0 1 7 4l14 32v26a8 8 0 0 1-8 8H38a8 8 0 0 1-8-8z" className="fill-primary/15 stroke-primary" strokeWidth="3" strokeLinejoin="round" />
      <path d="M30 66h30a6 6 0 0 1 6 6 14 14 0 0 0 28 0 6 6 0 0 1 6-6h30" className="stroke-primary" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      <rect x="62" y="14" width="36" height="22" rx="5" className="fill-tone-cyan/25 stroke-tone-cyan" strokeWidth="3" />
      <path d="M70 25h20" className="stroke-tone-cyan" strokeWidth="3" strokeLinecap="round" />
      <circle cx="132" cy="24" r="4" className="fill-tone-violet/35" />
      <circle cx="26" cy="38" r="3" className="fill-tone-violet/35" />
    </svg>
  )
}
