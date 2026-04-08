import Link from 'next/link'
import type { Department } from '@/lib/types'
import { Badge } from '@/components/ui/badge'

interface DeptStatusCardProps {
  department: Department
  lastActivity?: string
}

export default function DeptStatusCard({
  department,
  lastActivity = 'hace 5 min',
}: DeptStatusCardProps) {
  return (
    <Link href={`/chat/${department.id}`}>
      <div className="rounded-lg border border-border bg-card p-4 space-y-3 hover:border-primary/40 hover:bg-card/80 transition-all cursor-pointer group">
        {/* Icon */}
        <div
          className="h-10 w-10 rounded-xl flex items-center justify-center text-xl"
          style={{ backgroundColor: `${department.color}20` }}
        >
          {department.icon}
        </div>

        {/* Name + Status */}
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-1">
            <p className="text-sm font-medium text-foreground group-hover:text-primary transition-colors truncate">
              {department.displayName}
            </p>
          </div>
          <p className="text-xs text-muted-foreground truncate">{department.description}</p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between">
          <Badge variant={department.isActive ? 'success' : 'secondary'}>
            {department.isActive ? 'Activo' : 'Inactivo'}
          </Badge>
          <span className="text-[10px] text-muted-foreground/60">{lastActivity}</span>
        </div>
      </div>
    </Link>
  )
}
