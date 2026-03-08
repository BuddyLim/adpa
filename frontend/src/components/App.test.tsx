// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { App } from './App'

vi.mock('#/components/chat/ChatMessage', () => ({
  ChatMessage: ({ question }: { question: string }) => (
    <div data-testid="chat-message">{question}</div>
  ),
}))

vi.mock('#/components/ConversationSidebar', () => ({
  ConversationSidebar: () => <div data-testid="conversation-sidebar" />,
  getStoredConversations: vi.fn(() => []),
  saveStoredConversation: vi.fn(),
}))

vi.mock('#/components/visualization/EmptyCanvas', () => ({
  EmptyCanvas: () => <div data-testid="empty-canvas" />,
}))

vi.mock('#/components/visualization/VisualizationPanel', () => ({
  VisualizationPanel: () => <div data-testid="visualization-panel" />,
}))

vi.mock('#/components/chat/HistoricalConversationView', () => ({
  HistoricalConversationView: () => <div data-testid="historical-view" />,
}))

beforeEach(() => {
  localStorage.clear()
  Element.prototype.scrollIntoView = vi.fn()
})

describe('App', () => {
  describe('good flows', () => {
    it('input starts empty', () => {
      render(<App />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      expect(input.value).toBe('')
    })

    it('submit button is disabled when input is empty', () => {
      render(<App />)
      const button = screen.getByRole('button')
      expect(button.hasAttribute('disabled')).toBe(true)
    })

    it('submit button is enabled after typing a question', () => {
      render(<App />)
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'What is GDP?' } })
      expect(screen.getByRole('button').hasAttribute('disabled')).toBe(false)
    })

    it('pressing Enter submits the question and renders ChatMessage', () => {
      render(<App />)
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'What is GDP?' } })
      fireEvent.keyDown(input, { key: 'Enter' })
      expect(screen.getByTestId('chat-message')).toBeDefined()
      expect(screen.getByText('What is GDP?')).toBeDefined()
    })

    it('clicking send button submits the question', () => {
      render(<App />)
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'Tell me about housing' } })
      fireEvent.click(screen.getByRole('button'))
      expect(screen.getByText('Tell me about housing')).toBeDefined()
    })

    it('clears the input after submission', () => {
      render(<App />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      fireEvent.change(input, { target: { value: 'My question' } })
      fireEvent.keyDown(input, { key: 'Enter' })
      expect(input.value).toBe('')
    })

    it('multiple questions accumulate in the message list', () => {
      render(<App />)
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'First question' } })
      fireEvent.keyDown(input, { key: 'Enter' })
      fireEvent.change(input, { target: { value: 'Second question' } })
      fireEvent.keyDown(input, { key: 'Enter' })
      expect(screen.getAllByTestId('chat-message')).toHaveLength(2)
    })

    it('shows EmptyCanvas initially (no visualization data)', () => {
      render(<App />)
      expect(screen.getByTestId('empty-canvas')).toBeDefined()
    })

    it('renders ConversationSidebar', () => {
      render(<App />)
      expect(screen.getByTestId('conversation-sidebar')).toBeDefined()
    })
  })

  describe('bad flows', () => {
    it('whitespace-only input keeps the submit button disabled', () => {
      render(<App />)
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: '   ' } })
      expect(screen.getByRole('button').hasAttribute('disabled')).toBe(true)
    })

    it('pressing Enter with whitespace-only input does not add a message', () => {
      render(<App />)
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: '   ' } })
      fireEvent.keyDown(input, { key: 'Enter' })
      expect(screen.queryByTestId('chat-message')).toBeNull()
    })
  })
})
