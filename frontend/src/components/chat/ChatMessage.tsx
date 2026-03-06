import { useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { chatQueryOptions } from '#/queries/chat.queries'
import type {
  AnalysisTextMessage,
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

export function ChatMessage({
  question,
  onAccepted,
}: {
  question: string
  onAccepted: (
    result: ResultMessage,
    analysisResult?: PipelineAnalysisResult,
  ) => void
}) {
  const options = useMemo(() => chatQueryOptions(question), [question])
  const { error, data = [], isFetching } = useQuery(options)
  const calledRef = useRef(false)

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

  const analysisTextChunks = data.filter(
    (m): m is AnalysisTextMessage => m.type === 'analysis_text',
  )
  const analysisText = analysisTextChunks.map((m) => m.chunk).join('')
  const isStreamingNarrative =
    isFetching && analysisTextChunks.length > 0 && !result

  const toolInvocations = buildToolInvocations(toolCalls, toolResults)

  useEffect(() => {
    if (result?.accepted && !calledRef.current) {
      calledRef.current = true
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
      {(statusMessages.length > 0 || toolInvocations.length > 0 || error) && (
        <div className="space-y-2">
          <PipelineSteps
            steps={statusMessages}
            invocations={toolInvocations}
            isFetching={isFetching}
          />
          {error && (
            <p className="text-xs text-red-500 px-1">Error: {error.message}</p>
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
