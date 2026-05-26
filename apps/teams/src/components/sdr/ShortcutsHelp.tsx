'use client'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface ShortcutsHelpProps {
  open: boolean
  onOpenChange: (v: boolean) => void
}

const SHORTCUTS: { keys: string[]; desc: string }[] = [
  { keys: ['C'], desc: 'Iniciar llamada (cuando hay prospecto activo)' },
  { keys: ['H', 'Esc'], desc: 'Terminar llamada (mostrar formulario)' },
  { keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'], desc: 'Seleccionar disposition por número' },
  { keys: ['S'], desc: 'Guardar formulario' },
  { keys: ['N'], desc: 'Siguiente prospecto (pide confirmación si hay llamada activa)' },
  { keys: ['?'], desc: 'Mostrar esta ayuda' },
]

export function ShortcutsHelp({ open, onOpenChange }: ShortcutsHelpProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Atajos de teclado</DialogTitle>
          <DialogDescription>
            Activos solo cuando ningún campo de texto tiene el foco.
          </DialogDescription>
        </DialogHeader>
        <table className="w-full text-sm">
          <tbody>
            {SHORTCUTS.map((s, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                <td className="py-2 pr-3 align-top w-40">
                  {s.keys.map((k, j) => (
                    <kbd
                      key={j}
                      className="px-1.5 py-0.5 mr-1 text-[10px] rounded bg-muted border border-border font-mono"
                    >
                      {k}
                    </kbd>
                  ))}
                </td>
                <td className="py-2 text-muted-foreground">{s.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DialogContent>
    </Dialog>
  )
}
