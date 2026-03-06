import type { ResultMessage } from '#/queries/chat.queries'

export function ResultBubble({ result }: { result: ResultMessage }) {
  if (!result.accepted) {
    return (
      <div className="rounded-xl px-4 py-3 text-sm bg-orange-50 border border-orange-200 text-orange-800 dark:bg-orange-950 dark:border-orange-800 dark:text-orange-200">
        <div className="flex gap-2">
          <span className="shrink-0">⚠</span>
          <p>{result.reason}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl px-4 py-3 text-xs bg-[var(--surface-strong)] border border-[var(--line)] space-y-1">
      {result.refined_query && (
        <p className="font-medium text-[var(--sea-ink)]">
          {result.refined_query}
        </p>
      )}
      {result.reason && (
        <p className="text-xs text-[var(--sea-ink-soft)]">{result.reason}</p>
      )}
    </div>
  )
}
