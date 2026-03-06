import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  conversationMessagesQueryOptions,
  conversationResultsQueryOptions,
} from '#/queries/chat.queries'
import type { VisualizationData } from '#/components/visualization/VisualizationPanel'
import { PipelineSteps } from './PipelineSteps'
import type { ToolInvocation } from './types'

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm bg-[var(--lagoon-deep)] text-white">
        {content}
      </div>
    </div>
  )
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm bg-(--surface-strong) border border-(--line) leading-relaxed text-(--sea-ink) whitespace-pre-wrap">
      {content}
    </div>
  )
}

function RejectedBadge({ reason }: { reason: string }) {
  return (
    <div className="flex items-start gap-2 rounded-xl px-3 py-2.5 bg-amber-50 border border-amber-200 text-xs text-amber-800">
      <span className="shrink-0 mt-0.5">⚠</span>
      <span>{reason}</span>
    </div>
  )
}

export function HistoricalConversationView({
  conversationId,
  onVisualizationReady,
}: {
  conversationId: string
  onVisualizationReady: (items: VisualizationData[]) => void
}) {
  const { data: msgData, isLoading: loadingMsgs } = useQuery(
    conversationMessagesQueryOptions(conversationId),
  )
  const { data: resultsData, isLoading: loadingResults } = useQuery(
    conversationResultsQueryOptions(conversationId),
  )

  // Push charts to visualization panel once results are loaded
  useEffect(() => {
    if (!resultsData) return
    const items: VisualizationData[] = resultsData.results
      .filter((r) => r.status === 'completed' && r.analysis)
      .map((r) => ({
        query: r.enhanced_query ?? '',
        reason: '',
        analysisResult: r.analysis ?? undefined,
      }))
    onVisualizationReady(items)
  }, [resultsData, onVisualizationReady])

  if (loadingMsgs || loadingResults) {
    return (
      <div className="flex items-center justify-center flex-1 py-12">
        <div className="flex items-center gap-2 text-sm text-(--sea-ink-soft)">
          <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          Loading conversation…
        </div>
      </div>
    )
  }

  const messages = msgData?.messages ?? []
  const results = resultsData?.results ?? []

  // Build a merged timeline: pair user messages with their pipeline run result
  // Messages are ordered: [user, assistant, user, assistant, ...]
  // Results are in the same order as pipeline runs
  const pairs: Array<{
    userContent: string
    assistantContent?: string
    status?: string
    reason?: string
    statusSteps: Array<{ type: 'status'; message: string }>
    invocations: ToolInvocation[]
  }> = []

  let resultIdx = 0
  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i]
    if (msg.role !== 'user') continue

    const assistant =
      messages[i + 1]?.role === 'assistant' ? messages[i + 1] : undefined
    const run = results[resultIdx]
    resultIdx++

    const statusSteps = run.steps.map((s) => ({
      type: 'status' as const,
      message: s.message,
    }))

    const invocations: ToolInvocation[] = []
    if (run.datasets.length > 0) {
      invocations.push({
        tool: 'coordinator/datasets_selected',
        args: {},
        result: { datasets: run.datasets.map((d) => d.title) },
        pending: false,
      })
    }
    if (run.analysis) {
      invocations.push({
        tool: 'pipeline/analysis',
        args: { unified_rows: 0, columns: [] },
        result: run.analysis,
        pending: false,
      })
    }

    pairs.push({
      userContent: msg.content,
      assistantContent: run.status === 'rejected' ? undefined : assistant?.content,
      status: run.status,
      reason:
        run.status === 'rejected'
          ? (assistant?.content ?? 'Query was not accepted')
          : undefined,
      statusSteps,
      invocations,
    })
  }

  return (
    <div className="space-y-6">
      {pairs.map((pair, idx) => (
        <div key={idx} className="space-y-3">
          <UserBubble content={pair.userContent} />
          {(pair.statusSteps.length > 0 || pair.invocations.length > 0) && (
            <PipelineSteps
              steps={pair.statusSteps}
              invocations={pair.invocations}
              isFetching={false}
            />
          )}
          {pair.status === 'rejected' && pair.reason && (
            <RejectedBadge reason={pair.reason} />
          )}
          {pair.assistantContent && (
            <AssistantBubble content={pair.assistantContent} />
          )}
        </div>
      ))}
    </div>
  )
}
