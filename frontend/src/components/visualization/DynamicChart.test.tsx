// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DynamicChart } from './DynamicChart'
import type { ChartConfig } from '#/queries/chat.queries'

vi.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="area-chart">{children}</div>
  ),
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Bar: () => null,
  Line: () => null,
  Area: () => null,
  Pie: () => null,
  Sector: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))

const baseConfig: ChartConfig = {
  chart_type: 'bar',
  title: 'Test Chart',
  description: 'A test description',
  x_key: 'name',
  y_keys: ['value'],
  x_label: null,
  y_label: null,
  series_labels: { value: 'Value' },
  name_key: null,
  value_key: null,
  data: [
    { name: 'A', value: 42 },
    { name: 'B', value: 100 },
  ],
  color: null,
}

describe('DynamicChart', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    URL.revokeObjectURL = vi.fn()
  })

  describe('good flows', () => {
    it('renders the chart title', () => {
      render(<DynamicChart config={baseConfig} />)
      expect(screen.getByText('Test Chart')).toBeDefined()
    })

    it('renders the chart description', () => {
      render(<DynamicChart config={baseConfig} />)
      expect(screen.getByText('A test description')).toBeDefined()
    })

    it('renders a bar chart when chart_type is bar', () => {
      render(<DynamicChart config={baseConfig} />)
      expect(screen.getByTestId('bar-chart')).toBeDefined()
    })

    it('renders a line chart when chart_type is line', () => {
      render(<DynamicChart config={{ ...baseConfig, chart_type: 'line' }} />)
      expect(screen.getByTestId('line-chart')).toBeDefined()
    })

    it('renders an area chart when chart_type is area', () => {
      render(<DynamicChart config={{ ...baseConfig, chart_type: 'area' }} />)
      expect(screen.getByTestId('area-chart')).toBeDefined()
    })

    it('renders a pie chart when chart_type is pie', () => {
      render(
        <DynamicChart
          config={{ ...baseConfig, chart_type: 'pie', value_key: 'value', name_key: 'name' }}
        />,
      )
      expect(screen.getByTestId('pie-chart')).toBeDefined()
    })

    it('has an Export CSV button', () => {
      render(<DynamicChart config={baseConfig} />)
      expect(screen.getByTitle('Export CSV')).toBeDefined()
    })

    it('has an Export PNG button', () => {
      render(<DynamicChart config={baseConfig} />)
      expect(screen.getByTitle('Export PNG')).toBeDefined()
    })
  })

  describe('bad flows', () => {
    it('exportCsv does not throw when data is empty', () => {
      const emptyConfig = { ...baseConfig, data: [] }
      render(<DynamicChart config={emptyConfig} />)
      const csvBtn = screen.getByTitle('Export CSV')
      expect(() => fireEvent.click(csvBtn)).not.toThrow()
    })
  })
})
