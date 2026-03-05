import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BarChart as ReBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import {
  chatQueryOptions
} from '#/queries/chat.queries'
import type {ResultMessage, StatusMessage} from '#/queries/chat.queries';

export const Route = createFileRoute('/')({ component: App })

// ─── Types ────────────────────────────────────────────────────────────────────

interface VisualizationData {
  query: string
  reason: string
}

// ─── Icons ────────────────────────────────────────────────────────────────────

function DatabaseIcon() {
  return (
    <svg
      className="w-12 h-12 opacity-30"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-4 h-4"
    >
      <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" />
      <path d="m21.854 2.147-10.94 10.939" />
    </svg>
  )
}

// ─── Canvas ───────────────────────────────────────────────────────────────────

function EmptyCanvas() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-[var(--sea-ink-soft)]">
      <DatabaseIcon />
      <div className="text-center space-y-1">
        <p className="font-semibold text-[var(--sea-ink)]">No data yet</p>
        <p className="text-sm">Ask a question to see data visualisations here</p>
      </div>
    </div>
  )
}

// ─── Mock datasets ────────────────────────────────────────────────────────────

interface Dataset {
  kpis: { label: string; value: string; sub: string }[]
  bar: { label: string; color: string; formatValue?: (v: number) => string; data: { year: string; value: number }[] }
  spark: { label: string; unit: string; color: string; data: { year: string; value: number }[] }
}

