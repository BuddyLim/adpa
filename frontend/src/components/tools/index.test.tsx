// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  DatasetListCard,
  DatasetsSelectedCard,
  ExtractionCard,
  NormalizationCard,
  AnalysisCard,
} from './index'

// ─── DatasetListCard ──────────────────────────────────────────────────────────

describe('DatasetListCard', () => {
  it('shows loading text when pending', () => {
    render(<DatasetListCard args={{}} result={undefined} pending={true} failed={false} />)
    expect(screen.getByText('Loading datasets…')).toBeTruthy()
  })

  it('lists dataset titles when result is available', () => {
    const result = [
      { title: 'Population Data', path: '/pop' },
      { title: 'Employment Stats', path: '/emp', description: 'Jobs data' },
    ]
    render(<DatasetListCard args={{}} result={result} pending={false} failed={false} />)
    expect(screen.getByText('Population Data')).toBeTruthy()
    expect(screen.getByText('Employment Stats')).toBeTruthy()
  })

  it('shows failure label when failed', () => {
    render(<DatasetListCard args={{}} result={undefined} pending={false} failed={true} />)
    expect(screen.getByText('Dataset loading failed')).toBeTruthy()
  })
})

// ─── DatasetsSelectedCard ─────────────────────────────────────────────────────

describe('DatasetsSelectedCard', () => {
  it('shows pending text when no result', () => {
    render(<DatasetsSelectedCard args={{}} result={undefined} pending={true} failed={false} />)
    expect(screen.getByText('Selecting datasets…')).toBeTruthy()
  })

  it('lists selected dataset names when result is available', () => {
    render(
      <DatasetsSelectedCard
        args={{}}
        result={{ datasets: ['Births Register', 'Death Records'] }}
        pending={false}
        failed={false}
      />,
    )
    expect(screen.getByText('Births Register')).toBeTruthy()
    expect(screen.getByText('Death Records')).toBeTruthy()
  })

  it('shows failure label when failed', () => {
    render(<DatasetsSelectedCard args={{}} result={undefined} pending={false} failed={true} />)
    expect(screen.getByText('Dataset selection failed')).toBeTruthy()
  })
})

// ─── ExtractionCard ───────────────────────────────────────────────────────────

describe('ExtractionCard', () => {
  it('shows comma-separated dataset names from args when pending', () => {
    render(
      <ExtractionCard
        args={{ datasets: ['Dataset A', 'Dataset B'] }}
        result={undefined}
        pending={true}
        failed={false}
      />,
    )
    expect(screen.getByText('Dataset A, Dataset B')).toBeTruthy()
  })

  it('shows row counts per dataset when result is available', () => {
    render(
      <ExtractionCard
        args={{ datasets: ['A'] }}
        result={{ datasets: [{ title: 'Dataset A', row_count: 1500 }], total_rows: 1500 }}
        pending={false}
        failed={false}
      />,
    )
    expect(screen.getByText('Dataset A')).toBeTruthy()
    expect(screen.getByText('1,500 rows')).toBeTruthy()
  })

  it('shows total rows when there are multiple datasets', () => {
    render(
      <ExtractionCard
        args={{ datasets: ['A', 'B'] }}
        result={{
          datasets: [
            { title: 'Dataset A', row_count: 100 },
            { title: 'Dataset B', row_count: 200 },
          ],
          total_rows: 300,
        }}
        pending={false}
        failed={false}
      />,
    )
    expect(screen.getByText('300 rows total')).toBeTruthy()
  })

  it('does not show total rows for a single dataset', () => {
    render(
      <ExtractionCard
        args={{ datasets: ['A'] }}
        result={{ datasets: [{ title: 'Dataset A', row_count: 500 }], total_rows: 500 }}
        pending={false}
        failed={false}
      />,
    )
    expect(screen.queryByText(/rows total/)).toBeNull()
  })

  it('shows failure label when failed', () => {
    render(
      <ExtractionCard args={{ datasets: ['A'] }} result={undefined} pending={false} failed={true} />,
    )
    expect(screen.getByText('Extraction failed')).toBeTruthy()
  })
})

// ─── NormalizationCard ────────────────────────────────────────────────────────

describe('NormalizationCard', () => {
  it('shows plural source count when pending with multiple sources', () => {
    render(
      <NormalizationCard
        args={{ n_sources: 2, datasets: ['A', 'B'] }}
        result={undefined}
        pending={true}
        failed={false}
      />,
    )
    expect(screen.getByText('Merging 2 sources…')).toBeTruthy()
  })

  it('shows singular source count when pending with one source', () => {
    render(
      <NormalizationCard
        args={{ n_sources: 1, datasets: ['A'] }}
        result={undefined}
        pending={true}
        failed={false}
      />,
    )
    expect(screen.getByText('Merging 1 source…')).toBeTruthy()
  })

  it('shows unified row count and column count when result is available', () => {
    render(
      <NormalizationCard
        args={{ n_sources: 1, datasets: ['A'] }}
        result={{ unified_rows: 5000, columns: ['col_a', 'col_b', 'col_c'] }}
        pending={false}
        failed={false}
      />,
    )
    expect(screen.getByText('5,000 unified rows')).toBeTruthy()
    expect(screen.getByText('3 columns')).toBeTruthy()
  })

  it('shows failure label when failed', () => {
    render(
      <NormalizationCard
        args={{ n_sources: 1, datasets: ['A'] }}
        result={undefined}
        pending={false}
        failed={true}
      />,
    )
    expect(screen.getByText('Normalization failed')).toBeTruthy()
  })
})

// ─── AnalysisCard ─────────────────────────────────────────────────────────────

const mockChartConfig = {
  chart_type: 'bar' as const,
  title: 'Chart',
  description: '',
  x_key: 'x',
  y_keys: ['y'],
  data: [],
  series_labels: {},
}

describe('AnalysisCard', () => {
  it('shows row count from args when pending', () => {
    render(
      <AnalysisCard
        args={{ unified_rows: 2000, columns: [] }}
        result={undefined}
        pending={true}
        failed={false}
      />,
    )
    expect(screen.getByText('Processing 2,000 rows…')).toBeTruthy()
  })

  it('shows plural chart count when multiple charts are ready', () => {
    render(
      <AnalysisCard
        args={{ unified_rows: 2000, columns: [] }}
        result={{
          summary: 'ok',
          key_findings: [],
          chart_configs: [mockChartConfig, { ...mockChartConfig, title: 'Chart 2' }],
        }}
        pending={false}
        failed={false}
      />,
    )
    expect(screen.getByText('2 charts ready')).toBeTruthy()
  })

  it('shows singular chart count when exactly one chart is ready', () => {
    render(
      <AnalysisCard
        args={{ unified_rows: 2000, columns: [] }}
        result={{ summary: 'ok', key_findings: [], chart_configs: [mockChartConfig] }}
        pending={false}
        failed={false}
      />,
    )
    expect(screen.getByText('1 chart ready')).toBeTruthy()
  })

  it('shows failure label when failed', () => {
    render(
      <AnalysisCard
        args={{ unified_rows: 2000, columns: [] }}
        result={undefined}
        pending={false}
        failed={true}
      />,
    )
    expect(screen.getByText('Analysis failed')).toBeTruthy()
  })
})
