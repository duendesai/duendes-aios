import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Activity, Bot, DollarSign, FolderOpen, ListTodo } from 'lucide-react'
import DeptStatusCard from '@/components/dashboard/dept-status-card'
import KpiCard from '@/components/dashboard/kpi-card'
import { DEPARTMENTS } from '@/lib/constants'

const recentActivity = [
  { id: '1', text: 'CMO publicó hilo en Twitter sobre lanzamiento', time: 'hace 12 min', dept: '📣' },
  { id: '2', text: 'SDR calificó 3 leads nuevos de ProductHunt', time: 'hace 28 min', dept: '🎯' },
  { id: '3', text: 'CFO generó reporte de gastos de marzo', time: 'hace 1 h', dept: '💰' },
  { id: '4', text: 'CS respondió ticket #124 — Integración Slack', time: 'hace 2 h', dept: '🤝' },
  { id: '5', text: 'AE agendó demo con Acme Corp para el jueves', time: 'hace 3 h', dept: '🚀' },
]

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Buenos días'
  if (hour < 18) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function DashboardPage() {
  const today = format(new Date(), "EEEE d 'de' MMMM", { locale: es })
  const todayCapitalized = today.charAt(0).toUpperCase() + today.slice(1)

  return (
    <div className="p-6 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-foreground">
          {getGreeting()}, Oscar
        </h1>
        <p className="text-muted-foreground mt-1">{todayCapitalized}</p>
      </div>

      {/* KPI Grid */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Resumen
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            title="Proyectos activos"
            value="12"
            subtitle="3 actualizados hoy"
            icon={<FolderOpen className="h-4 w-4" />}
            trend={{ value: 2, positive: true }}
          />
          <KpiCard
            title="Tareas pendientes"
            value="34"
            subtitle="8 de alta prioridad"
            icon={<ListTodo className="h-4 w-4" />}
            trend={{ value: 5, positive: false }}
          />
          <KpiCard
            title="Agentes corriendo"
            value="5"
            subtitle="De 7 disponibles"
            icon={<Bot className="h-4 w-4" />}
          />
          <KpiCard
            title="Costo hoy"
            value="$2.41"
            subtitle="Presupuesto: $10/día"
            icon={<DollarSign className="h-4 w-4" />}
            trend={{ value: 12, positive: true }}
          />
        </div>
      </section>

      {/* Agents */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Agentes
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
          {DEPARTMENTS.map((dept) => (
            <DeptStatusCard key={dept.id} department={dept} />
          ))}
        </div>
      </section>

      {/* Recent Activity */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Actividad reciente
        </h2>
        <div className="rounded-lg border border-border bg-card divide-y divide-border">
          {recentActivity.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 px-4 py-3 hover:bg-accent/40 transition-colors"
            >
              <Activity className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <span className="text-sm mr-2">{item.dept}</span>
              <span className="text-sm text-foreground flex-1">{item.text}</span>
              <span className="text-xs text-muted-foreground shrink-0">{item.time}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
