// Tool card components for generative UI. Each component renders when a specific
// backend tool is called, showing args (when pending) or the full result (when complete).
//
// To add a new tool card:
// 1. Add its Args + Result types to chat.queries.ts (per-tool shapes + discriminated unions)
// 2. Create a card component below with typed props importing those types
// 3. Register it in TOOL_COMPONENTS at the bottom

import type {
  DatasetsSelectedResult,
  ListDatasetsResult,
  PipelineAnalysisArgs,
  PipelineAnalysisResult,
  PipelineExtractionArgs,
  PipelineExtractionResult,
  PipelineNormalizationArgs,
  PipelineNormalizationResult,
} from '#/queries/chat.queries'

// ─── Shared ───────────────────────────────────────────────────────────────────

function ToolBadge({
  label,
  pending,
  failed,
}: {
  label: string
  pending?: boolean
  failed?: boolean
}) {
  return (
    <div className="flex items-center gap-2 mb-2">
      {pending ? (
        <span className="inline-block w-2.5 h-2.5 border-2 border-(--lagoon-deep) border-t-transparent rounded-full animate-spin shrink-0" />
      ) : failed ? (
        <span className="w-2.5 h-2.5 rounded-full bg-red-400 shrink-0" />
      ) : (
        <span className="w-2.5 h-2.5 rounded-full bg-(--palm) shrink-0" />
      )}
      <span className="island-kicker">{label}</span>
    </div>
  )
}

function ToolCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-(--line) bg-(--surface-strong) p-3 text-xs shadow-sm overflow-hidden">
      {children}
    </div>
  )
}

// ─── DatasetListCard (coordinator/list_datasets) ──────────────────────────────

export function DatasetListCard({
  result,
  failed,
}: {
  args: Record<string, never>
  result?: ListDatasetsResult
  pending: boolean
  failed: boolean
}) {
  const datasets = Array.isArray(result) ? result : null

  return (
    <ToolCard>
      <ToolBadge
        label={failed ? 'Dataset loading failed' : 'Datasets available'}
        pending={!result && !failed}
        failed={failed}
      />
      {datasets ? (
        <ul className="space-y-0.5 text-(--sea-ink-soft)">
          {datasets.map((ds, i) => (
            <li key={i} className="whitespace-normal">
              <span className="font-medium text-(--sea-ink)">{ds.title}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-(--sea-ink-soft)">Loading datasets…</p>
      )}
    </ToolCard>
  )
}

// ─── DatasetsSelectedCard (coordinator/datasets_selected) ─────────────────────

export function DatasetsSelectedCard({
  result,
  pending,
  failed,
}: {
  args: Record<string, never>
  result?: DatasetsSelectedResult
  pending: boolean
  failed: boolean
}) {
  return (
    <ToolCard>
      <ToolBadge
        label={failed ? 'Dataset selection failed' : 'Datasets selected'}
        pending={pending}
        failed={failed}
      />
      {result ? (
        <ul className="space-y-0.5 text-(--sea-ink-soft)">
          {result.datasets.map((title, i) => (
            <li
              key={i}
              className="font-medium text-(--sea-ink) whitespace-normal"
            >
              {title}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-(--sea-ink-soft)">Selecting datasets…</p>
      )}
    </ToolCard>
  )
}

// ─── ExtractionCard (pipeline/extraction) ────────────────────────────────────

export function ExtractionCard({
  args,
  result,
  pending,
  failed,
}: {
  args: PipelineExtractionArgs
  result?: PipelineExtractionResult
  pending: boolean
  failed: boolean
}) {
  return (
    <ToolCard>
      <ToolBadge
        label={
          failed
            ? 'Extraction failed'
            : pending
              ? 'Extracting data…'
              : 'Data extracted'
        }
        pending={pending}
        failed={failed}
      />
      {result ? (
        <div className="space-y-1">
          {result.datasets.map((ds) => (
            <div
              key={ds.title}
              className="flex items-center justify-between gap-4"
            >
              <span className="font-medium text-(--sea-ink) whitespace-normal">
                {ds.title}
              </span>
              <span className="text-(--sea-ink-soft) shrink-0">
                {ds.row_count.toLocaleString()} rows
              </span>
            </div>
          ))}
          {result.datasets.length > 1 && (
            <p className="pt-1 text-(--sea-ink-soft) border-t border-(--line)">
              {result.total_rows.toLocaleString()} rows total
            </p>
          )}
        </div>
      ) : (
        <p className="text-(--sea-ink-soft)">{args.datasets.join(', ')}</p>
      )}
    </ToolCard>
  )
}

// ─── NormalizationCard (pipeline/normalization) ───────────────────────────────

export function NormalizationCard({
  args,
  result,
  pending,
  failed,
}: {
  args: PipelineNormalizationArgs
  result?: PipelineNormalizationResult
  pending: boolean
  failed: boolean
}) {
  return (
    <ToolCard>
      <ToolBadge
        label={
          failed
            ? 'Normalization failed'
            : pending
              ? 'Normalizing data…'
              : 'Data normalized'
        }
        pending={pending}
        failed={failed}
      />
      {result ? (
        <div className="flex items-center gap-3 text-(--sea-ink-soft)">
          <span>{result.unified_rows.toLocaleString()} unified rows</span>
          <span className="text-(--line)">·</span>
          <span>{result.columns.length} columns</span>
        </div>
      ) : (
        <p className="text-(--sea-ink-soft)">
          Merging {args.n_sources} source{args.n_sources !== 1 ? 's' : ''}…
        </p>
      )}
    </ToolCard>
  )
}

// ─── AnalysisCard (pipeline/analysis) ────────────────────────────────────────

export function AnalysisCard({
  args,
  result,
  pending,
  failed,
}: {
  args: PipelineAnalysisArgs
  result?: PipelineAnalysisResult
  pending: boolean
  failed: boolean
}) {
  return (
    <ToolCard>
      <ToolBadge
        label={
          failed
            ? 'Analysis failed'
            : pending
              ? 'Analysing data…'
              : 'Analysis complete'
        }
        pending={pending}
        failed={failed}
      />
      {result ? (
        <div>
          <p className="text-(--sea-ink-soft) opacity-60">
            {result.chart_configs.length} chart
            {result.chart_configs.length !== 1 ? 's' : ''} ready
          </p>
        </div>
      ) : (
        <p className="text-(--sea-ink-soft)">
          Processing {args.unified_rows.toLocaleString()} rows…
        </p>
      )}
    </ToolCard>
  )
}

// ─── Registry ─────────────────────────────────────────────────────────────────
// The registry uses a broad dispatch type; each card is typed via its props above.
// The cast below is intentional — the dispatcher in index.tsx passes unknown args/result
// and each card narrows to its specific types internally.

type ToolCardComponent = (props: {
  args: any
  result?: any
  pending: boolean
  failed: boolean
}) => React.ReactElement | null

export const TOOL_COMPONENTS: Record<string, ToolCardComponent> = {
  'coordinator/list_datasets': DatasetListCard,
  'coordinator/datasets_selected': DatasetsSelectedCard,
  'pipeline/extraction': ExtractionCard,
  'pipeline/normalization': NormalizationCard,
  'pipeline/analysis': AnalysisCard,
}