const DATASETS: Record<string, Dataset> = {
  housing: {
    kpis: [
      { label: 'HDB completions', value: '26,400', sub: '2024 (projected)' },
      { label: 'Median resale price', value: '$565k', sub: '4-room flat, 2024' },
      { label: 'New BTO launches', value: '19,600', sub: 'FY2024 units' },
    ],
    bar: {
      label: 'HDB flat completions by year',
      color: '#0891b2',
      formatValue: (v) => `${(v / 1000).toFixed(1)}k`,
      data: [
        { year: '2018', value: 18200 },
        { year: '2019', value: 14600 },
        { year: '2020', value: 12900 },
        { year: '2021', value: 11400 },
        { year: '2022', value: 9800 },
        { year: '2023', value: 23100 },
        { year: '2024', value: 26400 },
      ],
    },
    spark: {
      label: 'Median resale flat price (S$\'000)',
      unit: 'k',
      color: '#7c3aed',
      data: [
        { year: '2018', value: 430 },
        { year: '2019', value: 435 },
        { year: '2020', value: 448 },
        { year: '2021', value: 495 },
        { year: '2022', value: 543 },
        { year: '2023', value: 558 },
        { year: '2024', value: 565 },
      ],
    },
  },

  employment: {
    kpis: [
      { label: 'Employment rate', value: '68.6%', sub: '2024 resident workforce' },
      { label: 'Unemployment rate', value: '1.9%', sub: 'Resident, Q3 2024' },
      { label: 'Labour force', value: '2.41M', sub: 'Residents, 2024' },
    ],
    bar: {
      label: 'Resident employment rate by year (%)',
      color: '#059669',
      formatValue: (v) => `${v.toFixed(1)}%`,
      data: [
        { year: '2018', value: 67.2 },
        { year: '2019', value: 67.5 },
        { year: '2020', value: 65.3 },
        { year: '2021', value: 65.9 },
        { year: '2022', value: 67.4 },
        { year: '2023', value: 68.1 },
        { year: '2024', value: 68.6 },
      ],
    },
    spark: {
      label: 'Resident unemployment rate (%)',
      unit: '%',
      color: '#e11d48',
      data: [
        { year: '2018', value: 3.1 },
        { year: '2019', value: 3.2 },
        { year: '2020', value: 4.1 },
        { year: '2021', value: 3.5 },
        { year: '2022', value: 2.6 },
        { year: '2023', value: 2.1 },
        { year: '2024', value: 1.9 },
      ],
    },
  },

  education: {
    kpis: [
      { label: 'University enrolment', value: '81,200', sub: 'AY2023/24 undergrads' },
      { label: 'Participation rate', value: '51.5%', sub: 'Uni entry rate, 2024' },
      { label: 'Preschool coverage', value: '96.8%', sub: 'K1–K2 enrolment, 2024' },
    ],
    bar: {
      label: 'University undergraduate enrolment',
      color: '#d97706',
      formatValue: (v) => `${(v / 1000).toFixed(1)}k`,
      data: [
        { year: '2018', value: 74800 },
        { year: '2019', value: 75900 },
        { year: '2020', value: 76500 },
        { year: '2021', value: 77300 },
        { year: '2022', value: 78600 },
        { year: '2023', value: 80100 },
        { year: '2024', value: 81200 },
      ],
    },
    spark: {
      label: 'University entry participation rate (%)',
      unit: '%',
      color: '#d97706',
      data: [
        { year: '2018', value: 44.8 },
        { year: '2019', value: 45.7 },
        { year: '2020', value: 46.9 },
        { year: '2021', value: 48.2 },
        { year: '2022', value: 49.6 },
        { year: '2023', value: 50.8 },
        { year: '2024', value: 51.5 },
      ],
    },
  },

  healthcare: {
    kpis: [
      { label: 'Hospital beds', value: '13,900', sub: 'Public sector, 2024' },
      { label: 'Life expectancy', value: '83.9 yrs', sub: 'At birth, 2024' },
      { label: 'MOH expenditure', value: 'S$16.8B', sub: 'FY2024 budget' },
    ],
    bar: {
      label: 'MOH healthcare expenditure (S$B)',
      color: '#dc2626',
      formatValue: (v) => `$${v.toFixed(1)}B`,
      data: [
        { year: '2018', value: 10.2 },
        { year: '2019', value: 11.3 },
        { year: '2020', value: 13.4 },
        { year: '2021', value: 14.1 },
        { year: '2022', value: 14.8 },
        { year: '2023', value: 15.9 },
        { year: '2024', value: 16.8 },
      ],
    },
    spark: {
      label: 'Life expectancy at birth (years)',
      unit: '',
      color: '#059669',
      data: [
        { year: '2018', value: 83.2 },
        { year: '2019', value: 83.4 },
        { year: '2020', value: 83.5 },
        { year: '2021', value: 83.0 },
        { year: '2022', value: 83.3 },
        { year: '2023', value: 83.7 },
        { year: '2024', value: 83.9 },
      ],
    },
  },

  transport: {
    kpis: [
      { label: 'MRT ridership', value: '3.12M', sub: 'Daily avg, 2024' },
      { label: 'Bus ridership', value: '3.78M', sub: 'Daily avg, 2024' },
      { label: 'EV registrations', value: '28,400', sub: 'Cumulative, 2024' },
    ],
    bar: {
      label: 'MRT daily average ridership (M trips)',
      color: '#0891b2',
      formatValue: (v) => `${v.toFixed(2)}M`,
      data: [
        { year: '2018', value: 3.04 },
        { year: '2019', value: 3.11 },
        { year: '2020', value: 1.87 },
        { year: '2021', value: 2.21 },
        { year: '2022', value: 2.74 },
        { year: '2023', value: 3.02 },
        { year: '2024', value: 3.12 },
      ],
    },
    spark: {
      label: 'Electric vehicle registrations (cumulative)',
      unit: 'k',
      color: '#059669',
      data: [
        { year: '2018', value: 1.2 },
        { year: '2019', value: 2.1 },
        { year: '2020', value: 3.5 },
        { year: '2021', value: 6.4 },
        { year: '2022', value: 11.8 },
        { year: '2023', value: 19.7 },
        { year: '2024', value: 28.4 },
      ],
    },
  },

  population: {
    kpis: [
      { label: 'Total population', value: '5.92M', sub: 'June 2024' },
      { label: 'Citizen population', value: '3.61M', sub: 'June 2024' },
      { label: 'Median age', value: '42.7', sub: 'Residents, 2024' },
    ],
    bar: {
      label: 'Resident population by year (M)',
      color: '#7c3aed',
      formatValue: (v) => `${v.toFixed(2)}M`,
      data: [
        { year: '2018', value: 3.99 },
        { year: '2019', value: 4.03 },
        { year: '2020', value: 4.04 },
        { year: '2021', value: 4.07 },
        { year: '2022', value: 4.11 },
        { year: '2023', value: 4.15 },
        { year: '2024', value: 4.19 },
      ],
    },
    spark: {
      label: 'Median age of resident population',
      unit: '',
      color: '#d97706',
      data: [
        { year: '2018', value: 40.8 },
        { year: '2019', value: 41.1 },
        { year: '2020', value: 41.5 },
        { year: '2021', value: 41.8 },
        { year: '2022', value: 42.1 },
        { year: '2023', value: 42.4 },
        { year: '2024', value: 42.7 },
      ],
    },
  },
}

