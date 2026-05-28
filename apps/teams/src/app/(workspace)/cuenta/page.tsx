'use client'

import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { KeyRound, Loader2, Mail, Check, Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { createClient } from '@/lib/supabase/client'

export default function CuentaPage() {
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [hasPassword, setHasPassword] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data }) => {
      setUserEmail(data.user?.email ?? null)
      // Heurística: si hay app_metadata.providers que incluye 'email' Y identities con method 'password',
      // tiene password. Si no, usa solo magic link.
      const identities = data.user?.identities ?? []
      const emailIdentity = identities.find((i) => i.provider === 'email')
      // Supabase no expone directamente si hay password seteado.
      // La forma fiable es intentar `signInWithPassword` — pero no queremos hacer eso aquí.
      // Mostramos el form siempre, y si ya tiene password, lo cambia.
      setHasPassword(!!emailIdentity)
    })
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    if (newPassword.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.updateUser({ password: newPassword })
      if (error) throw error
      setSuccess('Contraseña actualizada. La próxima vez ya puedes entrar con ella.')
      setNewPassword('')
      setConfirmPassword('')
      toast.success('Contraseña actualizada')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error desconocido'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      <header className="h-16 shrink-0 border-b border-border px-6 flex items-center bg-card">
        <div>
          <p className="tag-label text-brand-purple-dark">Cuenta</p>
          <h1 className="font-display font-bold text-brand-dark text-base leading-tight mt-0.5">
            Tus credenciales
          </h1>
        </div>
      </header>

      <div className="p-6 max-w-2xl space-y-6">
        {/* Identidad */}
        <Card className="p-6 space-y-3">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-brand-purple-dark" />
            <p className="tag-label text-brand-purple-dark">Identidad</p>
          </div>
          <div className="text-sm space-y-1">
            <p className="font-semibold text-brand-dark">{userEmail ?? '…'}</p>
            <p className="text-xs text-muted-foreground">
              No puedes cambiar el email desde aquí. Si lo necesitas, dilo y lo
              hacemos en Supabase.
            </p>
          </div>
        </Card>

        {/* Contraseña */}
        <Card className="p-6 space-y-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <KeyRound className="h-4 w-4 text-brand-purple-dark" />
              <p className="tag-label text-brand-purple-dark">
                Contraseña
              </p>
            </div>
            <h2 className="font-display text-lg font-bold text-brand-dark">
              {hasPassword === false
                ? 'Configura una contraseña'
                : 'Cambiar contraseña'}
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Mínimo 8 caracteres. Cuando la guardes, el navegador (Safari/Chrome)
              te ofrecerá guardarla en Keychain — la próxima vez entras con Touch
              ID / Face ID directamente.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" autoComplete="on">
            {/* Email oculto para que el navegador asocie correctamente */}
            <input
              type="email"
              name="email"
              autoComplete="username"
              value={userEmail ?? ''}
              readOnly
              hidden
            />
            <div className="space-y-2">
              <Label htmlFor="new-password">Nueva contraseña</Label>
              <Input
                id="new-password"
                name="new-password"
                type="password"
                autoComplete="new-password"
                placeholder="Mínimo 8 caracteres"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Repite la contraseña</Label>
              <Input
                id="confirm-password"
                name="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            {error && (
              <div className="text-xs text-destructive bg-destructive/10 border border-destructive/30 rounded-lg p-2.5">
                {error}
              </div>
            )}
            {success && (
              <div className="text-xs text-success bg-success/10 border border-success/30 rounded-lg p-2.5 flex items-center gap-2">
                <Check className="h-4 w-4" />
                {success}
              </div>
            )}

            <Button type="submit" disabled={loading} size="lg">
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <KeyRound className="h-4 w-4" />
              )}
              <span>{loading ? 'Guardando...' : 'Guardar contraseña'}</span>
            </Button>
          </form>
        </Card>

        {/* Passkey (futuro) */}
        <Card className="p-6 space-y-3 border-dashed">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <p className="tag-label text-muted-foreground">Passkey (próximamente)</p>
          </div>
          <p className="text-sm text-muted-foreground">
            Para login con Touch ID directo (sin password) habrá que activar MFA
            WebAuthn en Supabase. Por ahora, si guardas la contraseña en Keychain
            del Mac, ya tienes la misma UX: Safari/Chrome la rellena con Touch ID
            automáticamente.
          </p>
        </Card>
      </div>
    </div>
  )
}
