export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = { sm: 'text-xl', md: 'text-3xl', lg: 'text-5xl' }
  return (
    <div className={`font-black tracking-wider ${sizes[size]}`}>
      <span style={{ color: '#4DA8DA' }}>U</span>
      <span style={{ color: '#0066CC' }}>P</span>
      <span style={{ color: '#4DA8DA' }}>D</span>
      <span style={{ color: '#FFFFFF' }}>S</span>
    </div>
  )
}
