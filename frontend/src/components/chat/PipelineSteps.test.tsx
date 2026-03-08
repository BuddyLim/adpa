// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PipelineSteps } from './PipelineSteps'
import type { TimelineItem } from './types'

vi.mock('#/components/tools', () => ({
  TOOL_COMPONENTS: {
    'coordinator/list_datasets': ({ pending }: { pending: boolean }) => (
      <div data-testid="tool-card-list-datasets">{pending ? 'pending' : 'done'}</div>
    ),
    'coordinator/datasets_selected': ({ pending }: { pending: boolean }) => (
      <div data-testid="tool-card-datasets-selected">{pending ? 'pending' : 'done'}</div>
    ),
    'pipeline/extraction': ({ pending }: { pending: boolean }) => (
      <div data-testid="tool-card-extraction">{pending ? 'pending' : 'done'}</div>
    ),
    'pipeline/normalization': ({ pending }: { pending: boolean }) => (
      <div data-testid="tool-card-normalization">{pending ? 'pending' : 'done'}</div>
    ),
    'pipeline/analysis': ({ pending }: { pending: boolean }) => (
      <div data-testid="tool-card-analysis">{pending ? 'pending' : 'done'}</div>
    ),
  },
}))

const statusTimeline: TimelineItem[] = [
  { kind: 'status', message: 'Searching datasets…' },
]

const toolTimeline: TimelineItem[] = [
  { kind: 'status', message: 'Looking up data…' },
  {
    kind: 'tool',
    tool: 'coordinator/list_datasets',
    args: {},
    result: undefined,
    pending: true,
    failed: false,
  },
]

const completedToolTimeline: TimelineItem[] = [
  { kind: 'status', message: 'Datasets ready' },
  {
    kind: 'tool',
    tool: 'coordinator/list_datasets',
    args: {},
    result: [],
    pending: false,
    failed: false,
  },
]

describe('PipelineSteps', () => {
  it('returns nothing when timeline is empty', () => {
    const { container } = render(<PipelineSteps timeline={[]} isFetching={false} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows the last status message in the header while fetching', () => {
    render(<PipelineSteps timeline={statusTimeline} isFetching={true} />)
    // Header button contains the status text (may also appear in expanded body)
    const button = screen.getByRole('button')
    expect(button.textContent).toContain('Searching datasets…')
  })

  it('shows "Done" in header when fetch completes with no completed tool', () => {
    render(<PipelineSteps timeline={statusTimeline} isFetching={false} />)
    expect(screen.getByText('Done')).toBeDefined()
  })

  it('shows TOOL_LABELS done label when fetch completes with a completed tool', () => {
    render(<PipelineSteps timeline={completedToolTimeline} isFetching={false} />)
    // TOOL_LABELS['coordinator/list_datasets'].done = 'Datasets available'
    expect(screen.getByText('Datasets available')).toBeDefined()
  })

  it('shows TOOL_LABELS pending label when a tool is pending', () => {
    render(<PipelineSteps timeline={toolTimeline} isFetching={true} />)
    // TOOL_LABELS['coordinator/list_datasets'].pending = 'Loading datasets…'
    expect(screen.getByText('Loading datasets…')).toBeDefined()
  })

  it('shows "Pipeline failed" header when isError is true', () => {
    render(<PipelineSteps timeline={statusTimeline} isFetching={false} isError={true} />)
    expect(screen.getByText('Pipeline failed')).toBeDefined()
  })

  it('renders status message text in the expanded body', () => {
    render(<PipelineSteps timeline={statusTimeline} isFetching={false} />)
    expect(screen.getByText('Searching datasets…')).toBeDefined()
  })

  it('renders a tool card for tool items', () => {
    render(<PipelineSteps timeline={toolTimeline} isFetching={true} />)
    expect(screen.getByTestId('tool-card-list-datasets')).toBeDefined()
  })

  it('collapses the body when the header button is clicked', () => {
    // isFetching=false → header shows "Done", body shows status text
    render(<PipelineSteps timeline={statusTimeline} isFetching={false} />)
    // Status text visible in expanded body
    expect(screen.getByText('Searching datasets…')).toBeDefined()
    fireEvent.click(screen.getByRole('button'))
    // After collapse the body is gone, header shows "Done" — status text absent
    expect(screen.queryByText('Searching datasets…')).toBeNull()
  })

  it('re-expands after a second click', () => {
    render(<PipelineSteps timeline={statusTimeline} isFetching={false} />)
    const button = screen.getByRole('button')
    fireEvent.click(button) // collapse
    fireEvent.click(button) // re-expand
    // Body text is visible again
    expect(screen.getByText('Searching datasets…')).toBeDefined()
  })
})
