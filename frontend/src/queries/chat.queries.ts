import {
  queryOptions,
  experimental_streamedQuery as streamedQuery,
} from '@tanstack/react-query'

export type StatusMessage = { type: 'status'; message: string }
export type ResultMessage = {
  type: 'result'
  accepted: boolean
  reason: string
  refined_query?: string | null
}
export type PipelineMessage = StatusMessage | ResultMessage

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
          const parsed = JSON.parse(line.slice(6)) as PipelineMessage
          yield parsed
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
