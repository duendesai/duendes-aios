# Configuración recomendada — Meta Instant Form + página de confirmación + email

## Flujo recomendado

```text
Meta Ads
  → Instant Form de Meta
  → Pantalla final de Meta (confirmación + CTA)
  → Página propia con vídeo de bienvenida
  → Email con acceso al webinar + PDF RED FLAGS
  → Recordatorios previos al evento
```

## 1. Pantalla final del Instant Form de Meta

### Título
¡Gracias por registrarte al webinar!

### Texto
En unos minutos recibirás un email con la confirmación de tu plaza, el acceso al webinar y el PDF de regalo “RED FLAGS”.

Mientras tanto, puedes ver este breve vídeo de bienvenida para ponerte en contexto antes de la sesión.

### Botón CTA
Ver vídeo de bienvenida

### URL destino
`https://TU-DOMINIO/webinar/confirmacion`

> Si el proyecto se sirve en local con Next.js, la ruta ya existe en `apps/web/src/app/webinar/confirmacion/page.tsx`.

## 2. Página propia de confirmación

Ruta implementada:

- `/webinar/confirmacion`

Contenido que ya incluye:

- confirmación del registro
- bloque de vídeo de bienvenida
- expectativa de la sesión
- recordatorio de que el acceso y el PDF llegan por email
- aviso de revisar spam/promociones

## 3. Vimeo

Subir el vídeo de onboarding a Vimeo y usar una URL embebible de este formato:

```text
https://player.vimeo.com/video/123456789
```

### Variable a configurar en el frontend

Añadir en `apps/web/.env.local`:

```env
NEXT_PUBLIC_WEBINAR_WELCOME_VIDEO_EMBED_URL=https://player.vimeo.com/video/123456789
```

## 4. Recomendación de privacidad en Vimeo

- Opción rápida: Unlisted
- Opción más profesional: restringir embed al dominio de Duendes

## 5. Qué debe seguir llegando por email

Aunque el vídeo se vea justo tras el registro, el email sigue siendo el canal oficial para:

- enlace de acceso al webinar
- PDF “RED FLAGS”
- recordatorios de asistencia
- seguimiento postwebinar

## 6. Datos del webinar ya cerrados

- Webinar: IA Real: Cómo automatizar tu empresa en 2026 sin morir en el intento
- Fecha: miércoles 8 de abril de 2026
- Hora: 19:00 h (hora peninsular española)
- Remitente: oscar@duendes.net
- Regalo: RED FLAGS — Guía definitiva para contratar servicios de IA sin pagar de más
- CTA postwebinar: 20% de descuento en la configuración inicial + reserva de diagnóstico gratuito de 15 minutos por Cal.com
