import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  deptIcon?: string
}

export default function MessageBubble({ role, content, deptIcon }: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      {!isUser && (
        <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-base shrink-0 mt-0.5">
          {deptIcon ?? '🤖'}
        </div>
      )}

      {/* Bubble */}
      <div
        className={cn(
          'max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : 'bg-card border border-border text-foreground rounded-tl-sm'
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose prose-sm prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const isInline = !className
                  return isInline ? (
                    <code
                      className="bg-muted px-1 py-0.5 rounded text-xs font-mono text-foreground"
                      {...props}
                    >
                      {children}
                    </code>
                  ) : (
                    <code
                      className={cn(
                        'block bg-muted/50 rounded-md p-3 text-xs font-mono overflow-x-auto',
                        className
                      )}
                      {...props}
                    >
                      {children}
                    </code>
                  )
                },
                p({ children }) {
                  return <p className="mb-2 last:mb-0">{children}</p>
                },
                ul({ children }) {
                  return <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>
                },
                ol({ children }) {
                  return <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}
