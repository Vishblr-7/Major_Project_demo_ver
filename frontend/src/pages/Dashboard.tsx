import { useEffect, useState } from 'react'
import { Row, Col, Card, Spin, Alert, Tag } from 'antd'
import {
  CarOutlined,
  DashboardOutlined,
  ThunderboltOutlined,
  AlertOutlined,
  CloudOutlined,
} from '@ant-design/icons'
import PageHeader from '../components/PageHeader'
import KpiCard, { formatValue } from '../components/KpiCard'
import CongestionBadge from '../components/CongestionBadge'
import { CopertTag } from '../components/SourceTag'
import { api } from '../services/api'
import type { Summary } from '../types/api'

const POLLUTANT_LABELS: Record<string, { label: string; unit: string; accent: string }> = {
  CO2: { label: 'CO2 Emissions', unit: 'g', accent: '#f87171' },
  NOx: { label: 'NOx Emissions', unit: 'g', accent: '#fb923c' },
  CO: { label: 'CO Emissions', unit: 'g', accent: '#facc15' },
  PM25: { label: 'PM2.5 Emissions', unit: 'g', accent: '#c084fc' },
}

const CLASS_COLORS: Record<string, string> = {
  car: 'blue',
  motorcycle: 'geekblue',
  bus: 'volcano',
  truck: 'orange',
  autorickshaw: 'gold',
  bicycle: 'default',
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getSummary().then(setSummary).catch((e) => setError(String(e)))
  }, [])

  if (error) return <Alert type="error" title="Failed to load dashboard data" description={error} showIcon />
  if (!summary) return <Spin size="large" style={{ marginTop: 80 }} />

  return (
    <div>
      <PageHeader
        title="Fleet-Wide Traffic & Emission Overview"
        subtitle={`${summary.videos_processed} INDRA videos processed · Module 1 (YOLO11s + ByteTrack) + Module 2 (COPERT + XGBoost)`}
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <KpiCard
            animate
            label="Total Vehicles Tracked"
            value={summary.total_vehicles_tracked}
            icon={<CarOutlined />}
            sub="Emission-eligible tracks, all videos"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <KpiCard
            animate
            label="Traffic Density"
            value={summary.average_traffic_density_veh_per_100m2}
            unit="veh/100m²"
            icon={<DashboardOutlined />}
            accent="#facc15"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <KpiCard
            animate
            label="Average Speed"
            value={summary.average_speed_kmph}
            unit="km/h"
            icon={<ThunderboltOutlined />}
            accent="#34d399"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card variant="borderless" style={{ background: '#111a2c', borderLeft: '3px solid #f87171', height: '100%' }} styles={{ body: { padding: '16px 18px' } }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div className="metric-label">Congestion Level</div>
                <div style={{ marginTop: 8 }}>
                  <CongestionBadge level={summary.congestion_level} />
                </div>
                <div className="metric-sub">Reused from project's traffic_condition() thresholds</div>
              </div>
              <AlertOutlined style={{ fontSize: 22, color: '#f87171', opacity: 0.85 }} />
            </div>
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 24, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
        <h2 className="section-title" style={{ margin: 0 }}>Emissions (COPERT-derived)</h2>
        <CopertTag />
      </div>
      <Row gutter={[16, 16]}>
        {(['CO2', 'NOx', 'CO', 'PM25'] as const).map((p) => (
          <Col xs={24} sm={12} lg={6} key={p}>
            <KpiCard
            animate
              label={POLLUTANT_LABELS[p].label}
              value={summary.total_emissions_g[p]}
              unit={POLLUTANT_LABELS[p].unit}
              icon={<CloudOutlined />}
              accent={POLLUTANT_LABELS[p].accent}
              sub="Total across all included vehicle tracks"
            />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={14}>
          <Card title="Vehicle Class Composition" variant="borderless" style={{ background: '#111a2c' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {Object.entries(summary.vehicle_class_counts).map(([cls, count]) => (
                <Tag
                  key={cls}
                  color={CLASS_COLORS[cls] ?? 'default'}
                  style={{ fontSize: 13, padding: '6px 12px' }}
                >
                  {cls === 'bicycle' ? 'Bicycles (excluded from emissions)' : cls} — {formatValue(count)}
                </Tag>
              ))}
            </div>
            <div className="data-source-tag" style={{ marginTop: 14 }}>{summary.tracked_scope_note}</div>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Data Provenance" variant="borderless" style={{ background: '#111a2c' }}>
            <p style={{ color: '#c3ccdc', fontSize: 13 }}>
              Module 1: <code>outputs/module1_distance_enriched_104/INDRA_COPERT_DATASET_WITH_DISTANCE.csv</code>
            </p>
            <p style={{ color: '#c3ccdc', fontSize: 13 }}>
              Module 2: <code>outputs/copert_emissions_104/vehicle_emissions.csv</code>
            </p>
            <p style={{ color: '#8a99b8', fontSize: 12, marginTop: 10 }}>{summary.bicycle_note}</p>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
