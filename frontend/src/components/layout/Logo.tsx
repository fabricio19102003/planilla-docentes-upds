import { cn } from '@/lib/utils'

/** Brand lockup for dark brand surfaces (login). Colors come from the primary-foreground token. */
export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const textSize = { sm: 'text-2xl tracking-[0.2em]', md: 'text-4xl tracking-[0.25em]', lg: 'text-6xl tracking-[0.3em]' }
  const subtitleSize = { sm: 'text-[8px]', md: 'text-[9px]', lg: 'text-sm' }
  const lineWidth = { sm: 'w-10', md: 'w-16', lg: 'w-24' }

  return (
    <div className="flex flex-col items-center select-none">
      <div className={cn('font-black text-primary-foreground', textSize[size])}>UPDS</div>

      {/* Accent line */}
      <div className={cn('mt-1.5 h-0.5 rounded-full bg-primary-foreground/40', lineWidth[size])} />

      <p className={cn('mt-1.5 font-bold uppercase tracking-[0.25em] text-primary-foreground/60', subtitleSize[size])}>
        Sistema de Pago
      </p>
    </div>
  )
}
