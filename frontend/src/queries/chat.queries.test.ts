import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { chatQueryOptions } from './chat.queries'
import type { PipelineMessage } from './chat.queries'

describe('chatQueryOptions golden path', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('streams status then result messages and accumulates them via QueryClient', async () => {
    const messages: PipelineMessage[] = [
      { type: 'conversation_started', conversation_id: 'conv-456', title: 'What is GovTech?' },
      { type: 'status', message: 'Thinking...' },
      { type: 'result', accepted: true, reason: 'Valid query', refined_query: 'Valid query' },
    ]

    const sseMessages = messages.filter((m) => m.type !== 'conversation_started')
    const ssePayload = sseMessages
      .map((m) => `data: ${JSON.stringify(m)}`)
      .join('\n\n') + '\n\n'

    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(ssePayload))
        controller.close()
      },
    })

    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ task_id: 'test-123', conversation_id: 'conv-456', title: 'What is GovTech?' }),
            { status: 200 },
          ),
        )
        .mockResolvedValueOnce(new Response(stream, { status: 200 })),
    )

    const client = new QueryClient()
    const options = chatQueryOptions('What is GovTech?')

    expect(options.queryKey).toEqual(['chat', 'What is GovTech?', 'new'])

    const context = {
      client,
      queryKey: options.queryKey,
      meta: undefined,
      pageParam: undefined,
      direction: undefined,
      signal: new AbortController().signal,
    }

    await options.queryFn!(context as Parameters<NonNullable<typeof options.queryFn>>[0])

    const data = client.getQueryData<PipelineMessage[]>(options.queryKey)
    expect(data).toEqual(messages)

    const fetchMock = vi.mocked(fetch)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/query')
    expect(fetchMock.mock.calls[1][0]).toBe('http://localhost:8000/query/test-123/stream')
  })
})
