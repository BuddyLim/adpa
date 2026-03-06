import type { PipelineAnalysisResult } from '#/queries/chat.queries'
import { DynamicChart } from './DynamicChart'

export interface VisualizationData {
  query: string
  reason: string
  analysisResult?: PipelineAnalysisResult
}

export function VisualizationPanel({ items }: { items: VisualizationData[] }) {
  return (
    <div className="h-full overflow-y-auto p-12 space-y-6">
      {items.map((item, idx) =>
        item.analysisResult ? (
          item.analysisResult.chart_configs.map((cfg, i) => (
            <DynamicChart key={`${idx}-${i}`} config={cfg} />
          ))
        ) : (
          item.reason && (
            <div key={idx} className="space-y-2">
              <p className="island-kicker">Insight</p>
              <p className="text-sm text-(--sea-ink-soft) leading-relaxed">
                {item.reason}
              </p>
            </div>
          )
        ),
      )}
    </div>
  )
}
