import {
  BarChart as ReBarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import type { ChartConfig } from '#/queries/chat.queries'

const PALETTE = ['#0891b2', '#7c3aed', '#059669', '#d97706', '#e11d48']

const CHART_STYLE = {
  contentStyle: {
    background: 'var(--surface-strong)',
    border: '1px solid var(--line)',
    borderRadius: 8,
    fontSize: 12,
  },
  labelStyle: { color: 'var(--sea-ink)', fontWeight: 600 },
}

export function DynamicChart({ config }: { config: ChartConfig }) {
  return (
    <div className="space-y-1">
      <p className="island-kicker">{config.title}</p>
      <p className="text-xs text-(--sea-ink-soft)">{config.description}</p>
      <div className="island-shell rounded-xl p-4 h-72">
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
            {config.y_keys.map((key, i) => (
              <Bar
                key={key}
                dataKey={key}
                name={config.series_labels[key] ?? key}
                fill={PALETTE[i % PALETTE.length]}
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
            {config.y_keys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={config.series_labels[key] ?? key}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={{
                  r: 3,
                  strokeWidth: 0,
                  fill: PALETTE[i % PALETTE.length],
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
                    stopColor={PALETTE[i % PALETTE.length]}
                    stopOpacity={0.18}
                  />
                  <stop
                    offset="95%"
                    stopColor={PALETTE[i % PALETTE.length]}
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
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                fill={`url(#area-grad-${i})`}
                dot={{
                  r: 3.5,
                  fill: PALETTE[i % PALETTE.length],
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
              labelLine={false}
            >
              {config.data.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Pie>
            <Tooltip {...CHART_STYLE} />
          </PieChart>
        )}
      </div>
    </div>
  )
}