function pickDataset(query: string): Dataset {
  const q = query.toLowerCase()
  if (/hdb|bto|flat|resale|housing|property|rent/.test(q)) return DATASETS.housing
  if (/employ|job|work|labour|labor|unemploy|workforce/.test(q)) return DATASETS.employment
  if (/educat|school|university|student|learn|skill|psle/.test(q)) return DATASETS.education
  if (/health|hospital|medic|doctor|moh|clinic|disease/.test(q)) return DATASETS.healthcare
  if (/transport|mrt|bus|train|ev|electric|car|vehicle|road/.test(q)) return DATASETS.transport
  if (/populat|demograph|age|citizen|birth|fertility|senior/.test(q)) return DATASETS.population
  // default to housing as most common topic
  return DATASETS.housing
}

// ─── Bar Chart ────────────────────────────────────────────────────────────────

function BarChart({
  data,
  label,
  color = '#0891b2',
  formatValue,
}: {
  data: { year: string; value: number }[]
  label: string
  color?: string
  formatValue?: (v: number) => string
}) {
  const fmt = formatValue ?? ((v: number) => v.toLocaleString())
  return (
    <div className="space-y-1">
      <p className="island-kicker">{label}</p>
      <div className="island-shell rounded-xl p-4">
        <ResponsiveContainer width="100%" height={220}>
          <ReBarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="3 3" />
            <XAxis dataKey="year" tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }} axisLine={false} tickLine={false} width={52} />
            <Tooltip
              formatter={(v: number) => [fmt(v), label]}
              contentStyle={{ background: 'var(--surface-strong)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: 'var(--sea-ink)', fontWeight: 600 }}
              cursor={{ fill: 'var(--line)' }}
            />
            <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} maxBarSize={48} />
          </ReBarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ─── Sparkline ────────────────────────────────────────────────────────────────

function SparkLine({
  data,
  label,
  unit,
  color = '#0891b2',
}: {
  data: { year: string; value: number }[]
  label: string
  unit?: string
  color?: string
}) {
  const latest = data.at(-1)!
  const prev = data.at(-2)!
  const delta = latest.value - prev.value
  const isUp = delta >= 0
  const fmt = (v: number) => `${v.toFixed(1)}${unit}`

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <p className="island-kicker">{label}</p>
        <span className="text-xs font-semibold" style={{ color: isUp ? 'var(--palm)' : '#e11d48' }}>
          {isUp ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}{unit} vs prior year
        </span>
      </div>
      <div className="island-shell rounded-xl p-4">
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id={`area-fill-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.18} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="3 3" />
            <XAxis dataKey="year" tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }} axisLine={false} tickLine={false} width={52} domain={['auto', 'auto']} />
            <Tooltip
              formatter={(v: number) => [fmt(v), label]}
              contentStyle={{ background: 'var(--surface-strong)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: 'var(--sea-ink)', fontWeight: 600 }}
            />
            <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill={`url(#area-fill-${color.replace('#', '')})`} dot={{ r: 3.5, fill: color, strokeWidth: 0 }} activeDot={{ r: 5 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="island-shell rounded-xl p-4 space-y-0.5">
      <p className="island-kicker">{label}</p>
      <p className="text-2xl font-bold text-[var(--sea-ink)]">{value}</p>
      <p className="text-xs text-[var(--sea-ink-soft)]">{sub}</p>
    </div>
  )
}

// ─── Visualization Panel ─────────────────────────────────────────────────────

function VisualizationPanel({ data }: { data: VisualizationData }) {
  const ds = pickDataset(data.query)

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div className="space-y-2">
        <p className="island-kicker">Enriched query</p>
        <p className="font-semibold text-[var(--sea-ink)] leading-snug">{data.query}</p>
      </div>

      {data.reason && (
        <div className="space-y-2">
          <p className="island-kicker">Insight</p>
          <p className="text-sm text-[var(--sea-ink-soft)] leading-relaxed">{data.reason}</p>
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-3 gap-3">
        {ds.kpis.map((kpi) => (
          <StatCard key={kpi.label} label={kpi.label} value={kpi.value} sub={kpi.sub} />
        ))}
      </div>

      {/* Bar chart */}
      <BarChart
        data={ds.bar.data}
        label={ds.bar.label}
        color={ds.bar.color}
        formatValue={ds.bar.formatValue}
      />

      {/* Sparkline */}
      <SparkLine
        data={ds.spark.data}
        label={ds.spark.label}
        unit={ds.spark.unit}
        color={ds.spark.color}
      />
    </div>
  )
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
  )
}

function CheckIcon() {
  return (
    <svg className="w-3 h-3 text-[var(--palm)] shrink-0" viewBox="0 0 12 12" fill="currentColor">
      <path d="M10 3L5 8.5 2 5.5l-1 1 4 4 6-7-1-1z" />
    </svg>
  )
}

function PipelineSteps({
  steps,
  isFetching,
}: {
  steps: StatusMessage[]
  isFetching: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  if (steps.length === 0) return null

  return (
    <div className="rounded-xl border border-[var(--line)] overflow-hidden text-sm bg-[var(--surface-strong)] shadow-sm">
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-[var(--sea-ink-soft)] hover:bg-[var(--chip-bg)] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {isFetching ? <Spinner /> : <CheckIcon />}
        <span className="flex-1 text-xs font-medium">
          {isFetching ? (steps.at(-1)?.message ?? 'Working…') : 'Done'}
        </span>
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M2 4l4 4 4-4" />
        </svg>
      </button>
      {expanded && (
        <div className="px-3 pb-2 pt-1 space-y-1 border-t border-[var(--line)]">
          {steps.map((step, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-[var(--sea-ink-soft)] py-0.5">
              {i === steps.length - 1 && isFetching ? <Spinner /> : <CheckIcon />}
              <span>{step.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ResultBubble({ result }: { result: ResultMessage }) {
  if (!result.accepted) {
    return (
      <div className="rounded-xl px-4 py-3 text-sm bg-orange-50 border border-orange-200 text-orange-800 dark:bg-orange-950 dark:border-orange-800 dark:text-orange-200">
        <div className="flex gap-2">
          <span className="shrink-0">⚠</span>
          <p>{result.reason}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl px-4 py-3 text-sm bg-[var(--surface-strong)] border border-[var(--line)] space-y-1">
      {result.refined_query && (
        <p className="font-medium text-[var(--sea-ink)]">{result.refined_query}</p>
      )}
      {result.reason && (
        <p className="text-xs text-[var(--sea-ink-soft)]">{result.reason}</p>
      )}
    </div>
  )
}

function ChatMessage({
  question,
  onAccepted,
}: {
  question: string
  onAccepted: (result: ResultMessage) => void
}) {
  const options = useMemo(() => chatQueryOptions(question), [question])
  const { error, data = [], isFetching } = useQuery(options)
  const calledRef = useRef(false)

  const statusMessages = data.filter((m): m is StatusMessage => m.type === 'status')
  const result = data.find((m): m is ResultMessage => m.type === 'result')

  useEffect(() => {
    if (result?.accepted && !calledRef.current) {
      calledRef.current = true
      onAccepted(result)
    }
  }, [result, onAccepted])

  return (
    <div className="space-y-2">
      {/* User bubble */}
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm bg-[var(--lagoon-deep)] text-white">
          {question}
        </div>
      </div>

      {/* Pipeline status + result */}
      {(statusMessages.length > 0 || error) && (
        <div className="space-y-2">
          <PipelineSteps steps={statusMessages} isFetching={isFetching} />
          {error && (
            <p className="text-xs text-red-500 px-1">Error: {error.message}</p>
          )}
          {result && <ResultBubble result={result} />}
        </div>
      )}
    </div>
  )
}

// ─── App ──────────────────────────────────────────────────────────────────────

function App() {
  const [questions, setQuestions] = useState<string[]>([])
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [visualizationData, setVisualizationData] = useState<VisualizationData | null>({
    query: 'HDB flat completions and resale prices in Singapore (2018–2024)',
    reason: 'HDB completions dipped to a low of 9,800 in 2022 due to COVID-19 construction delays, before ramping up sharply. Median resale prices rose steadily throughout, reaching a record $565k for a 4-room flat in 2024.',
  })
  const bottomRef = useRef<HTMLDivElement>(null)

  const submitMessage = () => {
    const q = currentQuestion.trim()
    if (!q) return
    setQuestions((prev) => [...prev, q])
    setCurrentQuestion('')
  }

  // Auto-scroll chat to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [questions])

  const handleAccepted = (result: ResultMessage) => {
    setVisualizationData({
      query: result.refined_query ?? result.reason,
      reason: result.reason,
    })
  }

  return (
    <main className="flex" style={{ height: 'calc(100vh - 57px)' }}>
      {/* Left — Canvas */}
      <div className="flex-1 overflow-hidden border-r border-[var(--line)] bg-[var(--foam)]">
        {visualizationData ? (
          <VisualizationPanel data={visualizationData} />
        ) : (
          <EmptyCanvas />
        )}
      </div>

      {/* Right — Chat */}
      <div className="w-[400px] shrink-0 flex flex-col overflow-hidden bg-[var(--foam)]">
        {/* Header */}
        <div className="px-4 py-3 border-b border-[var(--line)] bg-[var(--header-bg)] backdrop-blur-lg shrink-0">
          <p className="font-semibold text-sm text-[var(--sea-ink)]">Analytics Assistant</p>
          <p className="text-xs text-[var(--sea-ink-soft)]">Ask about Singapore policy data</p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 bg-[var(--sand)]">
          {questions.length === 0 && (
            <p className="text-sm text-[var(--sea-ink-soft)] text-center mt-8">
              Hi! Ask me anything about Singapore policy data — I can help you find relevant datasets and prepare visualisations.
            </p>
          )}
          {questions.map((q) => (
            <ChatMessage key={q} question={q} onAccepted={handleAccepted} />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 px-4 py-3 border-t border-[var(--line)] bg-[var(--surface-strong)]">
          <div className="flex items-center gap-2">
            <input
              className="flex-1 px-3 py-2 text-sm rounded-xl border border-slate-200 bg-white text-[var(--sea-ink)] placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[var(--lagoon)] focus:ring-offset-1"
              value={currentQuestion}
              onChange={(e) => setCurrentQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') submitMessage() }}
              placeholder="Ask about Singapore data…"
            />
            <button
              onClick={submitMessage}
              disabled={!currentQuestion.trim()}
              className="flex items-center justify-center w-9 h-9 rounded-xl bg-[var(--lagoon-deep)] text-white disabled:opacity-40 transition-opacity shrink-0"
            >
              <SendIcon />
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}
