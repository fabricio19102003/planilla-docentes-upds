export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const textSize = { sm: 'text-xl', md: 'text-2xl', lg: 'text-5xl' }
  const subtitleSize = { sm: 'text-[7px]', md: 'text-[8px]', lg: 'text-xs' }
  const letterSpacing = { sm: '0.2em', md: '0.25em', lg: '0.3em' }
  const lineWidth = { sm: 32, md: 48, lg: 80 }

  return (
    <div className="flex flex-col items-center select-none">
      {/* UPDS wordmark — each letter with UPDS brand gradient */}
      <div
        className={`font-black ${textSize[size]} relative`}
        style={{ letterSpacing: letterSpacing[size] }}
      >
        <span
          style={{
            background: 'linear-gradient(180deg, #FFFFFF 0%, #B8E6FE 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >U</span>
        <span
          style={{
            background: 'linear-gradient(180deg, #FFFFFF 0%, #00A6F4 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >P</span>
        <span
          style={{
            background: 'linear-gradient(180deg, #FFFFFF 0%, #B8E6FE 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >D</span>
        <span
          style={{
            background: 'linear-gradient(180deg, #FFFFFF 0%, #00BCFF 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >S</span>
      </div>

      {/* Double accent line — UPDS brand signature */}
      <div className="flex flex-col items-center gap-[2px] mt-1.5">
        <div
          className="rounded-full"
          style={{
            width: `${lineWidth[size]}px`,
            height: '2px',
            background: 'linear-gradient(90deg, transparent 0%, #1C398E 20%, #00A6F4 50%, #1C398E 80%, transparent 100%)',
          }}
        />
        <div
          className="rounded-full"
          style={{
            width: `${lineWidth[size] * 0.6}px`,
            height: '1px',
            background: 'linear-gradient(90deg, transparent 0%, #00BCFF 50%, transparent 100%)',
            opacity: 0.5,
          }}
        />
      </div>

      {/* Subtitle */}
      <p
        className={`${subtitleSize[size]} font-bold uppercase mt-1.5`}
        style={{ letterSpacing: '0.25em', color: 'rgba(184, 230, 254, 0.5)' }}
      >
        Sistema de Pago
      </p>
    </div>
  )
}
