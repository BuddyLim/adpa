import { Message } from '#/components/Message'
import { chatQueryOptions } from '#/queries/chat.queries'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'

export const Route = createFileRoute('/')({ component: App })

function ChatMessage({ question }: { question: string }) {
  const { error, data = [], isFetching } = useQuery(chatQueryOptions(question))

  if (error) return 'An error has occurred: ' + error.message

  return (
    <div>
      <Message message={{ content: question, isQuestion: true }} />
      <Message
        inProgress={isFetching}
        message={{ content: data.join(''), isQuestion: false }}
      />
    </div>
  )
}

function App() {
  const [questions, setQuestions] = useState<Array<string>>([])
  const [currentQuestion, setCurrentQuestion] = useState('')

  const submitMessage = () => {
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
            if (e.key === 'Enter') {
              submitMessage()
            }
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
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" />
            <path d="m21.854 2.147-10.94 10.939" />
          </svg>
        </button>
      </div>
    </main>
  )
}
