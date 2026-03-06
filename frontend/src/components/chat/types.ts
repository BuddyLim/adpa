import type { ToolCallMessage, ToolResultMessage } from '#/queries/chat.queries'

export interface ToolInvocation {
  tool: ToolCallMessage['tool']
  args: ToolCallMessage['args']
  result: ToolResultMessage['result'] | undefined
  pending: boolean
}

export const TOOL_LABELS: Partial<
  Record<ToolCallMessage['tool'], { pending: string; done: string }>
> = {
  'coordinator/list_datasets': {
    pending: 'Loading datasets…',
    done: 'Datasets available',
  },
  'coordinator/datasets_selected': {
    pending: 'Selecting datasets…',
    done: 'Datasets selected',
  },
  'pipeline/extraction': {
    pending: 'Extracting data…',
    done: 'Data extracted',
  },
  'pipeline/normalization': {
    pending: 'Normalizing data…',
    done: 'Data normalized',
  },
  'pipeline/analysis': {
    pending: 'Analysing data…',
    done: 'Analysis complete',
  },
}

export function buildToolInvocations(
  calls: ToolCallMessage[],
  results: ToolResultMessage[],
): ToolInvocation[] {
  const resultIndexByTool: Partial<Record<ToolCallMessage['tool'], number>> = {}
  const resultsByTool: Partial<
    Record<ToolCallMessage['tool'], ToolResultMessage[]>
  > = {}

  for (const r of results) {
    const bucket = (resultsByTool[r.tool] ??= [])
    bucket.push(r)
  }

  return calls.map((call) => {
    const idx = resultIndexByTool[call.tool] ?? 0
    const matchingResult = resultsByTool[call.tool]?.[idx]
    resultIndexByTool[call.tool] = idx + 1
    return {
      tool: call.tool,
      args: call.args,
      result: matchingResult?.result,
      pending: !matchingResult,
    }
  })
}
