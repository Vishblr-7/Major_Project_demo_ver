import { useEffect, useState } from 'react'
import { Row, Col, Card, Spin, Alert, Select, Table } from 'antd'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import KpiCard from '../components/KpiCard'
import { CopertTag } from '../components/SourceTag'
import { api, DEMO_VIDEO_ID } from '../services/api'
import type { EmissionsSummary, VideoEmissions, VideoListItem } from '../types/api'

const CHART_GRID = '#1f2b45'
const AXIS_COLOR = '#8a99b8'
const CLASS_COLORS: Record<string, string> = {
  car: '#22d3ee',
  motorcycle: '#34d399',
  bus: '#f87171',
  truck: '#fb923c',
}

const POLLUTANT_META: Record<string, { label: string; accent: string }> = {
  CO2: { label: 'Total CO2', accent: '#f87171' },
  NOx: { label: 'Total NOx', accent: '#fb923c' },
  CO: { label: 'Total CO', accent: '#facc15' },
  PM25: { label: 'Total PM2.5', accent: '#c084fc' },
}

export default function EmissionAnalytics() {
  const [summary, setSummary] = useState<EmissionsSummary | null>(null)
  const [videos, setVideos] = useState<VideoListItem[]>([])
  const [selected, setSelected] = useState(DEMO_VIDEO_ID)
  const [videoEmissions, setVideoEmissions] = useState<VideoEmissions | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getEmissionsSummary().then(setSummary).catch((e) => setError(String(e)))
    api.getVideos().then(setVideos).catch(() => undefined)
  }, [])

  useEffect(() => {
    api.getVideoEmissions(selected).then(setVideoEmissions).catch(() => setVideoEmissions(null))
  }, [selected])

  if (error) return <Alert type="error" title="Failed to load emission analytics" description={error} showIcon />
  if (!summary) return <Spin size="large" style={{ marginTop: 80 }} />

  const byTypeChart = summary.by_vehicle_type.map((row) => ({
    vehicle_type: row.vehicle_type as string,
    CO2: row.CO2_g_sum as number,
    NOx: row.NOx_g_sum as number,
    CO: row.CO_g_sum as number,
    PM25: row.PM25_g_sum as number,
  }))

  const shareData = byTypeChart.map((r) => ({ name: r.vehicle_type, value: r.CO2 }))

  return (
    <div>
      <PageHeader
        title="Emission Analytics"
        subtitle="CO2, NOx, CO and PM2.5 only — the four pollutants this project calculates"
      />
      <div style={{ marginBottom: 16 }}>
        <CopertTag />
      </div>

      <Row gutter={[16, 16]}>
        {(['CO2', 'NOx', 'CO', 'PM25'] as const).map((p) => (
          <Col xs={24} sm={12} lg={6} key={p}>
            <KpiCard
            animate
              label={POLLUTANT_META[p].label}
              value={summary.total_emissions_g[p]}
              unit="g"
              accent={POLLUTANT_META[p].accent}
              sub={`Avg/vehicle: ${summary.average_emission_per_vehicle_g[p]} g`}
            />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={14}>
          <Card title="Emissions by Vehicle Class" variant="borderless" style={{ background: '#111a2c' }}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={byTypeChart}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="vehicle_type" stroke={AXIS_COLOR} fontSize={12} />
                <YAxis stroke={AXIS_COLOR} fontSize={12} scale="log" domain={['auto', 'auto']} />
                <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
                <Legend />
                <Bar dataKey="CO2" fill="#f87171" name="CO2 (g)" isAnimationActive={false} />
                <Bar dataKey="NOx" fill="#fb923c" name="NOx (g)" isAnimationActive={false} />
                <Bar dataKey="CO" fill="#facc15" name="CO (g)" isAnimationActive={false} />
                <Bar dataKey="PM25" fill="#c084fc" name="PM2.5 (g)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
            <div className="data-source-tag">Log scale y-axis — pollutant magnitudes differ by orders of magnitude.</div>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="CO2 Share by Vehicle Class" variant="borderless" style={{ background: '#111a2c' }}>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={shareData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  isAnimationActive={false}
                  label={(props: { name?: string; percent?: number }) =>
                    `${props.name ?? ''} ${((props.percent ?? 0) * 100).toFixed(0)}%`
                  }
                >
                  {shareData.map((entry) => (
                    <Cell key={entry.name} fill={CLASS_COLORS[entry.name] ?? '#8a99b8'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card
            title="Excluded Vehicle Tracks"
            variant="borderless"
            style={{ background: '#111a2c' }}
          >
            <p style={{ color: '#8a99b8', fontSize: 13 }}>
              {summary.excluded_vehicle_tracks} vehicle tracks excluded from quantitative emissions
              (no approved COPERT factor mapping — e.g. autorickshaw). Bicycles are excluded from
              emission calculation entirely by definition and never appear in this dataset.
            </p>
            <Table
              size="small"
              pagination={false}
              dataSource={Object.entries(summary.excluded_by_type).map(([type, count]) => ({ type, count }))}
              rowKey="type"
              columns={[
                { title: 'Vehicle Type', dataIndex: 'type' },
                { title: 'Excluded Tracks', dataIndex: 'count' },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card
            title="Per-Video Emission Detail"
            variant="borderless"
            style={{ background: '#111a2c' }}
            extra={
              <Select
                size="small"
                style={{ width: 160 }}
                value={selected}
                onChange={setSelected}
                showSearch
                options={videos.map((v) => ({ value: v.video_id, label: v.video_id }))}
              />
            }
          >
            {videoEmissions?.note && (
              <Alert type="info" title={videoEmissions.note} showIcon style={{ marginBottom: 12 }} />
            )}
            {videoEmissions && !videoEmissions.note && (
              <Row gutter={16}>
                {(['CO2', 'NOx', 'CO', 'PM25'] as const).map((p) => (
                  <Col span={6} key={p}>
                    <KpiCard
            animate
                      label={`${p} total`}
                      value={videoEmissions.totals_g[p]}
                      unit="g"
                      accent={POLLUTANT_META[p].accent}
                    />
                  </Col>
                ))}
              </Row>
            )}
            <div className="data-source-tag" style={{ marginTop: 12 }}>
              Emission rate (g/s) is not a COPERT field — see AI Emission Prediction for the XGBoost
              rate model. COPERT reports total grams per completed vehicle track, not a rate.
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
