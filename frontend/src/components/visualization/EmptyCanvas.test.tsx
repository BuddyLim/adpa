// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyCanvas } from './EmptyCanvas'

describe('EmptyCanvas', () => {
  it('renders the "No data yet" heading', () => {
    render(<EmptyCanvas />)
    expect(screen.getByText('No data yet')).toBeDefined()
  })

  it('renders the prompt message', () => {
    render(<EmptyCanvas />)
    expect(screen.getByText('Ask a question to see data visualisations here')).toBeDefined()
  })
})
