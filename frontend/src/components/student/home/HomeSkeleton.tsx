import { Skeleton } from '@/components/ui/skeleton'

/** Content-shaped placeholder of Inicio below the hero: stats strip, "Hoy" sheet and career track. */
export function HomeSkeleton() {
  return (
    <div role="status" aria-label="Cargando tu resumen" className="sph-skeleton">
      <div className="sph-strip sph-strip--skeleton" aria-hidden="true">
        {[0, 1, 2, 3].map((cell) => (
          <div key={cell} className="sph-stat">
            <Skeleton className="sph-skel-line sph-skel-line--short" />
            <Skeleton className="sph-skel-fig" />
            <Skeleton className="sph-skel-line" />
          </div>
        ))}
      </div>
      <div className="sph-row" aria-hidden="true">
        <Skeleton className="sph-skel-sheet sph-skel-sheet--ink" />
        <Skeleton className="sph-skel-sheet" />
      </div>
    </div>
  )
}
