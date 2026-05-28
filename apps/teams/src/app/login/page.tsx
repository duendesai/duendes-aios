'use client'

import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { Loader2, Mail, KeyRound, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { createClient } from '@/lib/supabase/client'

type Mode = 'password' | 'magic'

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>('password')
  const [email, setEmail] = useState('hola@duendes.net')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submitPassword(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!email.trim() || !password) return
    setLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      })
      if (error) throw error
      // Redirigir al SDR — el middleware refresca el cookie automáticamente
      window.location.href = '/sdr'
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error desconocido'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  async function submitMagicLink(e: FormEvent) {
    e.preventDefault()
    setError(null)
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
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-cream p-4 relative overflow-hidden">
      <div className="absolute -top-32 -right-32 h-96 w-96 rounded-full bg-brand-purple/10 blur-3xl" />
      <div className="absolute -bottom-32 -left-32 h-96 w-96 rounded-full bg-brand-yellow/10 blur-3xl" />

      <div className="relative w-full max-w-md">
        <div className="bg-card rounded-2xl border border-border shadow-card p-8 space-y-6">
          {/* Header */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <img
                src="/logodef.svg"
                alt="Duendes"
                className="h-10 w-10"
              />
              <div>
                <p className="tag-label text-brand-purple-dark">Espacio interno</p>
                <h1 className="font-display text-2xl font-bold text-brand-dark leading-none mt-0.5">
                  teams.duendes.net
                </h1>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Espacio de operaciones interno de Duendes.
            </p>
          </div>

          {sent ? (
            <div className="space-y-4">
              <div className="rounded-xl bg-brand-yellow/15 border border-brand-yellow/30 p-4 flex items-start gap-3">
                <Mail className="h-5 w-5 text-brand-dark shrink-0 mt-0.5" />
                <div className="text-sm space-y-1">
                  <p className="font-semibold text-brand-dark">
                    Magic link enviado a <span className="font-bold">{email}</span>
                  </p>
                  <p className="text-muted-foreground">
                    Ábrelo desde este navegador para entrar. Después podrás{' '}
                    configurar tu contraseña en <strong>Cuenta</strong>.
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
          ) : mode === 'password' ? (
            <form onSubmit={submitPassword} className="space-y-4" autoComplete="on">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="hola@duendes.net"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  required
                  disabled={loading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Contraseña</Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password webauthn"
                  required
                  disabled={loading}
                />
              </div>
              {error && (
                <div className="text-xs text-destructive bg-destructive/10 border border-destructive/30 rounded-lg p-2.5">
                  {error}
                </div>
              )}
              <Button type="submit" className="w-full" size="lg" disabled={loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <LogIn className="h-4 w-4" />
                )}
                <span>{loading ? 'Entrando...' : 'Entrar'}</span>
              </Button>
              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setMode('magic')
                    setError(null)
                  }}
                  className="text-xs text-muted-foreground hover:text-brand-purple-dark transition-colors"
                >
                  ¿Sin contraseña aún? <strong>Recibir magic link</strong>
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={submitMagicLink} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="hola@duendes.net"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  required
                  disabled={loading}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Te enviaremos un enlace de acceso al correo. Solo para el primer
                login — después configura contraseña en <strong>Cuenta</strong>.
              </p>
              {error && (
                <div className="text-xs text-destructive bg-destructive/10 border border-destructive/30 rounded-lg p-2.5">
                  {error}
                </div>
              )}
              <Button type="submit" className="w-full" size="lg" disabled={loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Mail className="h-4 w-4" />
                )}
                <span>{loading ? 'Enviando...' : 'Enviar magic link'}</span>
              </Button>
              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setMode('password')
                    setError(null)
                  }}
                  className="text-xs text-muted-foreground hover:text-brand-purple-dark transition-colors"
                >
                  <KeyRound className="inline h-3 w-3 mr-0.5" /> Volver a entrar
                  con contraseña
                </button>
              </div>
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
