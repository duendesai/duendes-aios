'use client'

import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { Loader2, Mail } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    try {
      const supabase = createClient()
      const origin = window.location.origin
      const { error } = await supabase.auth.signInWithOtp({
        email: email.trim(),
        options: {
          emailRedirectTo: `${origin}/auth/callback`,
          shouldCreateUser: true,
        },
      })
      if (error) throw error
      setSent(true)
      toast.success('Magic link enviado. Revisa tu correo.')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error desconocido'
      toast.error(`No se pudo enviar el magic link: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-cream p-4 relative overflow-hidden">
      {/* Detalle decorativo brand */}
      <div className="absolute -top-32 -right-32 h-96 w-96 rounded-full bg-brand-purple/10 blur-3xl" />
      <div className="absolute -bottom-32 -left-32 h-96 w-96 rounded-full bg-brand-yellow/10 blur-3xl" />

      <div className="relative w-full max-w-md">
        <div className="bg-card rounded-2xl border border-border shadow-card p-8 space-y-6">
          {/* Header */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-10 w-10 rounded-xl bg-brand-purple flex items-center justify-center text-white font-display font-bold text-lg">
                D
              </div>
              <div>
                <p className="tag-label text-brand-purple-dark">Espacio interno</p>
                <h1 className="font-display text-2xl font-bold text-brand-dark leading-none mt-0.5">
                  teams.duendes.net
                </h1>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Espacio de operaciones interno de Duendes. Solo acceso con magic link.
            </p>
          </div>

          {sent ? (
            <div className="space-y-4">
              <div className="rounded-xl bg-brand-yellow/15 border border-brand-yellow/30 p-4 flex items-start gap-3">
                <Mail className="h-5 w-5 text-brand-dark shrink-0 mt-0.5" />
                <div className="text-sm space-y-1">
                  <p className="font-semibold text-brand-dark">
                    Te enviamos un enlace a{' '}
                    <span className="font-bold">{email}</span>
                  </p>
                  <p className="text-muted-foreground">
                    Ábrelo desde el mismo navegador para entrar.
                    Si no lo ves, revisa spam.
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSent(false)
                  setEmail('')
                }}
              >
                Usar otro email
              </Button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="hola@duendes.net"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  autoFocus
                  required
                  disabled={loading}
                />
              </div>
              <Button type="submit" className="w-full" size="lg" disabled={loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Mail className="h-4 w-4" />
                )}
                <span>{loading ? 'Enviando...' : 'Enviar magic link'}</span>
              </Button>
            </form>
          )}
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          duendes.net · agencia de agentes de voz IA
        </p>
      </div>
    </div>
  )
}
