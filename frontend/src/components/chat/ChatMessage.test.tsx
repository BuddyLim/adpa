// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useQuery } from '@tanstack/react-query'
import { ChatMessage } from './ChatMessage'

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@tanstack/react-query')>()
  return { ...mod, useQuery: vi.fn() }
})

vi.mock('#/queries/chat.queries', () => ({
  chatQueryOptions: vi.fn(() => ({ queryKey: ['mock'], queryFn: vi.fn() })),
}))

function makeQueryResult(overrides: Record<string, unknown> = {}) {
  return {
    data: [] as unknown[],
    isFetching: false,
    error: null as Error | null,
    refetch: vi.fn(),
    ...overrides,
  }
}

describe('ChatMessage', () => {
  beforeEach(() => {
    vi.mocked(useQuery).mockReset()
  })

  describe('good flows', () => {
    it('always shows UserBubble with the question text', () => {
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({ isFetching: true }) as never)
      render(<ChatMessage question="What is GDP?" onAccepted={vi.fn()} />)
      expect(screen.getByText('What is GDP?')).toBeDefined()
    })

    it('shows LoadingBubble while fetching with no data', () => {
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({ isFetching: true }) as never)
      const { container } = render(<ChatMessage question="test" onAccepted={vi.fn()} />)
      const dots = container.querySelectorAll('span.animate-bounce')
      expect(dots.length).toBeGreaterThan(0)
    })

    it('shows AssistantBubble with streaming analysis text chunks', () => {
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({
        data: [
          { type: 'status', message: 'Searching datasets...' },
          { type: 'analysis_text', chunk: 'Hello ' },
          { type: 'analysis_text', chunk: 'world' },
        ],
        isFetching: true,
      }) as never)
      render(<ChatMessage question="test" onAccepted={vi.fn()} />)
      expect(screen.getByText('Hello world')).toBeDefined()
    })

    it('calls onAccepted when result is accepted', () => {
      const onAccepted = vi.fn()
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({
        data: [{ type: 'result', accepted: true, refined_query: 'refined query' }],
        isFetching: false,
      }) as never)
      render(<ChatMessage question="test" onAccepted={onAccepted} />)
      expect(onAccepted).toHaveBeenCalledOnce()
    })

    it('calls onConversationStarted when conversation_started message arrives', () => {
      const onConversationStarted = vi.fn()
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({
        data: [{ type: 'conversation_started', conversation_id: 'conv-123', title: 'My Chat' }],
        isFetching: false,
      }) as never)
      render(
        <ChatMessage
          question="test"
          onAccepted={vi.fn()}
          onConversationStarted={onConversationStarted}
        />,
      )
      expect(onConversationStarted).toHaveBeenCalledWith('conv-123', 'My Chat')
    })
  })

  describe('bad flows', () => {
    it('shows ErrorBubble with Retry button on network error', () => {
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({
        error: new Error('Network failure'),
        isFetching: false,
      }) as never)
      render(<ChatMessage question="test" onAccepted={vi.fn()} />)
      expect(screen.getByText('Network failure')).toBeDefined()
      expect(screen.getByRole('button', { name: /retry/i })).toBeDefined()
    })

    it('shows ErrorBubble when pipeline error message arrives', () => {
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({
        data: [{ type: 'error', message: 'Pipeline failed' }],
        isFetching: false,
      }) as never)
      render(<ChatMessage question="test" onAccepted={vi.fn()} />)
      expect(screen.getByText('Pipeline failed')).toBeDefined()
    })

    it('shows RejectedBadge with reason when result is rejected', () => {
      vi.mocked(useQuery).mockReturnValue(makeQueryResult({
        data: [{ type: 'result', accepted: false, reason: 'Out of scope' }],
        isFetching: false,
      }) as never)
      render(<ChatMessage question="test" onAccepted={vi.fn()} />)
      expect(screen.getByText('Out of scope')).toBeDefined()
    })
  })
})
