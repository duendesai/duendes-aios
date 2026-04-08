export const WEBINAR_CONFIG = {
  title: 'IA Real: Cómo automatizar tu empresa en 2026 sin morir en el intento',
  slug: 'webinar-clinicas-abril-2026',
  dateLabel: 'Miércoles 8 de abril de 2026',
  timeLabel: '19:00 h — hora peninsular española',
  timezone: 'Europe/Madrid',
  contactEmail: 'oscar@duendes.net',
  bonusPdfTitle: 'RED FLAGS — Guía definitiva para contratar servicios de IA sin pagar de más',
  thankYouTitle: '¡Gracias por registrarte al webinar!',
  thankYouLead:
    'En unos minutos recibirás un email con la confirmación de tu plaza, el acceso al webinar y el PDF de regalo “RED FLAGS”.',
  thankYouReminder:
    'Si no te llega enseguida, revisa también tu carpeta de spam, promociones o correo no deseado.',
  videoIntro:
    'Mientras tanto, te dejo este breve vídeo de bienvenida para ponerte en contexto antes de la sesión.',
  videoFallbackTitle: 'Pendiente conectar el vídeo',
  videoFallbackBody:
    'Añade la URL embebible de Vimeo en NEXT_PUBLIC_WEBINAR_WELCOME_VIDEO_EMBED_URL para mostrar aquí el vídeo de onboarding.',
} as const

export function getWelcomeVideoEmbedUrl() {
  return process.env.NEXT_PUBLIC_WEBINAR_WELCOME_VIDEO_EMBED_URL?.trim() || ''
}
