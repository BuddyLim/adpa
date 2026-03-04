import { Message } from '#/components/Message'
import type { ResultMessage, StatusMessage } from '#/queries/chat.queries'
import { chatQueryOptions } from '#/queries/chat.queries'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'

export const Route = createFileRoute('/')({ component: App })

function Spinner() {
  return (
    <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 12 12" fill="currentColor">
      <path d="M10 3L5 8.5 2 5.5l-1 1 4 4 6-7-1-1z" />
    </svg>
  )
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`w-3 h-3 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M2 4l4 4 4-4" />
    </svg>
  )
}

function PipelineSteps({
  steps,
  isFetching,
}: {
  steps: StatusMessage[]
  isFetching: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  if (steps.length === 0) return null

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] w-fit rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden text-sm bg-white dark:bg-gray-900 shadow-sm">
        {/* Header / toggle */}
        <button
          className="w-full flex items-center gap-2 px-3 py-2 text-left text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          onClick={() => setExpanded(!expanded)}
        >
          {isFetching ? (
            <Spinner />
          ) : (
            <CheckIcon className="w-3 h-3 text-green-500 shrink-0" />
          )}
          <span className="flex-1 text-xs font-medium">
            {isFetching ? (steps.at(-1)?.message ?? 'Working...') : 'Done'}
          </span>
          <ChevronIcon expanded={expanded} />
        </button>

        {/* Expanded steps */}
        {expanded && steps.length > 0 && (
          <div className="px-3 pb-2 pt-1 space-y-1 border-t border-gray-100 dark:border-gray-800">
            {steps.map((step, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 py-0.5"
              >
                {i === steps.length - 1 && isFetching ? (
                  <Spinner />
                ) : (
                  <CheckIcon className="w-3 h-3 text-green-500 shrink-0" />
                )}
                <span>{step.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function PipelineResult({ result }: { result: ResultMessage }) {
  if (!result.accepted) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-xl px-4 py-3 text-sm bg-orange-50 border border-orange-200 text-orange-800 dark:bg-orange-950 dark:border-orange-800 dark:text-orange-200">
          <div className="flex gap-2">
            <span className="shrink-0">⚠</span>
            <p>{result.reason}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-xl px-4 py-3 text-sm bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100 space-y-2">
        {result.refined_query && (
          <p className="font-medium">{result.refined_query}</p>
        )}
        {result.reason && (
          <p className="text-gray-500 dark:text-gray-400 text-xs">
            {result.reason}
          </p>
        )}
      </div>
    </div>
  )
}

function ChatMessage({ question }: { question: string }) {
  const { error, data = [], isFetching } = useQuery(chatQueryOptions(question))

  if (error) {
    return (
      <div>
        <Message message={{ content: question, isQuestion: true }} />
        <div className="flex justify-start mt-2">
          <p className="text-sm text-red-500">Error: {error.message}</p>
        </div>
      </div>
    )
  }

  const statusMessages = data.filter(
    (m): m is StatusMessage => m.type === 'status',
  )
  const result = data.find((m): m is ResultMessage => m.type === 'result')

  return (
    <div className="space-y-2">
      <Message message={{ content: question, isQuestion: true }} />
      <PipelineSteps steps={statusMessages} isFetching={isFetching} />
      {result && <PipelineResult result={result} />}
    </div>
  )
}

function App() {
  const [questions, setQuestions] = useState<Array<string>>([])
  const [currentQuestion, setCurrentQuestion] = useState('')

  const submitMessage = () => {
    if (!currentQuestion.trim()) return
    setQuestions([...questions, currentQuestion])
    setCurrentQuestion('')
  }

  return (
    <main className="page-wrap px-4 pb-8 pt-14">
      <div className="overflow-y-auto mb-4 space-y-4">
        {questions.map((question) => (
          <ChatMessage key={question} question={question} />
        ))}
      </div>

      <div className="flex items-center space-x-2">
        <input
          className="flex-1 p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-100"
          value={currentQuestion}
          onChange={(e) => setCurrentQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitMessage()
          }}
          placeholder="Type your message..."
        />
        <button
          onClick={submitMessage}
          disabled={!currentQuestion.trim()}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-2xl shadow-md transition"
        >
          <span>Send</span>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" />
            <path d="m21.854 2.147-10.94 10.939" />
          </svg>
        </button>
      </div>
    </main>
  )
}
