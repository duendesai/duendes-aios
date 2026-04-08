import type { Department, DeptId } from './types'

export const DEPARTMENTS: Department[] = [
  {
    id: 'orchestrator',
    displayName: 'Orquestador',
    description: 'Router central',
    icon: '🧠',
    color: '#8B5CF6',
    isActive: true,
  },
  {
    id: 'cmo',
    displayName: 'CMO',
    description: 'Marketing y contenido',
    icon: '📣',
    color: '#EC4899',
    isActive: true,
  },
  {
    id: 'sdr',
    displayName: 'SDR',
    description: 'Captación y leads',
    icon: '🎯',
    color: '#F59E0B',
    isActive: true,
  },
  {
    id: 'cfo',
    displayName: 'CFO',
    description: 'Finanzas',
    icon: '💰',
    color: '#10B981',
    isActive: true,
  },
  {
    id: 'cs',
    displayName: 'CS',
    description: 'Clientes',
    icon: '🤝',
    color: '#06B6D4',
    isActive: true,
  },
  {
    id: 'ae',
    displayName: 'AE',
    description: 'Ventas y demos',
    icon: '🚀',
    color: '#F97316',
    isActive: true,
  },
  {
    id: 'coo',
    displayName: 'COO',
    description: 'Operaciones',
    icon: '⚙️',
    color: '#6366F1',
    isActive: true,
  },
]

export const DEPT_MAP = Object.fromEntries(
  DEPARTMENTS.map((d) => [d.id, d])
) as Record<DeptId, Department>
