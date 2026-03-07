import { memo, useRef } from 'react'
import {
  BarChart as ReBarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Sector,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import type { ChartConfig } from '#/queries/chat.queries'

function labelColor(label: string): string {
  let hash = 0
  for (let i = 0; i < label.length; i++) {
    hash = (hash * 31 + label.charCodeAt(i)) >>> 0
  }
  const hue = (hash * 137.508) % 360
  return `hsl(${hue.toFixed(0)}, 62%, 48%)`
}

const CHART_STYLE = {
  contentStyle: {
    background: 'var(--surface-strong)',
    border: '1px solid var(--line)',
    borderRadius: 8,
    fontSize: 12,
  },
  labelStyle: { color: 'var(--sea-ink)', fontWeight: 600 },
  formatter: (
    value: number | string | undefined,
    name: string | number | undefined,
  ) => {
    const val =
      typeof value === 'number'
        ? [value.toLocaleString(), '']
        : [value ?? '', '']

    return [val, name]
  },
}

export const DynamicChart = memo(function DynamicChart({
  config,
}: {
  config: ChartConfig
}) {
  const chartRef = useRef<HTMLDivElement>(null)

  const sanitizeFilename = (str: string) =>
    str.replace(/[^a-z0-9]/gi, '_').toLowerCase()

  const exportCsv = () => {
    if (!config.data.length) return
    const keys = Object.keys(config.data[0])
    const rows = [
      keys.join(','),
      ...config.data.map((row) =>
        keys
          .map((k) => {
            const s = String(row[k] ?? '')
            return s.includes(',') ? `"${s}"` : s
          })
          .join(','),
      ),
    ]
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${sanitizeFilename(config.title)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const exportPng = () => {
    const svgEl = chartRef.current?.querySelector('svg')
    if (!svgEl) return
    const { width, height } = svgEl.getBoundingClientRect()
    const serializer = new XMLSerializer()
    const svgStr = serializer.serializeToString(svgEl)
    const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const img = new Image()
    img.onload = () => {
      const scale = window.devicePixelRatio || 1
      const canvas = document.createElement('canvas')
      canvas.width = width * scale
      canvas.height = height * scale
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.scale(scale, scale)
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, width, height)
      ctx.drawImage(img, 0, 0, width, height)
      URL.revokeObjectURL(url)
      canvas.toBlob((pngBlob) => {
        if (!pngBlob) return
        const a = document.createElement('a')
        a.href = URL.createObjectURL(pngBlob)
        a.download = `${sanitizeFilename(config.title)}.png`
        a.click()
        URL.revokeObjectURL(a.href)
      })
    }
    img.src = url
  }

  return (
    <div className="space-y-1">
      <div className="flex items-start justify-between gap-2">
        <p className="island-kicker">{config.title}</p>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={exportCsv}
            title="Export CSV"
            className="p-1 rounded text-(--sea-ink-soft) hover:text-(--sea-ink) hover:bg-(--line) transition-colors"
          >
            <svg
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="w-3.5 h-3.5"
            >
              <rect x="2" y="1" width="12" height="14" rx="1.5" />
              <path d="M5 5h6M5 8h6M5 11h4" strokeLinecap="round" />
            </svg>
          </button>
          <button
            onClick={exportPng}
            title="Export PNG"
            className="p-1 rounded text-(--sea-ink-soft) hover:text-(--sea-ink) hover:bg-(--line) transition-colors"
          >
            <svg
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="w-3.5 h-3.5"
            >
              <path
                d="M8 2v8m0 0-2.5-2.5M8 10l2.5-2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path d="M3 13h10" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>
      <p className="text-xs text-(--sea-ink-soft)">{config.description}</p>
      <div ref={chartRef} className="island-shell rounded-xl p-4 h-72">
        {config.chart_type === 'bar' && (
          <ReBarChart
            responsive
            height={'100%'}
            data={config.data}
            margin={{ top: 16, right: 8, bottom: 16, left: 16 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="var(--line)"
              strokeDasharray="3 3"
            />
            <XAxis
              dataKey={config.x_key ?? undefined}
              tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }}
              axisLine={false}
              tickLine={false}
              label={
                config.x_label
                  ? {
                      value: config.x_label,
                      position: 'insideBottom',
                      offset: -4,
                      fontSize: 11,
                    }
                  : undefined
              }
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }}
              axisLine={false}
              tickLine={false}
              width={60}
              label={
                config.y_label
                  ? {
                      value: config.y_label,
                      angle: -90,
                      position: 'insideLeft',
                      fontSize: 11,
                      dy: 80,
                    }
                  : undefined
              }
            />
            <Tooltip {...CHART_STYLE} cursor={{ fill: 'var(--line)' }} />
            {config.y_keys.map((key) => (
              <Bar
                key={key}
                dataKey={key}
                name={config.series_labels[key] ?? key}
                fill={labelColor(config.series_labels[key] ?? key)}
                radius={[4, 4, 0, 0]}
                maxBarSize={48}
              />
            ))}
          </ReBarChart>
        )}

        {config.chart_type === 'line' && (
          <LineChart
            responsive
            height={'100%'}
            data={config.data}
            margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="var(--line)"
              strokeDasharray="3 3"
            />
            <XAxis
              dataKey={config.x_key ?? undefined}
              tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }}
              axisLine={false}
              tickLine={false}
              width={60}
            />
            <Tooltip {...CHART_STYLE} />
            {config.y_keys.map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={config.series_labels[key] ?? key}
                stroke={labelColor(config.series_labels[key] ?? key)}
                strokeWidth={2}
                dot={{
                  r: 3,
                  strokeWidth: 0,
                  fill: labelColor(config.series_labels[key] ?? key),
                }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        )}

        {config.chart_type === 'area' && (
          <AreaChart
            responsive
            height={'100%'}
            data={config.data}
            margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
          >
            <defs>
              {config.y_keys.map((key, i) => (
                <linearGradient
                  key={key}
                  id={`area-grad-${i}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="5%"
                    stopColor={labelColor(config.series_labels[key] ?? key)}
                    stopOpacity={0.18}
                  />
                  <stop
                    offset="95%"
                    stopColor={labelColor(config.series_labels[key] ?? key)}
                    stopOpacity={0}
                  />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid
              vertical={false}
              stroke="var(--line)"
              strokeDasharray="3 3"
            />
            <XAxis
              dataKey={config.x_key ?? undefined}
              tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--sea-ink-soft)' }}
              axisLine={false}
              tickLine={false}
              width={60}
              domain={['auto', 'auto']}
            />
            <Tooltip {...CHART_STYLE} />
            {config.y_keys.map((key, i) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                name={config.series_labels[key] ?? key}
                stroke={labelColor(config.series_labels[key] ?? key)}
                strokeWidth={2}
                fill={`url(#area-grad-${i})`}
                dot={{
                  r: 3.5,
                  fill: labelColor(config.series_labels[key] ?? key),
                  strokeWidth: 0,
                }}
                activeDot={{ r: 5 }}
              />
            ))}
          </AreaChart>
        )}

        {config.chart_type === 'pie' && (
          <PieChart responsive height={'100%'}>
            <Pie
              data={config.data}
              dataKey={config.value_key ?? 'value'}
              nameKey={config.name_key ?? 'group'}
              cx="50%"
              cy="50%"
              outerRadius={80}
              label={({ name, percent }) =>
                `${String(name)} ${((percent ?? 0) * 100).toFixed(0)}%`
              }
              labelLine={true}
              shape={(
                props: React.ComponentProps<typeof Sector> & { name?: string },
              ) => (
                <Sector
                  {...props}
                  fill={labelColor(String(props.name ?? ''))}
                />
              )}
            />
            <Tooltip {...CHART_STYLE} />
          </PieChart>
        )}
      </div>
    </div>
  )
})
