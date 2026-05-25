export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const textSize = { sm: 'text-2xl', md: 'text-4xl', lg: 'text-6xl' }
  const subtitleSize = { sm: 'text-[8px]', md: 'text-[9px]', lg: 'text-sm' }
  const letterSpacing = { sm: '0.2em', md: '0.25em', lg: '0.3em' }
  const lineWidth = { sm: 40, md: 64, lg: 96 }

  return (
    <div className="flex flex-col items-center select-none">
      <div
        className={`font-black text-white ${textSize[size]}`}
        style={{ letterSpacing: letterSpacing[size] }}
      >
        UPDS
      </div>

      {/* Accent line */}
      <div className="flex flex-col items-center gap-[2px] mt-1.5">
        <div
          className="rounded-full"
          style={{
            width: `${lineWidth[size]}px`,
            height: '2px',
            background: 'linear-gradient(90deg, transparent 0%, #1C398E 20%, #00A6F4 50%, #1C398E 80%, transparent 100%)',
          }}
        />
      </div>

      <p
        className={`${subtitleSize[size]} font-bold uppercase mt-1.5`}
        style={{ letterSpacing: '0.25em', color: 'rgba(184, 230, 254, 0.5)' }}
      >
        Sistema de Pago
      </p>
    </div>
  )
}
