import { describe, it, expect } from 'vitest'
import { buildTimeline } from './types'
import type { PipelineMessage } from '../../queries/chat.queries'

describe('buildTimeline', () => {
  // ─── Good flows ───────────────────────────────────────────────────────────

  it('maps status messages to status items', () => {
    const messages: PipelineMessage[] = [
      { type: 'status', message: 'Thinking...' },
      { type: 'status', message: 'Processing...' },
    ]
    expect(buildTimeline(messages)).toEqual([
      { kind: 'status', message: 'Thinking...' },
      { kind: 'status', message: 'Processing...' },
    ])
  })

  it('creates a pending tool item for a tool_call', () => {
    const messages: PipelineMessage[] = [
      { type: 'tool_call', tool: 'coordinator/list_datasets', args: {} },
    ]
    expect(buildTimeline(messages)).toEqual([
      {
        kind: 'tool',
        tool: 'coordinator/list_datasets',
        args: {},
        result: undefined,
        pending: true,
        failed: false,
      },
    ])
  })

  it('resolves a pending tool item when matching tool_result arrives', () => {
    const result = [{ title: 'Dataset A', path: '/a', description: 'desc' }]
    const messages: PipelineMessage[] = [
      { type: 'tool_call', tool: 'coordinator/list_datasets', args: {} },
      { type: 'tool_result', tool: 'coordinator/list_datasets', result },
    ]
    const timeline = buildTimeline(messages)
    expect(timeline).toHaveLength(1)
    expect(timeline[0]).toMatchObject({
      kind: 'tool',
      tool: 'coordinator/list_datasets',
      result,
      pending: false,
      failed: false,
    })
  })

  it('handles multiple interleaved tools independently', () => {
    const extractionResult = {
      datasets: [{ title: 'A', row_count: 100 }],
      total_rows: 100,
    }
    const normResult = { unified_rows: 100, columns: ['a', 'b'] }
    const messages: PipelineMessage[] = [
      { type: 'tool_call', tool: 'pipeline/extraction', args: { datasets: ['A'] } },
      {
        type: 'tool_call',
        tool: 'pipeline/normalization',
        args: { n_sources: 1, datasets: ['A'] },
      },
      { type: 'tool_result', tool: 'pipeline/extraction', result: extractionResult },
      { type: 'tool_result', tool: 'pipeline/normalization', result: normResult },
    ]
    const timeline = buildTimeline(messages)
    expect(timeline).toHaveLength(2)
    expect(timeline[0]).toMatchObject({
      tool: 'pipeline/extraction',
      result: extractionResult,
      pending: false,
    })
    expect(timeline[1]).toMatchObject({
      tool: 'pipeline/normalization',
      result: normResult,
      pending: false,
    })
  })

  it('ignores result, error, analysis_text, and conversation_started message types', () => {
    const messages: PipelineMessage[] = [
      { type: 'result', accepted: true, reason: 'ok', refined_query: 'ok' },
      { type: 'error', message: 'oops' },
      { type: 'analysis_text', chunk: 'some text' },
      { type: 'conversation_started', conversation_id: 'id', title: 'title' },
    ]
    expect(buildTimeline(messages)).toEqual([])
  })

  it('mixes status and tool items in order', () => {
    const messages: PipelineMessage[] = [
      { type: 'status', message: 'Starting...' },
      { type: 'tool_call', tool: 'coordinator/list_datasets', args: {} },
      { type: 'status', message: 'Almost done...' },
    ]
    const timeline = buildTimeline(messages)
    expect(timeline[0]).toMatchObject({ kind: 'status', message: 'Starting...' })
    expect(timeline[1]).toMatchObject({ kind: 'tool', tool: 'coordinator/list_datasets' })
    expect(timeline[2]).toMatchObject({ kind: 'status', message: 'Almost done...' })
  })

  // ─── Bad flows ────────────────────────────────────────────────────────────

  it('does not crash when tool_result has no matching tool_call', () => {
    const messages: PipelineMessage[] = [
      { type: 'tool_result', tool: 'coordinator/list_datasets', result: [] },
    ]
    expect(() => buildTimeline(messages)).not.toThrow()
    expect(buildTimeline(messages)).toEqual([])
  })

  it('marks pending tools as failed when rejected=true', () => {
    const messages: PipelineMessage[] = [
      { type: 'tool_call', tool: 'coordinator/list_datasets', args: {} },
    ]
    const timeline = buildTimeline(messages, true)
    expect(timeline[0]).toMatchObject({
      kind: 'tool',
      pending: false,
      failed: true,
    })
  })

  it('does not affect already-resolved tools when rejected=true', () => {
    const result = [{ title: 'A', path: '/a' }]
    const messages: PipelineMessage[] = [
      { type: 'tool_call', tool: 'coordinator/list_datasets', args: {} },
      { type: 'tool_result', tool: 'coordinator/list_datasets', result },
    ]
    const timeline = buildTimeline(messages, true)
    expect(timeline[0]).toMatchObject({ pending: false, failed: false, result })
  })

  it('handles empty message array', () => {
    expect(buildTimeline([])).toEqual([])
  })
})
