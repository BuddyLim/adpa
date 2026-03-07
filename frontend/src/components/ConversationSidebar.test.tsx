// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  getStoredConversations,
  saveStoredConversation,
  ConversationSidebar,
} from './ConversationSidebar'
import type { StoredConversation } from './ConversationSidebar'

const STORAGE_KEY = 'apda_conversations'

beforeEach(() => {
  localStorage.clear()
})

// ─── getStoredConversations ───────────────────────────────────────────────────

describe('getStoredConversations', () => {
  it('returns an empty array when localStorage has no entry', () => {
    expect(getStoredConversations()).toEqual([])
  })

  it('returns the parsed conversations from localStorage', () => {
    const convs: StoredConversation[] = [
      { id: '1', title: 'First', createdAt: '2024-01-01T00:00:00Z' },
      { id: '2', title: 'Second', createdAt: '2024-01-02T00:00:00Z' },
    ]
    localStorage.setItem(STORAGE_KEY, JSON.stringify(convs))
    expect(getStoredConversations()).toEqual(convs)
  })

  it('returns an empty array when localStorage contains corrupted JSON', () => {
    localStorage.setItem(STORAGE_KEY, 'not-valid-json{{[')
    expect(getStoredConversations()).toEqual([])
  })

  it('returns an empty array when localStorage contains an empty JSON array', () => {
    localStorage.setItem(STORAGE_KEY, '[]')
    expect(getStoredConversations()).toEqual([])
  })
})

// ─── saveStoredConversation ───────────────────────────────────────────────────

describe('saveStoredConversation', () => {
  it('saves a new conversation to localStorage', () => {
    const conv: StoredConversation = { id: '1', title: 'First', createdAt: '2024-01-01T00:00:00Z' }
    saveStoredConversation(conv)
    expect(getStoredConversations()).toEqual([conv])
  })

  it('prepends new conversations so the newest appears first', () => {
    const conv1: StoredConversation = { id: '1', title: 'First', createdAt: '2024-01-01T00:00:00Z' }
    const conv2: StoredConversation = { id: '2', title: 'Second', createdAt: '2024-01-02T00:00:00Z' }
    saveStoredConversation(conv1)
    saveStoredConversation(conv2)
    const saved = getStoredConversations()
    expect(saved[0]).toEqual(conv2)
    expect(saved[1]).toEqual(conv1)
  })

  it('deduplicates by id — re-saved conversation replaces the old entry and appears at top', () => {
    const conv1: StoredConversation = { id: '1', title: 'First', createdAt: '2024-01-01T00:00:00Z' }
    const conv2: StoredConversation = { id: '2', title: 'Second', createdAt: '2024-01-02T00:00:00Z' }
    saveStoredConversation(conv1)
    saveStoredConversation(conv2)

    const updated: StoredConversation = { id: '1', title: 'Updated First', createdAt: '2024-01-03T00:00:00Z' }
    saveStoredConversation(updated)

    const saved = getStoredConversations()
    expect(saved).toHaveLength(2)
    expect(saved[0]).toEqual(updated)
    expect(saved[1]).toEqual(conv2)
  })
})

// ─── ConversationSidebar component ───────────────────────────────────────────

const baseConvs: StoredConversation[] = [
  { id: 'a', title: 'Conversation Alpha', createdAt: new Date().toISOString() },
  { id: 'b', title: 'Conversation Beta', createdAt: new Date(Date.now() - 86_400_000).toISOString() },
]

describe('ConversationSidebar', () => {
  it('renders collapsed by default (no "New Chat" label visible)', () => {
    render(
      <ConversationSidebar
        conversations={[]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
      />,
    )
    expect(screen.queryByText('New Chat')).toBeNull()
  })

  it('expands when the chevron button is clicked', () => {
    render(
      <ConversationSidebar
        conversations={[]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    expect(screen.getByText('New Chat')).toBeTruthy()
  })

  it('collapses again when the collapse button is clicked', () => {
    render(
      <ConversationSidebar
        conversations={[]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    fireEvent.click(screen.getByTitle('Collapse sidebar'))
    expect(screen.queryByText('New Chat')).toBeNull()
  })

  it('shows empty state message when expanded with no conversations', () => {
    render(
      <ConversationSidebar
        conversations={[]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    expect(screen.getByText(/past conversations will appear here/i)).toBeTruthy()
  })

  it('renders conversation titles when expanded', () => {
    render(
      <ConversationSidebar
        conversations={baseConvs}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    expect(screen.getByText('Conversation Alpha')).toBeTruthy()
    expect(screen.getByText('Conversation Beta')).toBeTruthy()
  })

  it('calls onSelect with the conversation id when an item is clicked (expanded)', () => {
    const onSelect = vi.fn()
    render(
      <ConversationSidebar
        conversations={baseConvs}
        activeId={null}
        onSelect={onSelect}
        onNewChat={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    fireEvent.click(screen.getByText('Conversation Alpha'))
    expect(onSelect).toHaveBeenCalledWith('a')
  })

  it('calls onSelect when a collapsed icon button is clicked', () => {
    const onSelect = vi.fn()
    render(
      <ConversationSidebar
        conversations={baseConvs}
        activeId={null}
        onSelect={onSelect}
        onNewChat={vi.fn()}
      />,
    )
    // In collapsed mode conversations are rendered as icon buttons with title=conv.title
    fireEvent.click(screen.getByTitle('Conversation Alpha'))
    expect(onSelect).toHaveBeenCalledWith('a')
  })

  it('calls onNewChat when the expanded New Chat button is clicked', () => {
    const onNewChat = vi.fn()
    render(
      <ConversationSidebar
        conversations={[]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={onNewChat}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    fireEvent.click(screen.getByText('New Chat'))
    expect(onNewChat).toHaveBeenCalledOnce()
  })

  it('calls onNewChat when the collapsed icon button is clicked', () => {
    const onNewChat = vi.fn()
    render(
      <ConversationSidebar
        conversations={[]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={onNewChat}
      />,
    )
    fireEvent.click(screen.getByTitle('New Chat'))
    expect(onNewChat).toHaveBeenCalledOnce()
  })

  it('shows "Today" for conversations created today', () => {
    const todayConv: StoredConversation = {
      id: 'today',
      title: 'Today Chat',
      createdAt: new Date().toISOString(),
    }
    render(
      <ConversationSidebar
        conversations={[todayConv]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    expect(screen.getByText('Today')).toBeTruthy()
  })

  it('shows "Yesterday" for conversations created one day ago', () => {
    const yesterdayConv: StoredConversation = {
      id: 'yesterday',
      title: 'Yesterday Chat',
      createdAt: new Date(Date.now() - 86_400_000).toISOString(),
    }
    render(
      <ConversationSidebar
        conversations={[yesterdayConv]}
        activeId={null}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTitle('Expand sidebar'))
    expect(screen.getByText('Yesterday')).toBeTruthy()
  })
})
