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

export function EmptyCanvas() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-[var(--sea-ink-soft)]">
      <DatabaseIcon />
      <div className="text-center space-y-1">
        <p className="font-semibold text-gray-400">No data yet</p>
        <p className="text-sm text-gray-400">
          Ask a question to see data visualisations here
        </p>
      </div>
    </div>
  )
}
