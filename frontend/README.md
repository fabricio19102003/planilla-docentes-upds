# Frontend de SIPAD

React 19 + TypeScript + Vite + Tailwind CSS 4, con componentes coss UI sobre Base UI y datos vía TanStack Query. Sirve tres interfaces: el panel de administración, el portal docente (`/portal`) y el portal del estudiante (`/estudiante`).

## Arrancar

```bash
npm install
npm run dev          # http://localhost:5173 — /api se redirige al backend en :8000 (vite.config.ts)
```

Antes de abrir un PR:

```bash
npx tsc -b && npm run lint && npm run build
npm run test:ui-shared        # y los demás test:* que toque tu cambio
npm run test:e2e              # Playwright, API simulada (primera vez: npm run test:e2e:install)
```

## Dónde va cada cosa

| Carpeta | Contenido |
|---------|-----------|
| `src/pages/` | Una pantalla por ruta; `pages/student/` es el portal del estudiante |
| `src/components/ui/` | Primitivas coss UI (Button, Dialog, Sheet, Menu, Table, Select…). No se editan salvo bugs |
| `src/components/shared/` | Piezas comunes de página: `PageHeader`, `StatCard` (+ `CountUp`), `StatusBadge`, `EmptyState`, `TableCard`, `PersonAvatar`, `TeacherTypeBadge`, `tones.ts` |
| `src/components/<módulo>/` | Componentes de un módulo (designations, contracts, curriculum, schedule-planner, chat…) |
| `src/lib/` | Lógica pura y testeable: estado de pantallas, formatos, navegación (`navigation.ts`), colores académicos (`academicTones.ts`) |
| `src/api/` | `client.ts` (staff), `studentClient.ts` (portal estudiante, sesión separada) y `hooks/` de TanStack Query |
| `src/context/` | `AuthContext` y `ThemeContext` (modo oscuro) |
| `src/index.css` | Tokens del tema claro/oscuro y utilidades de marca |
| `scripts/check-*.mjs` | Checks `node:test` (`npm run test:<nombre>`) |
| `e2e/` | Specs de Playwright con rutas `/api` simuladas (`e2e/support/`) |

## Reglas de UI

1. **Colores solo por tokens.** Nada de hex, `linear-gradient`, clases `gradient-*`, clases de paleta (`bg-blue-500`) ni colores en `style={{}}` dentro de páginas y componentes. Si hace falta un color o degradado nuevo, se agrega como token o `@utility` en `index.css`. Los checks `test:ui-shared`, `test:ui-portal`, `test:ui-academico` y `test:student-ui` lo verifican.
2. **Tonos semánticos.** Para color por estado o categoría usá `Tone` y los mapas de `components/shared/tones.ts`:
   - `TONE_CHIP`: fondo tintado + texto, para badges y chips.
   - `TONE_SOLID`: relleno sólido con texto blanco, para íconos destacados y avatares.
   - `TONE_DOT` y `TONE_TEXT`: punto o texto del tono.
   Para semestres y turnos usá `semesterTone()` y `shiftTone()` de `lib/academicTones.ts`, así coinciden en todas las vistas.
3. **Estructura de página.** `PageHeader` arriba (`as="h1"` solo donde no hay header de app, como el portal del estudiante), `Skeleton` mientras carga, `Alert` para errores, `EmptyState` (con `illustration`) cuando no hay datos.
4. **Modo oscuro.** Usá tokens (`bg-card`, `text-muted-foreground`, `bg-brand`…) y el tema funciona solo. `bg-brand` es la banda de marca; `text-brand` es texto de marca y cambia de valor en oscuro.
5. **Contraste y movimiento.** El texto debe cumplir WCAG AA (4,5:1; 3:1 si es grande) en ambos temas. Las animaciones nuevas tienen que apagarse con `prefers-reduced-motion`; ver el bloque correspondiente en `index.css`.
6. **Textos fijados por tests.** Muchos checks buscan textos o identificadores exactos en una página (por ejemplo, `check-schedule-planner.mjs` y `check-designation-admin.mjs`). Antes de mover texto a otro componente, mirá cómo el check lee los archivos.

## Agregar una pantalla

1. Creá `src/pages/MiPagina.tsx` con `PageHeader` y los estados de carga, error y vacío.
2. Registrá la ruta en `src/App.tsx` y el ítem en `src/lib/navigation.ts` (grupo, ícono, etiqueta). `test:navigation` valida la navegación.
3. Poné la lógica pura en `src/lib/` con su `scripts/check-<nombre>.mjs` (RED primero), y registrala en `package.json` como `test:<nombre>`.
4. Si la pantalla es crítica, agregá un spec en `e2e/` con la API simulada.

## Documentación relacionada

- [README del proyecto](../README.md): stack, instalación, modelo de negocio y módulos.
- [Guías de procesos](../docs/procesos/README.md): cómo se opera cada módulo.
