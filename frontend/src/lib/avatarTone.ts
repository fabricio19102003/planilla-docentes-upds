import type { Tone } from '@/components/shared/tones'

/** Colorful tones an avatar can take; destructive and neutral are reserved for meaning. */
const AVATAR_TONES: readonly Tone[] = ['primary', 'violet', 'cyan', 'success', 'warning', 'info']

/** Stable tone for a person: the same key (CI or user id) always lands on the same tone. */
export function avatarTone(key: string): Tone {
  if (!key) return 'neutral'
  let hash = 2166136261
  for (let i = 0; i < key.length; i += 1) {
    hash ^= key.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return AVATAR_TONES[(hash >>> 0) % AVATAR_TONES.length]
}

/** First letters of the first two words, uppercase; "U" when there is no name. */
export function initials(fullName: string | null | undefined): string {
  const letters = (fullName ?? '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
  return letters || 'U'
}
