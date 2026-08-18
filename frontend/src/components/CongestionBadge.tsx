import { Tag } from 'antd'

const COLORS: Record<string, string> = {
  LOW: 'green',
  MEDIUM: 'gold',
  HIGH: 'orange',
  CONGESTED: 'red',
  'N/A': 'default',
}

export default function CongestionBadge({ level }: { level: string | null | undefined }) {
  const key = level ?? 'N/A'
  return (
    <Tag color={COLORS[key] ?? 'default'} style={{ fontWeight: 600, fontSize: 12 }}>
      {key}
    </Tag>
  )
}
