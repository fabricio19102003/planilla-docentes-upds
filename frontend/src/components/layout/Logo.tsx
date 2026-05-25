export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = { sm: 'text-xl', md: 'text-2xl', lg: 'text-5xl' }
  const subtitleSizes = { sm: 'text-[7px]', md: 'text-[8px]', lg: 'text-xs' }
  const gapSizes = { sm: 'tracking-[0.15em]', md: 'tracking-[0.2em]', lg: 'tracking-[0.25em]' }

  return (
    <div className="flex flex-col items-center">
      {/* Main wordmark */}
      <div
        className={`font-black ${sizes[size]} ${gapSizes[size]} relative`}
        style={{
          background: 'linear-gradient(135deg, #00BCFF 0%, #FFFFFF 40%, #00A6F4 70%, #4DA8DA 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          filter: 'drop-shadow(0 0 12px rgba(0, 166, 244, 0.3))',
        }}
      >
        UPDS
      </div>
      {/* Accent line */}
      <div
        className="rounded-full mt-1"
        style={{
          width: size === 'sm' ? '32px' : size === 'md' ? '44px' : '72px',
          height: '2px',
          background: 'linear-gradient(90deg, transparent, #00BCFF, #4DA8DA, transparent)',
        }}
      />
      {/* Subtitle */}
      <p className={`${subtitleSizes[size]} font-semibold tracking-[0.3em] uppercase mt-1`} style={{ color: 'rgba(255,255,255,0.45)' }}>
        Sistema de Pago
      </p>
    </div>
  )
}
