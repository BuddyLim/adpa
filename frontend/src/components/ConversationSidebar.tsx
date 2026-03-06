import { useState } from 'react'

export interface StoredConversation {
  id: string
  title: string
  createdAt: string
}

const STORAGE_KEY = 'apda_conversations'

export function getStoredConversations(): StoredConversation[] {
  try {
    return JSON.parse(
      localStorage.getItem(STORAGE_KEY) ?? '[]',
    ) as StoredConversation[]
  } catch {
    return []
  }
}

export function saveStoredConversation(conv: StoredConversation) {
  const existing = getStoredConversations().filter((c) => c.id !== conv.id)
  localStorage.setItem(STORAGE_KEY, JSON.stringify([conv, ...existing]))
}

function formatDate(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / 86_400_000)
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function PlusIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-4 h-4 shrink-0"
    >
      <path d="M5 12h14M12 5v14" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-3.5 h-3.5 shrink-0 opacity-50"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function ChevronLeftIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-3.5 h-3.5"
    >
      <path d="M15 18l-6-6 6-6" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-3.5 h-3.5"
    >
      <path d="M9 18l6-6-6-6" />
    </svg>
  )
}

export function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
}: {
  conversations: StoredConversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
}) {
  const [collapsed, setCollapsed] = useState(true)

  if (collapsed) {
    return (
      <div className="flex flex-col h-full bg-(--surface) border-r border-(--line) w-12 shrink-0 items-center py-3 gap-3">
        <button
          onClick={() => setCollapsed(false)}
          title="Expand sidebar"
          className="w-8 h-8 flex items-center justify-center rounded-lg text-(--sea-ink-soft) hover:bg-(--surface-strong) hover:text-(--sea-ink) transition-colors"
        >
          <ChevronRightIcon />
        </button>
        <button
          onClick={onNewChat}
          title="New Chat"
          className="w-8 h-8 flex items-center justify-center rounded-lg bg-(--lagoon-deep) text-white hover:opacity-90 transition-opacity"
        >
          <PlusIcon />
        </button>
        <div className="flex flex-col gap-1 mt-1 w-full px-1 overflow-y-auto">
          {conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => onSelect(conv.id)}
              title={conv.title}
              className={`w-full flex items-center justify-center py-2 rounded-lg transition-colors ${
                activeId === conv.id
                  ? 'bg-(--lagoon)/10 text-(--sea-ink)'
                  : 'text-(--sea-ink-soft) hover:bg-(--surface-strong) hover:text-(--sea-ink)'
              }`}
            >
              <ChatIcon />
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-(--surface) border-r border-(--line) w-56 shrink-0">
      {/* Header */}
      <div className="px-3 py-3 border-b border-(--line) shrink-0 flex items-center gap-2">
        <button
          onClick={onNewChat}
          className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium bg-(--lagoon-deep) text-white hover:opacity-90 transition-opacity"
        >
          <PlusIcon />
          New Chat
        </button>
        <button
          onClick={() => setCollapsed(true)}
          title="Collapse sidebar"
          className="w-7 h-7 flex items-center justify-center rounded-lg text-(--sea-ink-soft) hover:bg-(--surface-strong) hover:text-(--sea-ink) transition-colors shrink-0"
        >
          <ChevronLeftIcon />
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto py-2">
        {conversations.length === 0 ? (
          <p className="text-xs text-(--sea-ink-soft) text-center mt-6 px-3 leading-relaxed">
            Your past conversations will appear here
          </p>
        ) : (
          <ul className="space-y-0.5 px-2">
            {conversations.map((conv) => (
              <li key={conv.id}>
                <button
                  onClick={() => onSelect(conv.id)}
                  className={`w-full text-left flex items-start gap-2 px-2 py-2 rounded-lg text-xs transition-colors group ${
                    activeId === conv.id
                      ? 'bg-(--lagoon)/10 text-(--sea-ink)'
                      : 'text-(--sea-ink-soft) hover:bg-(--surface-strong) hover:text-(--sea-ink)'
                  }`}
                >
                  <ChatIcon />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium leading-snug">
                      {conv.title}
                    </p>
                    <p className="text-[10px] opacity-60 mt-0.5">
                      {formatDate(conv.createdAt)}
                    </p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
