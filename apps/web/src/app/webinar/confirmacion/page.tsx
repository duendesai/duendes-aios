import { WEBINAR_CONFIG, getWelcomeVideoEmbedUrl } from '@/lib/webinar'

export const metadata = {
  title: 'Confirmación webinar | Duendes',
  description: 'Pantalla de confirmación del webinar de Duendes',
}

function VideoCard() {
  const embedUrl = getWelcomeVideoEmbedUrl()

  if (!embedUrl) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-card/60 p-6 text-left">
        <p className="text-sm font-semibold text-foreground">{WEBINAR_CONFIG.videoFallbackTitle}</p>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {WEBINAR_CONFIG.videoFallbackBody}
        </p>
        <p className="mt-4 text-xs text-muted-foreground/80">
          Ejemplo de valor: https://player.vimeo.com/video/123456789
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-2xl shadow-black/20">
      <div className="aspect-video w-full bg-black">
        <iframe
          src={embedUrl}
          title="Vídeo de bienvenida al webinar"
          className="h-full w-full"
          allow="autoplay; fullscreen; picture-in-picture"
          allowFullScreen
        />
      </div>
    </div>
  )
}

export default function WebinarConfirmationPage() {
  return (
    <main className="min-h-screen bg-background px-4 py-10 text-foreground sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl">
        <div className="rounded-3xl border border-border bg-card/80 p-6 shadow-2xl shadow-black/20 backdrop-blur sm:p-10">
          <div className="mx-auto max-w-3xl text-center">
            <span className="inline-flex rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              Plaza reservada
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              {WEBINAR_CONFIG.thankYouTitle}
            </h1>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground sm:text-lg">
              {WEBINAR_CONFIG.thankYouLead}
            </p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {WEBINAR_CONFIG.videoIntro}
            </p>
          </div>

          <div className="mt-8">
            <VideoCard />
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-[1.4fr,0.9fr]">
            <section className="rounded-2xl border border-border bg-background/60 p-5">
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Qué vas a encontrar en esta sesión
              </h2>
              <ul className="mt-4 space-y-3 text-sm leading-relaxed text-foreground">
                <li>• Entender qué es realmente la IA aplicada a empresa y qué no lo es.</li>
                <li>• Identificar qué podría necesitar tu negocio antes de contratar nada.</li>
                <li>• Saber qué pedir a una agencia o proveedor para no pagar de más.</li>
                <li>• Detectar a tiempo soluciones sobredimensionadas, humo o sobreventa.</li>
              </ul>
            </section>

            <aside className="rounded-2xl border border-border bg-background/60 p-5">
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Datos del evento
              </h2>
              <dl className="mt-4 space-y-3 text-sm">
                <div>
                  <dt className="text-muted-foreground">Webinar</dt>
                  <dd className="mt-1 font-medium text-foreground">{WEBINAR_CONFIG.title}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Fecha</dt>
                  <dd className="mt-1 font-medium text-foreground">{WEBINAR_CONFIG.dateLabel}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Hora</dt>
                  <dd className="mt-1 font-medium text-foreground">{WEBINAR_CONFIG.timeLabel}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Entrega por email</dt>
                  <dd className="mt-1 font-medium text-foreground">Acceso al webinar + PDF RED FLAGS</dd>
                </div>
              </dl>
            </aside>
          </div>

          <div className="mt-8 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm leading-relaxed text-amber-100">
            <p>{WEBINAR_CONFIG.thankYouReminder}</p>
            <p className="mt-2 text-amber-100/90">
              Si pasados unos minutos sigues sin verlo, escribe a{' '}
              <a className="font-medium underline underline-offset-4" href={`mailto:${WEBINAR_CONFIG.contactEmail}`}>
                {WEBINAR_CONFIG.contactEmail}
              </a>
              .
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
