import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import {
  chatQueryOptions,
  conversationMessagesQueryOptions,
  conversationResultsQueryOptions,
} from './chat.queries'
import type { PipelineMessage } from './chat.queries'

// ─── chatQueryOptions ─────────────────────────────────────────────────────────

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
    const ssePayload =
      sseMessages.map((m) => `data: ${JSON.stringify(m)}`).join('\n\n') + '\n\n'

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

describe('chatQueryOptions bad flows', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  function makeContext(client: QueryClient, options: ReturnType<typeof chatQueryOptions>) {
    return {
      client,
      queryKey: options.queryKey,
      meta: undefined,
      pageParam: undefined,
      direction: undefined,
      signal: new AbortController().signal,
    } as Parameters<NonNullable<typeof options.queryFn>>[0]
  }

  it('rejects when initial POST returns a non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(
        new Response('Internal Server Error', { status: 500, statusText: 'Internal Server Error' }),
      ),
    )

    const client = new QueryClient()
    const options = chatQueryOptions('test question')
    await expect(options.queryFn!(makeContext(client, options))).rejects.toThrow(
      'Chat request failed',
    )
  })

  it('rejects when SSE stream endpoint returns a non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ task_id: 'task-1', conversation_id: 'conv-1', title: null }),
            { status: 200 },
          ),
        )
        .mockResolvedValueOnce(
          new Response('Service Unavailable', { status: 503, statusText: 'Service Unavailable' }),
        ),
    )

    const client = new QueryClient()
    const options = chatQueryOptions('test question')
    await expect(options.queryFn!(makeContext(client, options))).rejects.toThrow(
      'Stream request failed',
    )
  })

  it('rejects when SSE stream response has no body', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ task_id: 'task-1', conversation_id: 'conv-1', title: null }),
            { status: 200 },
          ),
        )
        .mockResolvedValueOnce({ ok: true, body: null } as Response),
    )

    const client = new QueryClient()
    const options = chatQueryOptions('test question')
    await expect(options.queryFn!(makeContext(client, options))).rejects.toThrow(
      'Stream response has no body',
    )
  })

  it('skips malformed SSE lines and still accumulates valid messages', async () => {
    const validMessage: PipelineMessage = { type: 'status', message: 'Valid status' }
    const ssePayload =
      `data: not-json-at-all\n\n` +
      `data: {"broken": }\n\n` +
      `data: ${JSON.stringify(validMessage)}\n\n`

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
            JSON.stringify({ task_id: 'task-2', conversation_id: 'conv-2', title: null }),
            { status: 200 },
          ),
        )
        .mockResolvedValueOnce(new Response(stream, { status: 200 })),
    )

    const client = new QueryClient()
    const options = chatQueryOptions('test question')
    const context = makeContext(client, options)
    await options.queryFn!(context)

    const data = client.getQueryData<PipelineMessage[]>(options.queryKey)
    // conversation_started injected first, then only the valid status message
    expect(data).toContainEqual(validMessage)
    expect(data?.filter((m) => m.type === 'status')).toHaveLength(1)
  })

  it('includes conversationId in the query key when provided', () => {
    const options = chatQueryOptions('question', 'conv-abc')
    expect(options.queryKey).toEqual(['chat', 'question', 'conv-abc'])
  })
})

// ─── conversationMessagesQueryOptions ────────────────────────────────────────

describe('conversationMessagesQueryOptions', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches and returns conversation messages on success', async () => {
    const responseBody = {
      conversation_id: 'conv-1',
      messages: [
        { role: 'user', content: 'Hello' },
        { role: 'assistant', content: 'Hi there' },
      ],
    }

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(responseBody), { status: 200 })),
    )

    const options = conversationMessagesQueryOptions('conv-1')
    expect(options.queryKey).toEqual(['conversation-messages', 'conv-1'])

    const client = new QueryClient()
    const context = {
      client,
      queryKey: options.queryKey,
      meta: undefined,
      pageParam: undefined,
      direction: undefined,
      signal: new AbortController().signal,
    } as Parameters<NonNullable<typeof options.queryFn>>[0]

    const result = await options.queryFn!(context)
    expect(result).toEqual(responseBody)
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe(
      'http://localhost:8000/conversations/conv-1/messages',
    )
  })

  it('rejects when the messages endpoint returns a non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(new Response('Not Found', { status: 404 })),
    )

    const options = conversationMessagesQueryOptions('conv-1')
    const client = new QueryClient()
    const context = {
      client,
      queryKey: options.queryKey,
      meta: undefined,
      pageParam: undefined,
      direction: undefined,
      signal: new AbortController().signal,
    } as Parameters<NonNullable<typeof options.queryFn>>[0]

    await expect(options.queryFn!(context)).rejects.toThrow(
      'Failed to load conversation messages',
    )
  })
})

// ─── conversationResultsQueryOptions ─────────────────────────────────────────

describe('conversationResultsQueryOptions', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches and returns conversation results on success', async () => {
    const responseBody = {
      conversation_id: 'conv-1',
      results: [
        {
          pipeline_run_id: 'run-1',
          status: 'completed',
          enhanced_query: 'What is X?',
          created_at: '2024-01-01T00:00:00Z',
          completed_at: '2024-01-01T00:01:00Z',
          datasets: [{ id: 'ds-1', title: 'Dataset A' }],
          steps: [],
          extraction: null,
          normalization: null,
          analysis: null,
        },
      ],
    }

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(responseBody), { status: 200 })),
    )

    const options = conversationResultsQueryOptions('conv-1')
    expect(options.queryKey).toEqual(['conversation-results', 'conv-1'])

    const client = new QueryClient()
    const context = {
      client,
      queryKey: options.queryKey,
      meta: undefined,
      pageParam: undefined,
      direction: undefined,
      signal: new AbortController().signal,
    } as Parameters<NonNullable<typeof options.queryFn>>[0]

    const result = await options.queryFn!(context)
    expect(result).toEqual(responseBody)
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe(
      'http://localhost:8000/conversations/conv-1/results',
    )
  })

  it('rejects when the results endpoint returns a non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(new Response('Server Error', { status: 500 })),
    )

    const options = conversationResultsQueryOptions('conv-1')
    const client = new QueryClient()
    const context = {
      client,
      queryKey: options.queryKey,
      meta: undefined,
      pageParam: undefined,
      direction: undefined,
      signal: new AbortController().signal,
    } as Parameters<NonNullable<typeof options.queryFn>>[0]

    await expect(options.queryFn!(context)).rejects.toThrow(
      'Failed to load conversation results',
    )
  })
})
