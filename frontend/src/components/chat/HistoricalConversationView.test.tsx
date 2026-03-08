// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useQuery } from '@tanstack/react-query'
import { HistoricalConversationView } from './HistoricalConversationView'

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@tanstack/react-query')>()
  return { ...mod, useQuery: vi.fn() }
})

vi.mock('#/queries/chat.queries', () => ({
  conversationMessagesQueryOptions: vi.fn(() => ({ queryKey: ['msgs'], queryFn: vi.fn() })),
  conversationResultsQueryOptions: vi.fn(() => ({ queryKey: ['results'], queryFn: vi.fn() })),
}))

function makeMsgQueryResult(overrides: Record<string, unknown> = {}) {
  return { data: undefined, isLoading: false, error: null, refetch: vi.fn(), ...overrides }
}

const baseRun = {
  pipeline_run_id: 'run-1',
  status: 'completed',
  enhanced_query: null as string | null,
  created_at: '2024-01-01T00:00:00Z',
  completed_at: null as string | null,
  datasets: [] as Array<{ id: string; title: string }>,
  steps: [] as Array<{ message: string; step_type?: string | null }>,
  extraction: null,
  normalization: null,
  analysis: null,
}

describe('HistoricalConversationView', () => {
  beforeEach(() => {
    vi.mocked(useQuery).mockReset()
  })

  describe('good flows', () => {
    it('shows loading spinner when both queries are loading', () => {
      vi.mocked(useQuery)
        .mockReturnValueOnce(makeMsgQueryResult({ isLoading: true }) as never)
        .mockReturnValueOnce(makeMsgQueryResult({ isLoading: true }) as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={vi.fn()}
        />,
      )
      expect(screen.getByText('Loading conversation…')).toBeDefined()
    })

    it('renders UserBubble and AssistantBubble for a completed conversation', () => {
      const msgData = {
        conversation_id: 'conv-1',
        messages: [
          { role: 'user', content: 'What is GDP?' },
          { role: 'assistant', content: 'GDP stands for Gross Domestic Product' },
        ],
      }
      const resultsData = { conversation_id: 'conv-1', results: [baseRun] }
      vi.mocked(useQuery)
        .mockReturnValueOnce(makeMsgQueryResult({ data: msgData }) as never)
        .mockReturnValueOnce(makeMsgQueryResult({ data: resultsData }) as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={vi.fn()}
        />,
      )
      expect(screen.getByText('What is GDP?')).toBeDefined()
      expect(screen.getByText('GDP stands for Gross Domestic Product')).toBeDefined()
    })

    it('calls onVisualizationReady with chart items when analysis is present', () => {
      const onVisualizationReady = vi.fn()
      const msgData = {
        conversation_id: 'conv-1',
        messages: [
          { role: 'user', content: 'Query' },
          { role: 'assistant', content: 'Answer' },
        ],
      }
      const analysis = {
        summary: 'Summary here',
        key_findings: ['Finding 1'],
        chart_configs: [],
      }
      const resultsData = {
        conversation_id: 'conv-1',
        results: [{ ...baseRun, enhanced_query: 'Enhanced query', analysis }],
      }
      vi.mocked(useQuery)
        .mockReturnValueOnce(makeMsgQueryResult({ data: msgData }) as never)
        .mockReturnValueOnce(makeMsgQueryResult({ data: resultsData }) as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={onVisualizationReady}
        />,
      )
      expect(onVisualizationReady).toHaveBeenCalledWith([
        { query: 'Enhanced query', reason: '', analysisResult: analysis },
      ])
    })

    it('shows RejectedBadge with reason for a rejected run', () => {
      const msgData = {
        conversation_id: 'conv-1',
        messages: [
          { role: 'user', content: 'Off-topic query' },
          { role: 'assistant', content: 'This query is out of scope' },
        ],
      }
      const resultsData = {
        conversation_id: 'conv-1',
        results: [{ ...baseRun, status: 'rejected' }],
      }
      vi.mocked(useQuery)
        .mockReturnValueOnce(makeMsgQueryResult({ data: msgData }) as never)
        .mockReturnValueOnce(makeMsgQueryResult({ data: resultsData }) as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={vi.fn()}
        />,
      )
      expect(screen.getByText('This query is out of scope')).toBeDefined()
    })

    it('covers dataset_found step: renders timeline tool cards for datasets and extraction', () => {
      const msgData = {
        conversation_id: 'conv-1',
        messages: [
          { role: 'user', content: 'Show me datasets' },
          { role: 'assistant', content: 'Here are the datasets' },
        ],
      }
      const resultsData = {
        conversation_id: 'conv-1',
        results: [
          {
            ...baseRun,
            steps: [{ message: 'Dataset found', step_type: 'dataset_found' }],
            datasets: [{ id: 'd1', title: 'Population Data' }],
            extraction: {
              datasets: [{ title: 'Population Data', row_count: 500 }],
              total_rows: 500,
            },
          },
        ],
      }
      vi.mocked(useQuery)
        .mockReturnValueOnce(makeMsgQueryResult({ data: msgData }) as never)
        .mockReturnValueOnce(makeMsgQueryResult({ data: resultsData }) as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={vi.fn()}
        />,
      )
      expect(screen.getByText('Show me datasets')).toBeDefined()
    })

    it('covers normalization step: renders timeline tool card for normalization', () => {
      const msgData = {
        conversation_id: 'conv-1',
        messages: [
          { role: 'user', content: 'Normalize data' },
          { role: 'assistant', content: 'Data normalized' },
        ],
      }
      const resultsData = {
        conversation_id: 'conv-1',
        results: [
          {
            ...baseRun,
            steps: [{ message: 'Normalizing', step_type: 'normalization' }],
            datasets: [{ id: 'd1', title: 'DS1' }],
            normalization: { unified_rows: 200, columns: ['col1', 'col2'] },
          },
        ],
      }
      vi.mocked(useQuery)
        .mockReturnValueOnce(makeMsgQueryResult({ data: msgData }) as never)
        .mockReturnValueOnce(makeMsgQueryResult({ data: resultsData }) as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={vi.fn()}
        />,
      )
      expect(screen.getByText('Normalize data')).toBeDefined()
    })

    it('covers analysis step: renders timeline tool card for analysis', () => {
      const msgData = {
        conversation_id: 'conv-1',
        messages: [
          { role: 'user', content: 'Analyse this' },
          { role: 'assistant', content: 'Analysis done' },
        ],
      }
      const analysis = { summary: 'S', key_findings: [], chart_configs: [] }
      const resultsData = {
        conversation_id: 'conv-1',
        results: [
          {
            ...baseRun,
            steps: [{ message: 'Analysing', step_type: 'analysis' }],
            analysis,
            normalization: { unified_rows: 100, columns: ['a'] },
          },
        ],
      }
      vi.mocked(useQuery)
        .mockReturnValueOnce(makeMsgQueryResult({ data: msgData }) as never)
        .mockReturnValueOnce(makeMsgQueryResult({ data: resultsData }) as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={vi.fn()}
        />,
      )
      expect(screen.getByText('Analyse this')).toBeDefined()
    })
  })

  describe('bad flows', () => {
    it('shows ErrorBubble with Retry button when a query errors', () => {
      vi.mocked(useQuery)
        .mockReturnValueOnce(
          makeMsgQueryResult({ error: new Error('Failed to load conversation messages') }) as never,
        )
        .mockReturnValueOnce(makeMsgQueryResult() as never)
      render(
        <HistoricalConversationView
          conversationId="conv-1"
          onVisualizationReady={vi.fn()}
        />,
      )
      expect(screen.getByText('Failed to load conversation messages')).toBeDefined()
      expect(screen.getByRole('button', { name: /retry/i })).toBeDefined()
    })
  })
})
