import {
  queryOptions,
  experimental_streamedQuery as streamedQuery,
} from '@tanstack/react-query'

async function* chatAnswer(question: string) {
  const initResponse = await fetch('http://localhost:8000/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!initResponse.ok) {
    throw new Error(`Chat request failed: ${initResponse.statusText}`)
  }

  const { task_id } = await initResponse.json() as { task_id: string }

  const streamResponse = await fetch(`http://localhost:8000/query/${task_id}/stream`)

  if (!streamResponse.ok) {
    throw new Error(`Stream request failed: ${streamResponse.statusText}`)
  }

  const reader = streamResponse.body!.getReader()
  const decoder = new TextDecoder()

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    yield decoder.decode(value, { stream: true })
  }
}

export const chatQueryOptions = (question: string) =>
  queryOptions({
    queryKey: ['chat', question],
    queryFn: streamedQuery({
      streamFn: () => chatAnswer(question),
    }),
    staleTime: Infinity,
  })
