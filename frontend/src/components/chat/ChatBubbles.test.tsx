// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UserBubble, AssistantBubble, RejectedBadge, ErrorBubble, LoadingBubble } from './ChatBubbles'

describe('UserBubble', () => {
  it('renders content text', () => {
    render(<UserBubble content="Hello world" />)
    expect(screen.getByText('Hello world')).toBeTruthy()
  })

  it('renders long content without truncation', () => {
    const long = 'A'.repeat(500)
    render(<UserBubble content={long} />)
    expect(screen.getByText(long)).toBeTruthy()
  })
})

describe('AssistantBubble', () => {
  it('renders content text when not streaming', () => {
    render(<AssistantBubble content="Response text" />)
    expect(screen.getByText('Response text')).toBeTruthy()
  })

  it('renders content with blinking cursor when streaming', () => {
    const { container } = render(<AssistantBubble content="Partial response" isStreaming />)
    expect(screen.getByText('Partial response')).toBeTruthy()
    expect(container.querySelector('span.animate-pulse')).toBeTruthy()
  })

  it('renders three bounce dots when streaming with no content', () => {
    const { container } = render(<AssistantBubble content="" isStreaming />)
    const dots = container.querySelectorAll('span.animate-bounce')
    expect(dots.length).toBe(3)
  })

  it('does not render cursor when not streaming', () => {
    const { container } = render(<AssistantBubble content="Done" isStreaming={false} />)
    expect(container.querySelector('span.animate-pulse')).toBeNull()
  })
})

describe('RejectedBadge', () => {
  it('renders reason text', () => {
    render(<RejectedBadge reason="Query not valid" />)
    expect(screen.getByText('Query not valid')).toBeTruthy()
  })

  it('renders the warning icon', () => {
    render(<RejectedBadge reason="Bad query" />)
    expect(screen.getByText('⚠')).toBeTruthy()
  })
})

describe('ErrorBubble', () => {
  it('renders the error message', () => {
    render(<ErrorBubble message="Network failure" />)
    expect(screen.getByText('Network failure')).toBeTruthy()
    expect(screen.getByText('Something went wrong')).toBeTruthy()
  })

  it('does not render a Retry button when onRetry is not provided', () => {
    render(<ErrorBubble message="Network failure" />)
    expect(screen.queryByRole('button', { name: /retry/i })).toBeNull()
  })

  it('renders a Retry button when onRetry is provided', () => {
    render(<ErrorBubble message="Network failure" onRetry={vi.fn()} />)
    expect(screen.getByRole('button', { name: /retry/i })).toBeTruthy()
  })

  it('calls onRetry when the Retry button is clicked', () => {
    const onRetry = vi.fn()
    render(<ErrorBubble message="Network failure" onRetry={onRetry} />)
    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})

describe('LoadingBubble', () => {
  it('renders three animated bounce dots', () => {
    const { container } = render(<LoadingBubble />)
    const dots = container.querySelectorAll('span.animate-bounce')
    expect(dots.length).toBe(3)
  })
})
