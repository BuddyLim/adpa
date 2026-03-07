import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  conversationMessagesQueryOptions,
  conversationResultsQueryOptions,
} from '#/queries/chat.queries'
import type { VisualizationData } from '#/components/visualization/VisualizationPanel'
import { PipelineSteps } from './PipelineSteps'
import { AssistantBubble, ErrorBubble, RejectedBadge, UserBubble } from './ChatBubbles'

export function HistoricalConversationView({
  conversationId,
  onVisualizationReady,
}: {
  conversationId: string
  onVisualizationReady: (items: VisualizationData[]) => void
}) {
  const { data: msgData, isLoading: loadingMsgs, error: msgsError, refetch: refetchMsgs } = useQuery(
    conversationMessagesQueryOptions(conversationId),
  )
  const { data: resultsData, isLoading: loadingResults, error: resultsError, refetch: refetchResults } = useQuery(
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

  const loadError = msgsError ?? resultsError
  const refetchAll = () => {
    if (msgsError) void refetchMsgs()
    if (resultsError) void refetchResults()
  }

  if (loadError && !loadingMsgs && !loadingResults) {
    return (
      <div className="py-4">
        <ErrorBubble
          message={loadError.message}
          onRetry={refetchAll}
        />
      </div>
    )
  }

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
    timeline: Array<
      | { kind: 'status'; message: string }
      | {
          kind: 'tool'
          tool: string
          args: unknown
          result: unknown
          pending: boolean
        }
    >
  }> = []

  let resultIdx = 0
  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i]
    if (msg.role !== 'user') continue

    const assistant =
      messages[i + 1]?.role === 'assistant' ? messages[i + 1] : undefined
    const run = results[resultIdx]
    resultIdx++

    const timeline: (typeof pairs)[number]['timeline'] = []

    for (const step of run.steps) {
      timeline.push({ kind: 'status', message: step.message })

      // Insert tool cards after the step that precedes them in the live stream
      if (step.step_type === 'dataset_found') {
        if (run.datasets.length > 0) {
          timeline.push({
            kind: 'tool',
            tool: 'coordinator/datasets_selected',
            args: {},
            result: { datasets: run.datasets.map((d) => d.title) },
            pending: false,
          })
        }
        if (run.extraction) {
          timeline.push({
            kind: 'tool',
            tool: 'pipeline/extraction',
            args: { datasets: run.extraction.datasets.map((d) => d.title) },
            result: {
              datasets: run.extraction.datasets,
              total_rows: run.extraction.total_rows,
            },
            pending: false,
          })
        }
      } else if (step.step_type === 'normalization' && run.normalization) {
        timeline.push({
          kind: 'tool',
          tool: 'pipeline/normalization',
          args: {
            n_sources: run.datasets.length,
            datasets: run.datasets.map((d) => d.title),
          },
          result: {
            unified_rows: run.normalization.unified_rows,
            columns: run.normalization.columns,
          },
          pending: false,
        })
      } else if (step.step_type === 'analysis' && run.analysis) {
        timeline.push({
          kind: 'tool',
          tool: 'pipeline/analysis',
          args: {
            unified_rows:
              run.normalization?.unified_rows ??
              run.extraction?.total_rows ??
              0,
            columns: run.normalization?.columns ?? [],
          },
          result: run.analysis,
          pending: false,
        })
      }
    }

    pairs.push({
      userContent: msg.content,
      assistantContent:
        run.status === 'rejected' ? undefined : assistant?.content,
      status: run.status,
      reason:
        run.status === 'rejected'
          ? (assistant?.content ?? 'Query was not accepted')
          : undefined,
      timeline,
    })
  }

  return (
    <div className="space-y-6">
      {pairs.map((pair, idx) => (
        <div key={idx} className="space-y-3">
          <UserBubble content={pair.userContent} />
          {pair.timeline.length > 0 && (
            <PipelineSteps
              timeline={
                pair.timeline as Parameters<typeof PipelineSteps>[0]['timeline']
              }
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
