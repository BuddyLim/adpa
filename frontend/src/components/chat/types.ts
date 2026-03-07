import type { PipelineMessage, ToolCallMessage, ToolResultMessage } from '#/queries/chat.queries'

export interface ToolInvocation {
  tool: ToolCallMessage['tool']
  args: ToolCallMessage['args']
  result: ToolResultMessage['result'] | undefined
  pending: boolean
  failed: boolean
}

export type TimelineItem =
  | { kind: 'status'; message: string }
  | ({ kind: 'tool' } & ToolInvocation)

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

export function buildTimeline(messages: PipelineMessage[], rejected?: boolean): TimelineItem[] {
  const items: TimelineItem[] = []

  for (const msg of messages) {
    if (msg.type === 'status') {
      items.push({ kind: 'status', message: msg.message })
    } else if (msg.type === 'tool_call') {
      items.push({ kind: 'tool', tool: msg.tool, args: msg.args, result: undefined, pending: true, failed: false })
    } else if (msg.type === 'tool_result') {
      // Find the last pending tool item with the same tool name and resolve it
      for (let i = items.length - 1; i >= 0; i--) {
        const item = items[i]
        if (item.kind === 'tool' && item.tool === msg.tool && item.pending) {
          items[i] = { ...item, result: msg.result, pending: false }
          break
        }
      }
    }
  }

  // On rejection, any tool that never received a result was abandoned mid-flight
  if (rejected) {
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.kind === 'tool' && item.pending) {
        items[i] = { ...item, pending: false, failed: true }
      }
    }
  }

  return items
}
