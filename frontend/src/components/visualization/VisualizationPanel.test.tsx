// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VisualizationPanel } from './VisualizationPanel'
import type { VisualizationData } from './VisualizationPanel'

vi.mock('./DynamicChart', () => ({
  DynamicChart: ({ config }: { config: { title: string } }) => (
    <div data-testid="dynamic-chart">{config.title}</div>
  ),
}))

const barChartConfig = {
  chart_type: 'bar' as const,
  title: 'GDP Chart',
  description: 'GDP over time',
  x_key: 'year',
  y_keys: ['value'],
  series_labels: {},
  data: [{ year: '2020', value: 100 }],
  x_label: null,
  y_label: null,
  name_key: null,
  value_key: null,
  color: null,
}

describe('VisualizationPanel', () => {
  it('renders a DynamicChart for each chart_config in an item with analysisResult', () => {
    const items: VisualizationData[] = [
      {
        query: 'What is GDP?',
        reason: '',
        analysisResult: {
          summary: 'GDP summary',
          key_findings: [],
          chart_configs: [barChartConfig],
        },
      },
    ]
    render(<VisualizationPanel items={items} />)
    expect(screen.getByTestId('dynamic-chart')).toBeDefined()
    expect(screen.getByText('GDP Chart')).toBeDefined()
  })

  it('renders multiple charts when analysisResult has multiple chart_configs', () => {
    const items: VisualizationData[] = [
      {
        query: 'Query',
        reason: '',
        analysisResult: {
          summary: 'Summary',
          key_findings: [],
          chart_configs: [
            { ...barChartConfig, title: 'Chart One' },
            { ...barChartConfig, title: 'Chart Two' },
          ],
        },
      },
    ]
    render(<VisualizationPanel items={items} />)
    expect(screen.getAllByTestId('dynamic-chart')).toHaveLength(2)
  })

  it('renders reason text for items without analysisResult', () => {
    const items: VisualizationData[] = [
      { query: 'Query', reason: 'Relevant insight here', analysisResult: undefined },
    ]
    render(<VisualizationPanel items={items} />)
    expect(screen.getByText('Relevant insight here')).toBeDefined()
    expect(screen.getByText('Insight')).toBeDefined()
  })

  it('renders nothing for items with no analysisResult and no reason', () => {
    const items: VisualizationData[] = [
      { query: 'Query', reason: '', analysisResult: undefined },
    ]
    const { container } = render(<VisualizationPanel items={items} />)
    expect(container.querySelector('[data-testid="dynamic-chart"]')).toBeNull()
    expect(screen.queryByText('Insight')).toBeNull()
  })
})
