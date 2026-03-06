import { useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { chatQueryOptions } from '#/queries/chat.queries'
import type {
  AnalysisTextMessage,
  ConversationStartedMessage,
  ErrorMessage,
  PipelineAnalysisResult,
  ResultMessage,
  StatusMessage,
  ToolCallMessage,
  ToolResultMessage,
} from '#/queries/chat.queries'
import { PipelineSteps } from './PipelineSteps'
import { buildToolInvocations } from './types'

function AnalysisBubble({
  text,
  isStreaming,
}: {
  text: string
  isStreaming: boolean
}) {
  return (
    <div className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm bg-(--surface-strong) border border-(--line) leading-relaxed text-(--sea-ink) whitespace-pre-wrap">
      {text}
      {isStreaming && (
        <span className="inline-block w-0.5 h-4 bg-(--sea-ink) ml-0.5 align-text-bottom animate-pulse" />
      )}
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
  const { error, data = [], isFetching } = useQuery(options)
  const acceptedRef = useRef(false)
  const convStartedRef = useRef(false)

  const convStarted = data.find(
    (m): m is ConversationStartedMessage => m.type === 'conversation_started',
  )
  const statusMessages = data.filter(
    (m): m is StatusMessage => m.type === 'status',
  )
  const toolCalls = data.filter(
    (m): m is ToolCallMessage => m.type === 'tool_call',
  )
  const toolResults = data.filter(
    (m): m is ToolResultMessage => m.type === 'tool_result',
  )
  const result = data.find((m): m is ResultMessage => m.type === 'result')

  const analysisToolResult = toolResults.find(
    (r): r is ToolResultMessage & { tool: 'pipeline/analysis' } =>
      r.tool === 'pipeline/analysis',
  )

  const pipelineError = data.find((m): m is ErrorMessage => m.type === 'error')

  const analysisTextChunks = data.filter(
    (m): m is AnalysisTextMessage => m.type === 'analysis_text',
  )
  const analysisText = analysisTextChunks.map((m) => m.chunk).join('')
  const isStreamingNarrative =
    isFetching && analysisTextChunks.length > 0 && !result

  const toolInvocations = buildToolInvocations(toolCalls, toolResults)

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
      {/* User bubble */}
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm bg-[var(--lagoon-deep)] text-white">
          {question}
        </div>
      </div>

      {/* Pipeline status + tool cards + result */}
      {(statusMessages.length > 0 || toolInvocations.length > 0 || error || pipelineError || result) && (
        <div className="space-y-2">
          <PipelineSteps
            steps={statusMessages}
            invocations={toolInvocations}
            isFetching={isFetching}
          />
          {(error ?? pipelineError) && (
            <p className="text-xs text-red-500 px-1">
              Error: {error?.message ?? pipelineError?.message}
            </p>
          )}
          {result && !result.accepted && result.reason && (
            <RejectedBadge reason={result.reason} />
          )}
          {analysisText && (
            <AnalysisBubble
              text={analysisText}
              isStreaming={isStreamingNarrative}
            />
          )}
        </div>
      )}
    </div>
  )
}
