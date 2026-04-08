export type DeptId = 'orchestrator' | 'cmo' | 'sdr' | 'cfo' | 'cs' | 'ae' | 'coo'

export interface Department {
  id: DeptId
  displayName: string
  description: string
  icon: string
  color: string
  isActive: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  metadata?: Record<string, unknown>
}

export interface Conversation {
  id: string
  deptId: DeptId
  title: string
  updatedAt: string
  messages: Message[]
}

export interface Project {
  id: string
  title: string
  deptId: DeptId
  status: 'inbox' | 'in_progress' | 'completed' | 'archived'
  createdAt: string
}

export interface Task {
  id: string
  projectId: string
  title: string
  status: 'pending' | 'in_progress' | 'completed'
  assigneeType: 'agent' | 'oscar'
  priority: 'low' | 'medium' | 'high' | 'urgent'
}

export interface AgentRun {
  id: string
  deptId: DeptId
  status: 'running' | 'completed' | 'failed'
  model: string
  costUsd: number
  durationMs: number
  startedAt: string
}
