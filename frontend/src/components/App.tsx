import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  PipelineAnalysisResult,
  ResultMessage,
} from '#/queries/chat.queries'
import { EmptyCanvas } from './visualization/EmptyCanvas'
import { VisualizationPanel } from './visualization/VisualizationPanel'
import type { VisualizationData } from './visualization/VisualizationPanel'
import { ChatMessage } from './chat/ChatMessage'
import { HistoricalConversationView } from './chat/HistoricalConversationView'
import {
  ConversationSidebar,
  getStoredConversations,
  saveStoredConversation,
} from './ConversationSidebar'
import type { StoredConversation } from './ConversationSidebar'

function SendIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-4 h-4"
    >
      <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" />
      <path d="m21.854 2.147-10.94 10.939" />
    </svg>
  )
}

export function App() {
  // Live chat state
  const [questions, setQuestions] = useState<
    Array<{ question: string; convId: string | null }>
  >([])
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [visualizationItems, setVisualizationItems] = useState<
    VisualizationData[]
  >([])

  // Conversation / history state
  const currentConvIdRef = useRef<string | null>(null)
  const [savedConversations, setSavedConversations] = useState<
    StoredConversation[]
  >(() => getStoredConversations())
  const [historicalConvId, setHistoricalConvId] = useState<string | null>(null)

  const isHistoricalMode = historicalConvId !== null

  const bottomRef = useRef<HTMLDivElement>(null)
  const hasData = visualizationItems.length > 0

  // Auto-scroll to bottom on new live messages
  useEffect(() => {
    if (!isHistoricalMode) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [questions, isHistoricalMode])

  // ─── Handlers ───────────────────────────────────────────────────────────────

  const handleConversationStarted = useCallback(
    (id: string, title: string | null) => {
      if (!currentConvIdRef.current) {
        currentConvIdRef.current = id
        const conv: StoredConversation = {
          id,
          title:
            title !== null ? title : (questions[0]?.question ?? 'Conversation'),
          createdAt: new Date().toISOString(),
        }
        saveStoredConversation(conv)
        setSavedConversations(getStoredConversations())
      }
    },
    [questions],
  )

  const handleAccepted = useCallback(
    (result: ResultMessage, analysisResult?: PipelineAnalysisResult) => {
      setVisualizationItems((prev) => [
        ...prev,
        {
          query: result.refined_query ?? result.reason ?? '',
          reason: result.reason ?? '',
          analysisResult,
        },
      ])
    },
    [],
  )

  const submitMessage = () => {
    const q = currentQuestion.trim()
    if (!q) return
    // Switch to live mode if user types while viewing history
    if (historicalConvId !== null) {
      setVisualizationItems([])
    }
    setHistoricalConvId(null)
    setQuestions((prev) => [
      ...prev,
      { question: q, convId: currentConvIdRef.current },
    ])
    setCurrentQuestion('')
  }

  const handleNewChat = () => {
    currentConvIdRef.current = null
    setQuestions([])
    setVisualizationItems([])
    setHistoricalConvId(null)
  }

  const handleSelectConversation = (id: string) => {
    setHistoricalConvId(id)
  }
  const handleHistoricalVizReady = useCallback((items: VisualizationData[]) => {
    setVisualizationItems(items)
  }, [])

  // Active sidebar id: selected historical conversation or current live one
  const activeSidebarId = isHistoricalMode
    ? historicalConvId
    : currentConvIdRef.current

  return (
    <main className="flex" style={{ height: 'calc(100vh - 57px)' }}>
      {/* Sidebar */}
      <ConversationSidebar
        conversations={savedConversations}
        activeId={activeSidebarId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
      />

      {/* Chat panel */}
      <div
        className="shrink-0 flex flex-col overflow-hidden bg-(--foam) border-r border-(--line)"
        style={{ width: 320 }}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-(--line) bg-(--header-bg) backdrop-blur-lg shrink-0 flex items-center justify-between">
          <div>
            <p className="font-semibold text-sm text-(--sea-ink)">
              {isHistoricalMode
                ? (savedConversations.find((c) => c.id === historicalConvId)
                    ?.title ?? 'Past Conversation')
                : 'Analytics Assistant'}
            </p>
            <p className="text-xs text-(--sea-ink-soft)">
              {isHistoricalMode
                ? 'Viewing history'
                : 'Ask about Singapore policy data'}
            </p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 bg-(--header-bg)">
          {isHistoricalMode ? (
            <HistoricalConversationView
              conversationId={historicalConvId}
              onVisualizationReady={handleHistoricalVizReady}
            />
          ) : (
            <>
              {questions.length === 0 && (
                <p className="text-sm text-gray-400 text-center mt-8">
                  Hi! Ask me anything about Singaporean data related matters, I
                  can help you find relevant datasets and prepare
                  visualisations.
                </p>
              )}
              {questions.map(({ question, convId }) => (
                <ChatMessage
                  key={`${question}-${convId ?? 'new'}`}
                  question={question}
                  conversationId={convId}
                  onAccepted={handleAccepted}
                  onConversationStarted={handleConversationStarted}
                />
              ))}
              <div ref={bottomRef} />
            </>
          )}
        </div>

        {/* Input */}
        <div className="shrink-0 px-4 py-3 border-t border-(--line) bg-(--surface-strong)">
          <div className="flex items-center gap-2">
            <input
              className="flex-1 px-3 py-2 text-sm rounded-xl border border-slate-200 bg-white text-(--sea-ink) placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-(--lagoon) focus:ring-offset-1"
              value={currentQuestion}
              onChange={(e) => setCurrentQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') submitMessage()
              }}
              placeholder={
                isHistoricalMode
                  ? 'Type to follow up your question'
                  : 'Ask a question to start a new chat'
              }
            />
            <button
              onClick={submitMessage}
              disabled={!currentQuestion.trim()}
              className="flex items-center justify-center w-9 h-9 rounded-xl bg-(--lagoon-deep) text-white disabled:opacity-40 transition-opacity shrink-0"
            >
              <SendIcon />
            </button>
          </div>
        </div>
      </div>

      {/* Visualization panel */}
      <div className="flex-1 overflow-hidden border-r border-(--line) bg-[radial-gradient(circle at 18% 12%, rgba(6, 182, 212, 0.06), transparent 38%), radial-gradient(circle at 82% 20%, rgba(139, 92, 246, 0.05), transparent 40%)]">
        {hasData ? (
          <VisualizationPanel items={visualizationItems} />
        ) : (
          <EmptyCanvas />
        )}
      </div>
    </main>
  )
}
