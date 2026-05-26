'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname, useRouter } from 'next/navigation'
import {
  Phone,
  CalendarClock,
  LogOut,
  ChevronsLeft,
  ChevronsRight,
  type LucideIcon,
} from 'lucide-react'
import * as Tooltip from '@radix-ui/react-tooltip'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { createClient } from '@/lib/supabase/client'

interface SidebarProps {
  userEmail: string
}

interface NavItem {
  href: string
  label: string
  icon: LucideIcon
  tag?: string
}

const NAV: NavItem[] = [
  { href: '/sdr', label: 'Llamadas', icon: Phone, tag: 'SDR' },
  { href: '/agenda', label: 'Agenda', icon: CalendarClock },
]

const STORAGE_KEY = 'teams-sidebar-collapsed'

export default function Sidebar({ userEmail }: SidebarProps) {
  const pathname = usePathname()
  const router = useRouter()

  // Estado colapsado persistido en localStorage
  const [collapsed, setCollapsed] = useState(false)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === '1') setCollapsed(true)
    setHydrated(true)
  }, [])

  function toggleCollapsed() {
    const next = !collapsed
    setCollapsed(next)
    localStorage.setItem(STORAGE_KEY, next ? '1' : '0')
  }

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.replace('/login')
    router.refresh()
  }

  return (
    <Tooltip.Provider delayDuration={200}>
      <aside
        className={cn(
          'shrink-0 border-r border-border bg-card flex flex-col transition-[width] duration-200',
          collapsed ? 'w-16' : 'w-60',
          !hydrated && 'invisible'
        )}
      >
        {/* Header: logo */}
        <div
          className={cn(
            'border-b border-border flex items-center',
            collapsed ? 'h-16 justify-center' : 'h-16 px-4 gap-3'
          )}
        >
          <Link
            href="/sdr"
            className="flex items-center gap-2.5 group"
            title="teams.duendes.net"
          >
            <Image
              src="/logodef.svg"
              alt="Duendes"
              width={36}
              height={36}
              priority
              className="h-9 w-9 shrink-0"
            />
            {!collapsed && (
              <div>
                <div className="font-display text-base font-bold leading-tight text-brand-dark">
                  teams
                </div>
                <div className="text-[11px] text-muted-foreground leading-tight">
                  duendes.net
                </div>
              </div>
            )}
          </Link>
        </div>

        {/* Nav items */}
        <nav className="flex-1 p-2 space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon
            const active = pathname.startsWith(item.href)
            const link = (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 rounded-xl text-sm font-semibold transition-colors',
                  collapsed ? 'justify-center h-10 w-10 mx-auto' : 'px-3 py-2.5',
                  active
                    ? 'bg-brand-purple/10 text-brand-purple-dark'
                    : 'text-brand-dark/70 hover:bg-accent hover:text-brand-dark'
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && (
                  <>
                    <span className="flex-1">{item.label}</span>
                    {item.tag && (
                      <span className="text-[9px] font-bold uppercase tracking-widest text-brand-purple-dark/60">
                        {item.tag}
                      </span>
                    )}
                  </>
                )}
              </Link>
            )

            if (!collapsed) return link

            return (
              <Tooltip.Root key={item.href}>
                <Tooltip.Trigger asChild>{link}</Tooltip.Trigger>
                <Tooltip.Portal>
                  <Tooltip.Content
                    side="right"
                    sideOffset={8}
                    className="bg-brand-dark text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-lg z-50"
                  >
                    {item.label}
                    <Tooltip.Arrow className="fill-brand-dark" />
                  </Tooltip.Content>
                </Tooltip.Portal>
              </Tooltip.Root>
            )
          })}
        </nav>

        {/* Footer: user + collapse toggle + logout */}
        <div className="p-2 border-t border-border space-y-1">
          {!collapsed && (
            <div
              className="text-xs text-muted-foreground truncate px-2 py-1.5"
              title={userEmail}
            >
              {userEmail}
            </div>
          )}

          {collapsed ? (
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <button
                  onClick={handleLogout}
                  className="h-10 w-10 mx-auto flex items-center justify-center rounded-xl text-muted-foreground hover:bg-accent hover:text-brand-dark transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </Tooltip.Trigger>
              <Tooltip.Portal>
                <Tooltip.Content
                  side="right"
                  sideOffset={8}
                  className="bg-brand-dark text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-lg z-50"
                >
                  Salir · {userEmail}
                  <Tooltip.Arrow className="fill-brand-dark" />
                </Tooltip.Content>
              </Tooltip.Portal>
            </Tooltip.Root>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start text-muted-foreground hover:text-brand-dark"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" />
              Salir
            </Button>
          )}

          {/* Toggle colapsar */}
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button
                onClick={toggleCollapsed}
                className={cn(
                  'flex items-center justify-center rounded-xl text-muted-foreground hover:bg-accent hover:text-brand-dark transition-colors',
                  collapsed ? 'h-10 w-10 mx-auto' : 'h-9 w-full gap-2 text-xs'
                )}
              >
                {collapsed ? (
                  <ChevronsRight className="h-4 w-4" />
                ) : (
                  <>
                    <ChevronsLeft className="h-4 w-4" />
                    <span>Colapsar</span>
                  </>
                )}
              </button>
            </Tooltip.Trigger>
            {collapsed && (
              <Tooltip.Portal>
                <Tooltip.Content
                  side="right"
                  sideOffset={8}
                  className="bg-brand-dark text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-lg z-50"
                >
                  Expandir menú
                  <Tooltip.Arrow className="fill-brand-dark" />
                </Tooltip.Content>
              </Tooltip.Portal>
            )}
          </Tooltip.Root>
        </div>
      </aside>
    </Tooltip.Provider>
  )
}
