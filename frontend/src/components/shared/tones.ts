/**
 * Semantic tones shared by StatCard, StatusBadge and the other page helpers.
 * Every class resolves to a theme token (primary, success, warning, destructive, info),
 * so a tone never carries a raw color.
 */
export type Tone = 'primary' | 'success' | 'warning' | 'destructive' | 'info' | 'neutral'

export const TONES: readonly Tone[] = ['primary', 'success', 'warning', 'destructive', 'info', 'neutral']

/** Soft tinted chip: icon containers and tinted surfaces. */
export const TONE_CHIP: Record<Tone, string> = {
  primary: 'bg-primary/10 text-primary',
  success: 'bg-success/10 text-success-foreground',
  warning: 'bg-warning/10 text-warning-foreground',
  destructive: 'bg-destructive/10 text-destructive-foreground',
  info: 'bg-info/10 text-info-foreground',
  neutral: 'bg-muted text-muted-foreground',
}

/** Solid dot color, used for status indicators. */
export const TONE_DOT: Record<Tone, string> = {
  primary: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning',
  destructive: 'bg-destructive',
  info: 'bg-info',
  neutral: 'bg-muted-foreground/60',
}

/** Text color for a tone, used for trend lines and inline emphasis. */
export const TONE_TEXT: Record<Tone, string> = {
  primary: 'text-primary',
  success: 'text-success-foreground',
  warning: 'text-warning-foreground',
  destructive: 'text-destructive-foreground',
  info: 'text-info-foreground',
  neutral: 'text-muted-foreground',
}

export function isTone(value: string | undefined): value is Tone {
  return value !== undefined && (TONES as readonly string[]).includes(value)
}

/**
 * Maps a legacy CSS hex color to the closest semantic tone by hue, so pages that still pass
 * `color="..."` keep rendering until they migrate to `tone`. Greys and low-saturation colors
 * become `neutral`. The source holds no color literals: the hue is computed at runtime.
 */
export function toneFromHexColor(color: string): Tone | undefined {
  const hex = color.trim().replace(/^#/, '')
  if (!/^[0-9a-fA-F]{6}$/.test(hex) && !/^[0-9a-fA-F]{3}$/.test(hex)) return undefined
  const full = hex.length === 3 ? hex.replace(/./g, (c) => c + c) : hex
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255)
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const lightness = (max + min) / 2
  const delta = max - min
  if (delta === 0) return 'neutral'
  const saturation = delta / (1 - Math.abs(2 * lightness - 1))
  if (saturation < 0.25) return 'neutral'

  let hue: number
  if (max === r) hue = ((g - b) / delta) % 6
  else if (max === g) hue = (b - r) / delta + 2
  else hue = (r - g) / delta + 4
  hue = (hue * 60 + 360) % 360

  if (hue < 12 || hue >= 345) return 'destructive'
  if (hue < 65) return 'warning'
  if (hue < 170) return 'success'
  if (hue < 205) return 'info'
  return 'primary'
}

/** Maps the legacy gradient class names (green, yellow, red, blue, navy, slate) to a tone. */
export function toneFromGradientClass(gradient: string): Tone | undefined {
  if (/green/.test(gradient)) return 'success'
  if (/yellow|orange/.test(gradient)) return 'warning'
  if (/red/.test(gradient)) return 'destructive'
  if (/slate|gray|grey/.test(gradient)) return 'neutral'
  if (/blue|navy/.test(gradient)) return 'primary'
  return undefined
}

/**
 * Resolves a tone from the new `tone` prop or, in order, the legacy `gradient` and `color` props.
 * Falls back to `primary`.
 */
export function resolveTone(input: { tone?: Tone; color?: string; gradient?: string }): Tone {
  if (input.tone) return input.tone
  if (input.gradient) {
    const fromGradient = toneFromGradientClass(input.gradient)
    if (fromGradient) return fromGradient
  }
  if (input.color) {
    if (isTone(input.color)) return input.color
    const fromColor = toneFromHexColor(input.color)
    if (fromColor) return fromColor
  }
  return 'primary'
}
