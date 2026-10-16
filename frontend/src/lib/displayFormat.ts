const LOCALE = 'es-BO'

export function formatHours(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${value.toLocaleString(LOCALE, { maximumFractionDigits: 2 })} h`
}

function formatBs(value: number): string {
  return `Bs ${value.toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function formatPaymentBreakdown(regular: number, practice: number): string {
  return `Teoría ${formatBs(regular)} · Asistencial ${formatBs(practice)}`
}

export function humanizeCode(code: string): string {
  const spaced = code.replace(/[_-]+/g, ' ').trim()
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : ''
}

export const ACTIVITY_CATEGORY_LABELS: Record<string, string> = {
  academic_management: 'Gestión académica',
  academic_schedule: 'Horarios académicos',
  admin: 'Administración',
  auth: 'Autenticación',
  billing: 'Facturación',
  contracts: 'Contratos',
  medicine_schedule: 'Horarios de Medicina',
  planilla: 'Planilla',
  'practice-planilla': 'Planilla de prácticas',
  practice_attendance: 'Asistencia de prácticas',
  profile: 'Perfil',
  reports: 'Reportes',
  requests: 'Solicitudes',
  settings: 'Configuración',
  teachers: 'Docentes',
  upload: 'Cargas de archivos',
  users: 'Usuarios',
  whatsapp: 'WhatsApp',
}

export function resolveActivityCategoryLabel(category: string): string {
  if (!category) return '—'
  return ACTIVITY_CATEGORY_LABELS[category] ?? humanizeCode(category)
}

const WHATSAPP_REASON_LABELS: Record<string, string> = {
  activation_artifact_unavailable: 'el comprobante no está disponible',
  activation_consent_ineligible: 'el docente no tiene consentimiento válido',
  activation_consent_revision_mismatch: 'el consentimiento cambió desde la vista previa',
  activation_disabled: 'la activación de prueba está desactivada',
  activation_provider_failed: 'el proveedor rechazó el mensaje de prueba',
  activation_publication_corrupt: 'la publicación tiene datos inconsistentes',
  activation_publication_not_current: 'la publicación ya no es la vigente',
  activation_readiness_unavailable: 'no se pudo verificar el estado del proveedor',
  activation_recipient_mismatch: 'el destinatario no coincide con la vista previa',
  activation_requires_global_delivery_disabled: 'primero hay que desactivar el envío global',
  activation_teacher_not_in_revision: 'el docente no está en la revisión publicada',
  activation_template_unapproved: 'la plantilla de mensaje no está aprobada',
  admin_disabled: 'la entrega está desactivada por administración',
  capacity_unavailable: 'el proveedor no tiene capacidad de envío disponible',
  configuration_missing: 'falta la configuración del proveedor',
  configuration_unsafe: 'la configuración del proveedor no es segura',
  global_delivery_enabled: 'el envío global ya está activado',
  process_gate_disabled: 'el proceso de envío está deshabilitado en el servidor',
  provider_unavailable: 'el proveedor de WhatsApp no está disponible',
  readiness_adapter_unavailable: 'no se pudo verificar el estado del proveedor',
  sender_unavailable: 'el número remitente no está en línea',
  template_unapproved: 'la plantilla de mensaje no está aprobada',
  worker_unavailable: 'el proceso de envío no está activo',
}

export function describeWhatsappReason(code: string): string {
  return WHATSAPP_REASON_LABELS[code] ?? code.replace(/[_-]+/g, ' ').trim()
}

export function describeWhatsappReasons(codes: string[]): string {
  return codes.map(describeWhatsappReason).join(', ')
}
