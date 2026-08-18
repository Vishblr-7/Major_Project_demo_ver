import { Card } from 'antd'
import type { ReactNode } from 'react'
import { useCountUp } from '../hooks/useCountUp'

interface KpiCardProps {
  label: string
  value: string | number | null | undefined
  unit?: string
  icon?: ReactNode
  sub?: string
  accent?: string
  /** Animate numeric values counting up from 0 -- cosmetic only, the value
   * shown at rest is always the same real number passed in. */
  animate?: boolean
}

export function formatValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return 'N/A'
  if (typeof value === 'number') {
    if (Number.isNaN(value)) return 'N/A'
    if (Number.isInteger(value)) return value.toLocaleString()
    // Small emission totals (e.g. NOx/PM2.5 grams for one vehicle) round to a
    // misleading "0.00" at 2 decimals -- show enough precision to stay honest.
    const abs = Math.abs(value)
    if (abs > 0 && abs < 0.01) return value.toExponential(2)
    if (abs < 1) return value.toFixed(4)
    return value.toFixed(2)
  }
  return value
}

export default function KpiCard({ label, value, unit, icon, sub, accent, animate }: KpiCardProps) {
  const numericTarget = typeof value === 'number' && !Number.isNaN(value) ? value : null
  const animatedValue = useCountUp(animate ? numericTarget : null)
  const display =
    animate && numericTarget !== null && animatedValue !== null
      ? formatValue(animatedValue)
      : formatValue(value)

  return (
    <Card
      variant="borderless"
      style={{
        background: '#111a2c',
        borderLeft: `3px solid ${accent ?? '#22d3ee'}`,
        height: '100%',
      }}
      styles={{ body: { padding: '16px 18px' } }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div className="metric-label">{label}</div>
          <div className="metric-value">
            {display}
            {display !== 'N/A' && unit ? (
              <span style={{ fontSize: 14, fontWeight: 400, color: '#8a99b8', marginLeft: 6 }}>
                {unit}
              </span>
            ) : null}
          </div>
          {sub ? <div className="metric-sub">{sub}</div> : null}
        </div>
        {icon ? (
          <div style={{ fontSize: 22, color: accent ?? '#22d3ee', opacity: 0.85 }}>{icon}</div>
        ) : null}
      </div>
    </Card>
  )
}
