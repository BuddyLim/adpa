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
      { type: 'status', message: 'Thinking...' },
      { type: 'result', accepted: true, reason: 'Valid query', refined_query: null },
    ]

    const ssePayload = messages
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
          new Response(JSON.stringify({ task_id: 'test-123' }), { status: 200 }),
        )
        .mockResolvedValueOnce(new Response(stream, { status: 200 })),
    )

    const client = new QueryClient()
    const options = chatQueryOptions('What is GovTech?')

    expect(options.queryKey).toEqual(['chat', 'What is GovTech?'])

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
