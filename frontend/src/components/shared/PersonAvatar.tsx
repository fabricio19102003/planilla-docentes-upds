import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { avatarTone, initials } from '@/lib/avatarTone'
import { cn } from '@/lib/utils'
import { TONE_CHIP, TONE_SOLID } from './tones'

export type PersonAvatarSize = 'sm' | 'md' | 'lg'

export interface PersonAvatarProps {
  /** Full name, used for the initials. */
  name: string | null | undefined
  /** Stable key for the color (CI or user id). Falls back to the name. */
  colorKey?: string | number | null
  /** Optional photo; the initials show while it loads or when it fails. */
  imageUrl?: string | null
  size?: PersonAvatarSize
  /** Hidden from assistive tech by default because the name is rendered next to it. */
  decorative?: boolean
  className?: string
}

const SIZE_CLASS: Record<PersonAvatarSize, string> = {
  sm: '[--avatar-size:--spacing(7)]',
  md: '[--avatar-size:--spacing(9)]',
  lg: '[--avatar-size:--spacing(12)]',
}

/**
 * Round avatar with the person's initials on a stable tone derived from their CI or user id.
 * Small and medium sizes use the soft chip, the large one the solid tone.
 *
 * @example
 * <PersonAvatar name={teacher.full_name} colorKey={teacher.ci} size="sm" />
 */
export function PersonAvatar({ name, colorKey, imageUrl, size = 'md', decorative = true, className }: PersonAvatarProps) {
  const tone = avatarTone(String(colorKey ?? name ?? ''))
  const palette = size === 'lg' ? TONE_SOLID : TONE_CHIP
  return (
    <Avatar
      className={cn(SIZE_CLASS[size], className)}
      {...(decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': name ?? 'Usuario' })}
    >
      {imageUrl && <AvatarImage src={imageUrl} alt="" />}
      <AvatarFallback className={cn('font-semibold', palette[tone])}>{initials(name)}</AvatarFallback>
    </Avatar>
  )
}
