import { redirect } from 'next/navigation'
import Sidebar from '@/components/layout/sidebar'
import { createClient } from '@/lib/supabase/server'

export default async function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar userEmail={user.email ?? 'sin email'} />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  )
}
