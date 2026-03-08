// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ResultBubble } from './ResultBubble'

describe('ResultBubble', () => {
  describe('rejected result', () => {
    it('renders the rejection reason', () => {
      render(<ResultBubble result={{ type: 'result', accepted: false, reason: 'Out of scope' }} />)
      expect(screen.getByText('Out of scope')).toBeDefined()
    })

    it('renders a warning icon', () => {
      render(<ResultBubble result={{ type: 'result', accepted: false, reason: 'Bad query' }} />)
      expect(screen.getByText('⚠')).toBeDefined()
    })
  })

  describe('accepted result', () => {
    it('renders the refined query when present', () => {
      render(
        <ResultBubble
          result={{ type: 'result', accepted: true, refined_query: 'GDP growth in Singapore' }}
        />,
      )
      expect(screen.getByText('GDP growth in Singapore')).toBeDefined()
    })

    it('renders the reason text when present', () => {
      render(
        <ResultBubble
          result={{ type: 'result', accepted: true, reason: 'Relevant dataset found' }}
        />,
      )
      expect(screen.getByText('Relevant dataset found')).toBeDefined()
    })

    it('renders nothing extra when neither refined_query nor reason is present', () => {
      const { container } = render(
        <ResultBubble result={{ type: 'result', accepted: true }} />,
      )
      // The outer div still renders, just no inner text
      expect(container.querySelector('p')).toBeNull()
    })
  })
})
