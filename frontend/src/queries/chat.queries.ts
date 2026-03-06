'use client'

import {
  queryOptions,
  experimental_streamedQuery as streamedQuery,
} from '@tanstack/react-query'
import { z } from 'zod'

// ─── Per-tool arg schemas ─────────────────────────────────────────────────────
// To add a new tool: add its Args + Result schemas here, then add variants to
// ToolCallMessageSchema / ToolResultMessageSchema below, then create a card in
// tools/index.tsx.

const ListDatasetsArgsSchema = z.object({})
const DatasetsSelectedArgsSchema = z.object({})
const PipelineExtractionArgsSchema = z.object({
  datasets: z.array(z.string()),
})
const PipelineNormalizationArgsSchema = z.object({
  n_sources: z.number(),
  datasets: z.array(z.string()),
})

const PipelineAnalysisArgsSchema = z.object({
  unified_rows: z.number(),
  columns: z.array(z.string()),
})

export type ListDatasetsArgs = z.infer<typeof ListDatasetsArgsSchema>
export type DatasetsSelectedArgs = z.infer<typeof DatasetsSelectedArgsSchema>
export type PipelineExtractionArgs = z.infer<
  typeof PipelineExtractionArgsSchema
>
export type PipelineNormalizationArgs = z.infer<
  typeof PipelineNormalizationArgsSchema
>
export type PipelineAnalysisArgs = z.infer<typeof PipelineAnalysisArgsSchema>

// ─── Per-tool result schemas ──────────────────────────────────────────────────

const ListDatasetsResultSchema = z.array(
  z.object({
    title: z.string(),
    path: z.string(),
    description: z.string().optional(),
  }),
)

const DatasetsSelectedResultSchema = z.object({
  datasets: z.array(z.string()),
})

const PipelineExtractionResultSchema = z.object({
  datasets: z.array(z.object({ title: z.string(), row_count: z.number() })),
  total_rows: z.number(),
})

const PipelineNormalizationResultSchema = z.object({
  unified_rows: z.number(),
  columns: z.array(z.string()),
})

export const ChartConfigSchema = z.object({
  chart_type: z.enum(['bar', 'line', 'area', 'pie']),
  title: z.string(),
  description: z.string(),
  x_key: z.string().nullish(),
  y_keys: z.array(z.string()).default([]),
  x_label: z.string().nullish(),
  y_label: z.string().nullish(),
  series_labels: z.record(z.string(), z.string()).default({}),
  name_key: z.string().nullish(),
  value_key: z.string().nullish(),
  data: z.array(z.record(z.string(), z.unknown())),
  color: z.string().nullish(),
})

const PipelineAnalysisResultSchema = z.object({
  summary: z.string(),
  key_findings: z.array(z.string()),
  chart_configs: z.array(ChartConfigSchema),
})

export type ListDatasetsResult = z.infer<typeof ListDatasetsResultSchema>
export type DatasetsSelectedResult = z.infer<
  typeof DatasetsSelectedResultSchema
>
export type PipelineExtractionResult = z.infer<
  typeof PipelineExtractionResultSchema
>
export type PipelineNormalizationResult = z.infer<
  typeof PipelineNormalizationResultSchema
>
export type ChartConfig = z.infer<typeof ChartConfigSchema>
export type PipelineAnalysisResult = z.infer<
  typeof PipelineAnalysisResultSchema
>

// ─── Discriminated message schemas ────────────────────────────────────────────

const StatusMessageSchema = z.object({
  type: z.literal('status'),
  message: z.string(),
})

const ResultMessageSchema = z.object({
  type: z.literal('result'),
  accepted: z.boolean(),
  reason: z.string().optional(),
  refined_query: z.string().optional(),
})

const ToolCallMessageSchema = z.discriminatedUnion('tool', [
  z.object({
    type: z.literal('tool_call'),
    tool: z.literal('coordinator/list_datasets'),
    args: ListDatasetsArgsSchema,
  }),
  z.object({
    type: z.literal('tool_call'),
    tool: z.literal('coordinator/datasets_selected'),
    args: DatasetsSelectedArgsSchema,
  }),
  z.object({
    type: z.literal('tool_call'),
    tool: z.literal('pipeline/extraction'),
    args: PipelineExtractionArgsSchema,
  }),
  z.object({
    type: z.literal('tool_call'),
    tool: z.literal('pipeline/normalization'),
    args: PipelineNormalizationArgsSchema,
  }),
  z.object({
    type: z.literal('tool_call'),
    tool: z.literal('pipeline/analysis'),
    args: PipelineAnalysisArgsSchema,
  }),
])

const ToolResultMessageSchema = z.discriminatedUnion('tool', [
  z.object({
    type: z.literal('tool_result'),
    tool: z.literal('coordinator/list_datasets'),
    result: ListDatasetsResultSchema,
  }),
  z.object({
    type: z.literal('tool_result'),
    tool: z.literal('coordinator/datasets_selected'),
    result: DatasetsSelectedResultSchema,
  }),
  z.object({
    type: z.literal('tool_result'),
    tool: z.literal('pipeline/extraction'),
    result: PipelineExtractionResultSchema,
  }),
  z.object({
    type: z.literal('tool_result'),
    tool: z.literal('pipeline/normalization'),
    result: PipelineNormalizationResultSchema,
  }),
  z.object({
    type: z.literal('tool_result'),
    tool: z.literal('pipeline/analysis'),
    result: PipelineAnalysisResultSchema,
  }),
])

const AnalysisTextMessageSchema = z.object({
  type: z.literal('analysis_text'),
  chunk: z.string(),
})

const PipelineMessageSchema = z.union([
  StatusMessageSchema,
  ResultMessageSchema,
  ToolCallMessageSchema,
  ToolResultMessageSchema,
  AnalysisTextMessageSchema,
])

export type StatusMessage = z.infer<typeof StatusMessageSchema>
export type ResultMessage = z.infer<typeof ResultMessageSchema>
export type ToolCallMessage = z.infer<typeof ToolCallMessageSchema>
export type ToolResultMessage = z.infer<typeof ToolResultMessageSchema>
export type AnalysisTextMessage = z.infer<typeof AnalysisTextMessageSchema>
export type PipelineMessage = z.infer<typeof PipelineMessageSchema>

async function* chatAnswer(question: string): AsyncGenerator<PipelineMessage> {
  const initResponse = await fetch('http://localhost:8000/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!initResponse.ok) {
    throw new Error(`Chat request failed: ${initResponse.statusText}`)
  }

  const { task_id } = (await initResponse.json()) as { task_id: string }

  const streamResponse = await fetch(
    `http://localhost:8000/query/${task_id}/stream`,
  )

  if (!streamResponse.ok) {
    throw new Error(`Stream request failed: ${streamResponse.statusText}`)
  }

  const reader = streamResponse.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by double newlines
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''

    for (const event of events) {
      const line = event.trim()
      if (line.startsWith('data: ')) {
        try {
          const raw: unknown = JSON.parse(line.slice(6))
          const parsed = PipelineMessageSchema.safeParse(raw)
          console.log(parsed)
          if (parsed.success) yield parsed.data
        } catch {
          // ignore malformed events
        }
      }
    }
  }
}

export const chatQueryOptions = (question: string) =>
  queryOptions({
    queryKey: ['chat', question],
    queryFn: streamedQuery({
      streamFn: () => chatAnswer(question),
    }),
    staleTime: Infinity,
    retry: false,
  })
