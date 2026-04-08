import type { Project } from '@/lib/types'
import { DEPT_MAP } from '@/lib/constants'
import { cn } from '@/lib/utils'

const SAMPLE_PROJECTS: Project[] = [
  { id: '1', title: 'Lanzamiento ProductHunt', deptId: 'cmo', status: 'in_progress', createdAt: '2026-03-20T10:00:00Z' },
  { id: '2', title: 'Pipeline Q2 — Outreach', deptId: 'sdr', status: 'in_progress', createdAt: '2026-03-22T09:00:00Z' },
  { id: '3', title: 'Cierre contrato Acme Corp', deptId: 'ae', status: 'in_progress', createdAt: '2026-03-25T14:00:00Z' },
  { id: '4', title: 'Reporte financiero Marzo', deptId: 'cfo', status: 'completed', createdAt: '2026-03-15T08:00:00Z' },
  { id: '5', title: 'Onboarding cliente TechStart', deptId: 'cs', status: 'completed', createdAt: '2026-03-10T11:00:00Z' },
  { id: '6', title: 'Automatización backoffice', deptId: 'coo', status: 'completed', createdAt: '2026-03-05T09:00:00Z' },
  { id: '7', title: 'Investigar integración Notion', deptId: 'orchestrator', status: 'inbox', createdAt: '2026-03-28T16:00:00Z' },
  { id: '8', title: 'Campaña email nurturing', deptId: 'cmo', status: 'inbox', createdAt: '2026-03-29T10:00:00Z' },
  { id: '9', title: 'Análisis churn Q1', deptId: 'cfo', status: 'inbox', createdAt: '2026-03-30T09:00:00Z' },
]

const COLUMNS: { status: Project['status']; label: string; color: string }[] = [
  { status: 'in_progress', label: 'En progreso', color: 'text-blue-400' },
  { status: 'completed', label: 'Completados', color: 'text-emerald-400' },
  { status: 'inbox', label: 'Inbox', color: 'text-muted-foreground' },
]

function ProjectCard({ project }: { project: Project }) {
  const dept = DEPT_MAP[project.deptId]
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3 hover:border-primary/40 transition-colors cursor-pointer group">
      <p className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
        {project.title}
      </p>
      <div className="flex items-center gap-2">
        <span className="text-sm">{dept?.icon}</span>
        <span className="text-xs text-muted-foreground">{dept?.displayName}</span>
      </div>
    </div>
  )
}

export default function ProjectsPage() {
  return (
    <div className="p-6 h-full">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Proyectos</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {SAMPLE_PROJECTS.length} proyectos en total
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6 h-[calc(100%-80px)]">
        {COLUMNS.map(({ status, label, color }) => {
          const projects = SAMPLE_PROJECTS.filter((p) => p.status === status)
          return (
            <div key={status} className="flex flex-col gap-3">
              <div className="flex items-center gap-2 pb-2 border-b border-border">
                <h2 className={cn('text-sm font-medium', color)}>{label}</h2>
                <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5">
                  {projects.length}
                </span>
              </div>
              <div className="flex flex-col gap-2 overflow-y-auto">
                {projects.map((project) => (
                  <ProjectCard key={project.id} project={project} />
                ))}
                {projects.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-8">Sin proyectos</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
