import { useMediaQuery } from '@/hooks/use-media-query'

/** True while the OS asks for reduced motion; follows live changes of the setting. */
export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)')
}
