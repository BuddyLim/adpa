export function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-xs bg-(--lagoon-deep) text-white">
        {content}
      </div>
    </div>
  )
}

export function AssistantBubble({
  content,
  isStreaming = false,
}: {
  content: string
  isStreaming?: boolean
}) {
  if (!content && isStreaming) {
    return (
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm px-4 py-3 w-fit bg-(--surface-strong) border border-(--line)">
        <span className="w-1 h-1 rounded-full bg-(--sea-ink-soft) animate-bounce [animation-delay:-0.3s]" />
        <span className="w-1 h-1 rounded-full bg-(--sea-ink-soft) animate-bounce [animation-delay:-0.15s]" />
        <span className="w-1 h-1 rounded-full bg-(--sea-ink-soft) animate-bounce" />
      </div>
    )
  }

  return (
    <div className="rounded-2xl rounded-tl-sm px-4 py-3 text-xs bg-(--surface-strong) border border-(--line) leading-relaxed text-(--sea-ink) whitespace-pre-wrap">
      {content}
      {isStreaming && (
        <span className="inline-block w-0.5 h-4 bg-(--sea-ink) ml-0.5 align-text-bottom animate-pulse" />
      )}
    </div>
  )
}

export function RejectedBadge({ reason }: { reason: string }) {
  return (
    <div className="flex items-start gap-2 rounded-xl px-3 py-2.5 bg-amber-50 border border-amber-200 text-xs text-amber-800">
      <span className="shrink-0 mt-0.5">⚠</span>
      <span>{reason}</span>
    </div>
  )
}

export function ErrorBubble({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="flex items-start gap-2 rounded-xl px-3 py-2.5 bg-red-50 border border-red-200 text-xs text-red-800">
      <span className="shrink-0 mt-0.5">✕</span>
      <div className="flex-1 min-w-0">
        <p className="font-medium">Something went wrong</p>
        <p className="text-red-600 mt-0.5 wrap-break-word">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 ml-1 px-2 py-1 rounded-lg text-xs font-medium bg-red-100 hover:bg-red-200 text-red-700 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function LoadingBubble() {
  return (
    <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm px-4 py-3 w-fit bg-(--surface-strong) border border-(--line)">
      <span className="w-1 h-1 rounded-full bg-(--sea-ink-soft) animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1 h-1 rounded-full bg-(--sea-ink-soft) animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1 h-1 rounded-full bg-(--sea-ink-soft) animate-bounce" />
    </div>
  )
}
