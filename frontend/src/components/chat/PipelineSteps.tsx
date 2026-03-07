import { useState } from 'react'
import { TOOL_COMPONENTS } from '#/components/tools'
import { TOOL_LABELS } from './types'
import type { TimelineItem } from './types'

function Spinner() {
  return (
    <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
  )
}

function CheckIcon() {
  return (
    <svg
      className="w-3 h-3 text-(--palm) shrink-0"
      viewBox="0 0 12 12"
      fill="currentColor"
    >
      <path d="M10 3L5 8.5 2 5.5l-1 1 4 4 6-7-1-1z" />
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg
      className="w-3 h-3 text-red-500 shrink-0"
      viewBox="0 0 12 12"
      fill="currentColor"
    >
      <path d="M6 1a5 5 0 100 10A5 5 0 006 1zm.75 7.5h-1.5v-1.5h1.5v1.5zm0-3h-1.5v-3h1.5v3z" />
    </svg>
  )
}

export function PipelineSteps({
  timeline,
  isFetching,
  isError = false,
}: {
  timeline: TimelineItem[]
  isFetching: boolean
  isError?: boolean
}) {
  const [expanded, setExpanded] = useState(true)
  if (timeline.length === 0) return null

  type ToolItem = Extract<TimelineItem, { kind: 'tool' }>
  const pendingTool = timeline.find(
    (item): item is ToolItem => item.kind === 'tool' && item.pending,
  )
  const lastCompletedTool = [...timeline]
    .reverse()
    .find((item): item is ToolItem => item.kind === 'tool' && !item.pending)
  const lastStatus = [...timeline]
    .filter((item) => item.kind === 'status')
    .at(-1)

  let headerText = lastStatus?.message ?? 'Working…'

  if (!isFetching) {
    if (isError) {
      headerText = 'Pipeline failed'
    } else {
      headerText = lastCompletedTool
        ? (TOOL_LABELS[lastCompletedTool.tool]?.done ?? 'Done')
        : 'Done'
    }
  } else if (pendingTool) {
    headerText = TOOL_LABELS[pendingTool.tool]?.pending ?? headerText
  }

  return (
    <div className="rounded-xl border border-(--line) overflow-hidden text-sm bg-(--surface-strong) shadow-sm">
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-(--sea-ink-soft) hover:bg-(--chip-bg) transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {isFetching ? <Spinner /> : isError ? <ErrorIcon /> : <CheckIcon />}
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
        <div className="px-3 pb-4 pt-1 space-y-2 border-t border-(--line)">
          {timeline.map((item, i) => {
            if (item.kind === 'status') {
              const isLastItem = i === timeline.length - 1
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-xs text-(--sea-ink-soft) py-1"
                >
                  {isLastItem && isFetching ? <Spinner /> : <CheckIcon />}
                  <span>{item.message}</span>
                </div>
              )
            }
            const Component = TOOL_COMPONENTS[item.tool]
            // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
            if (!Component) return null
            return (
              <Component
                key={`${item.tool}-${i}`}
                args={item.args}
                result={item.result}
                pending={item.pending}
                failed={item.failed}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
