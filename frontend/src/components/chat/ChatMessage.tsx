import { useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { chatQueryOptions } from '#/queries/chat.queries'
import type {
  AnalysisTextMessage,
  ConversationStartedMessage,
  ErrorMessage,
  PipelineAnalysisResult,
  ResultMessage,
  ToolResultMessage,
} from '#/queries/chat.queries'
import { PipelineSteps } from './PipelineSteps'
import { buildTimeline } from './types'
import { AssistantBubble, ErrorBubble, LoadingBubble, RejectedBadge, UserBubble } from './ChatBubbles'

export function ChatMessage({
  question,
  conversationId,
  onAccepted,
  onConversationStarted,
}: {
  question: string
  conversationId?: string | null
  onAccepted: (
    result: ResultMessage,
    analysisResult?: PipelineAnalysisResult,
  ) => void
  onConversationStarted?: (id: string, title: string | null) => void
}) {
  const options = useMemo(
    () => chatQueryOptions(question, conversationId),
    [question, conversationId],
  )
  const { error, data = [], isFetching, refetch } = useQuery(options)
  const acceptedRef = useRef(false)
  const convStartedRef = useRef(false)

  const convStarted = data.find(
    (m): m is ConversationStartedMessage => m.type === 'conversation_started',
  )
  const result = data.find((m): m is ResultMessage => m.type === 'result')
  const rejected = result != null && !result.accepted
  const timeline = buildTimeline(data, rejected)

  const analysisToolResult = data
    .filter((m): m is ToolResultMessage => m.type === 'tool_result')
    .find(
      (r): r is ToolResultMessage & { tool: 'pipeline/analysis' } =>
        r.tool === 'pipeline/analysis',
    )

  const pipelineError = data.find((m): m is ErrorMessage => m.type === 'error')

  const analysisTextChunks = data.filter(
    (m): m is AnalysisTextMessage => m.type === 'analysis_text',
  )
  const analysisText = analysisTextChunks.map((m) => m.chunk).join('')

  useEffect(() => {
    if (convStarted && !convStartedRef.current) {
      convStartedRef.current = true
      onConversationStarted?.(convStarted.conversation_id, convStarted.title)
    }
  }, [convStarted, onConversationStarted])

  useEffect(() => {
    if (result?.accepted && !acceptedRef.current) {
      acceptedRef.current = true
      onAccepted(result, analysisToolResult?.result)
    }
  }, [result, analysisToolResult, onAccepted])

  return (
    <div className="space-y-6">
      <UserBubble content={question} />

      {/* Loading bubble while waiting for first visible pipeline event */}
      {isFetching &&
        timeline.length === 0 &&
        !result &&
        !pipelineError &&
        !error && <LoadingBubble />}

      {/* Pipeline status + tool cards + result */}
      {(timeline.length > 0 || error || pipelineError || result) && (
        <div className="space-y-2">
          <PipelineSteps
            timeline={timeline}
            isFetching={isFetching}
            isError={!isFetching && !!(error ?? pipelineError ?? rejected)}
          />
          {!isFetching && (error ?? pipelineError) && (
            <ErrorBubble
              message={error?.message ?? pipelineError?.message ?? 'An unexpected error occurred'}
              onRetry={() => void refetch()}
            />
          )}
          {result && !result.accepted && result.reason && (
            <RejectedBadge reason={result.reason} />
          )}
          {(isFetching && !pipelineError && !error || analysisText) && (
            <AssistantBubble
              content={analysisText}
              isStreaming={isFetching && !result}
            />
          )}
        </div>
      )}
    </div>
  )
}
