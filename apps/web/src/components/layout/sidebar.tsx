'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Bot, FileText, FolderOpen, Plug, Rss, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DEPARTMENTS } from '@/lib/constants'

interface NavItemProps {
  href: string
  label: string
  icon: React.ReactNode
  isActive: boolean
}

function NavItem({ href, label, icon, isActive }: NavItemProps) {
  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-colors',
        isActive
          ? 'bg-accent text-foreground font-medium'
          : 'text-muted-foreground hover:text-foreground hover:bg-accent/60'
      )}
    >
      {icon}
      <span>{label}</span>
    </Link>
  )
}

function SidebarSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
        {title}
      </p>
      {children}
    </div>
  )
}

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside
      className="flex flex-col h-full shrink-0 border-r border-border bg-card"
      style={{ width: 240 }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-border">
        <div className="h-7 w-7 rounded-md bg-primary flex items-center justify-center">
          <Bot className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="font-bold text-foreground tracking-tight text-base">AIOS</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
        {/* Chat / Agents */}
        <SidebarSection title="Chat">
          {DEPARTMENTS.map((dept) => (
            <NavItem
              key={dept.id}
              href={`/chat/${dept.id}`}
              label={dept.displayName}
              icon={<span className="text-base leading-none">{dept.icon}</span>}
              isActive={pathname === `/chat/${dept.id}`}
            />
          ))}
        </SidebarSection>

        {/* Workspace */}
        <SidebarSection title="Workspace">
          <NavItem
            href="/dashboard"
            label="Dashboard"
            icon={<Rss className="h-4 w-4" />}
            isActive={pathname === '/dashboard'}
          />
          <NavItem
            href="/projects"
            label="Proyectos"
            icon={<FolderOpen className="h-4 w-4" />}
            isActive={pathname === '/projects'}
          />
          <NavItem
            href="/documents"
            label="Documentos"
            icon={<FileText className="h-4 w-4" />}
            isActive={pathname === '/documents'}
          />
        </SidebarSection>

        {/* Config */}
        <SidebarSection title="Config">
          <NavItem
            href="/agents"
            label="Agentes"
            icon={<Bot className="h-4 w-4" />}
            isActive={pathname === '/agents'}
          />
          <NavItem
            href="/connectors"
            label="Conectores"
            icon={<Plug className="h-4 w-4" />}
            isActive={pathname === '/connectors'}
          />
          <NavItem
            href="/settings"
            label="Settings"
            icon={<Settings className="h-4 w-4" />}
            isActive={pathname === '/settings'}
          />
        </SidebarSection>
      </nav>

      {/* User */}
      <div className="px-3 py-3 border-t border-border">
        <div className="flex items-center gap-2.5 px-2 py-2 rounded-md">
          <div className="relative">
            <div className="h-7 w-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">
              O
            </div>
            <span className="absolute bottom-0 right-0 h-2 w-2 rounded-full bg-emerald-500 ring-1 ring-card" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">Oscar</p>
            <p className="text-xs text-emerald-400">Online</p>
          </div>
        </div>
      </div>
    </aside>
  )
}
