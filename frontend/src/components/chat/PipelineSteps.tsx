import { useState } from 'react'
import type { StatusMessage } from '#/queries/chat.queries'
import { TOOL_COMPONENTS } from '#/components/tools'
import { TOOL_LABELS } from './types'
import type { ToolInvocation } from './types'

function Spinner() {
  return (
    <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
  )
}

function CheckIcon() {
  return (
    <svg
      className="w-3 h-3 text-[var(--palm)] shrink-0"
      viewBox="0 0 12 12"
      fill="currentColor"
    >
      <path d="M10 3L5 8.5 2 5.5l-1 1 4 4 6-7-1-1z" />
    </svg>
  )
}

export function PipelineSteps({
  steps,
  invocations,
  isFetching,
}: {
  steps: StatusMessage[]
  invocations: ToolInvocation[]
  isFetching: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  if (steps.length === 0 && invocations.length === 0) return null

  const pendingInvocation = invocations.find((inv) => inv.pending)
  const lastCompletedInvocation = [...invocations]
    .reverse()
    .find((inv) => !inv.pending)

  let headerText = steps.at(-1)?.message ?? 'Working…'

  if (!isFetching) {
    headerText = lastCompletedInvocation?.tool
      ? (TOOL_LABELS[lastCompletedInvocation.tool]?.done ?? 'Done')
      : 'Done'
  } else if (pendingInvocation) {
    headerText = TOOL_LABELS[pendingInvocation.tool]?.pending ?? headerText
  }

  return (
    <div className="rounded-xl border border-[var(--line)] overflow-hidden text-sm bg-[var(--surface-strong)] shadow-sm">
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-[var(--sea-ink-soft)] hover:bg-[var(--chip-bg)] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {isFetching ? <Spinner /> : <CheckIcon />}
        <span className="flex-1 text-xs font-medium">{headerText}</span>
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M2 4l4 4 4-4" />
        </svg>
      </button>
      {expanded && (
        <div className="px-3 pb-4 pt-1 space-y-2 border-t border-[var(--line)]">
          {steps.map((step, i) => (
            <div
              key={i}
              className="flex items-center gap-2 text-xs text-[var(--sea-ink-soft)] py-0.5"
            >
              {i === steps.length - 1 && isFetching ? (
                <Spinner />
              ) : (
                <CheckIcon />
              )}
              <span>{step.message}</span>
            </div>
          ))}
          {invocations.length > 0 && (
            <div className="space-y-2 pt-1">
              {invocations.map((inv, i) => {
                const Component = TOOL_COMPONENTS[inv.tool]
                // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
                if (!Component) return null
                return (
                  <Component
                    key={`${inv.tool}-${i}`}
                    args={inv.args}
                    result={inv.result}
                    pending={inv.pending}
                  />
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
