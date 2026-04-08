import { TrendingDown, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'

interface KpiCardProps {
  title: string
  value: string
  subtitle?: string
  icon?: React.ReactNode
  trend?: {
    value: number
    positive: boolean
  }
}

export default function KpiCard({ title, value, subtitle, icon, trend }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
        {icon && (
          <div className="h-7 w-7 rounded-md bg-muted flex items-center justify-center text-muted-foreground">
            {icon}
          </div>
        )}
      </div>

      {/* Value */}
      <div>
        <p className="text-2xl font-bold text-foreground tracking-tight">{value}</p>
        {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>

      {/* Trend */}
      {trend && (
        <div
          className={cn(
            'flex items-center gap-1 text-xs font-medium',
            trend.positive ? 'text-emerald-400' : 'text-red-400'
          )}
        >
          {trend.positive ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          <span>{trend.value}% vs ayer</span>
        </div>
      )}
    </div>
  )
}
