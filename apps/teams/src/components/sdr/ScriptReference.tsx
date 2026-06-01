'use client'

import { useState } from 'react'
import { BookOpen, Copy, ChevronDown, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { getScriptForCampaign } from '@/lib/sdr/scripts'
import { useCallSessionStore } from '@/store/useCallSessionStore'

export function ScriptReference() {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set(['apertura']))
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const campaign = useCallSessionStore((s) => s.campaign)
  const campaigns = useCallSessionStore((s) => s.campaigns)
  const sections = getScriptForCampaign(campaign)
  const campaignLabel =
    campaigns.find((c) => c.id === campaign)?.label ?? 'Guion genérico'

  function toggle(id: string) {
    setOpenIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function copySection(id: string, body: string) {
    try {
      await navigator.clipboard.writeText(body)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 1500)
    } catch {
      /* ignore */
    }
  }

  const filtered = query.trim()
    ? sections.filter(
        (s) =>
          s.title.toLowerCase().includes(query.toLowerCase()) ||
          s.body.toLowerCase().includes(query.toLowerCase())
      )
    : sections

  return (
    <aside className="w-80 shrink-0 border-l border-border bg-card flex flex-col h-full">
      <div className="h-14 px-4 border-b border-border flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-brand-purple-dark" />
        <div>
          <p className="tag-label text-brand-purple-dark">Script SDR</p>
          <p className="text-xs text-muted-foreground leading-tight">
            {campaignLabel}
          </p>
        </div>
      </div>

      <div className="p-3 border-b border-border">
        <input
          type="text"
          placeholder="Buscar objeción, palabra..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full h-9 rounded-lg border border-border-strong bg-input px-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent"
        />
      </div>

      <ScrollArea className="flex-1">
        <div className="p-3 space-y-2">
          {filtered.map((section) => {
            const isOpen = openIds.has(section.id) || query.trim().length > 0
            const copied = copiedId === section.id
            return (
              <div
                key={section.id}
                className="rounded-xl border border-border bg-card overflow-hidden"
              >
                <button
                  onClick={() => toggle(section.id)}
                  className="w-full p-3 flex items-center justify-between gap-2 text-left text-sm hover:bg-accent transition-colors"
                >
                  <span className="font-semibold text-brand-dark">
                    {section.title}
                  </span>
                  <ChevronDown
                    className={cn(
                      'h-4 w-4 transition-transform text-muted-foreground',
                      isOpen && 'rotate-180'
                    )}
                  />
                </button>
                {isOpen && (
                  <div className="px-3 pb-3 space-y-2 border-t border-border bg-brand-cream/40">
                    <pre className="text-xs whitespace-pre-wrap font-sans text-brand-dark/85 leading-relaxed pt-2">
                      {section.body}
                    </pre>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 text-xs"
                      onClick={() => copySection(section.id, section.body)}
                    >
                      {copied ? (
                        <>
                          <Check className="h-3 w-3" /> Copiado
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3" /> Copiar
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </div>
            )
          })}
          {filtered.length === 0 && (
            <div className="text-xs text-muted-foreground p-4 text-center">
              Sin resultados para “{query}”.
            </div>
          )}
        </div>
      </ScrollArea>
    </aside>
  )
}
