import { useEffect, useState } from 'react'
import { Row, Col, Card, Spin, Alert, Table, Tag } from 'antd'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts'
import PageHeader from '../components/PageHeader'
import { CopertTag, XgboostTag } from '../components/SourceTag'
import { api } from '../services/api'
import type { ModelPerformance, Pollutant } from '../types/api'

const CHART_GRID = '#1f2b45'
const AXIS_COLOR = '#8a99b8'
const POLLUTANT_COLORS: Record<Pollutant, string> = {
  CO2: '#f87171',
  NOx: '#fb923c',
  CO: '#facc15',
  PM25: '#c084fc',
}

export default function AIPrediction() {
  const [perf, setPerf] = useState<ModelPerformance | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getModelPerformance().then(setPerf).catch((e) => setError(String(e)))
  }, [])

  if (error) return <Alert type="error" title="Failed to load model performance" description={error} showIcon />
  if (!perf) return <Spin size="large" style={{ marginTop: 80 }} />

  const r2Chart = (Object.keys(perf.pollutants) as Pollutant[]).map((p) => ({
    pollutant: p === 'PM25' ? 'PM2.5' : p,
    r2: perf.pollutants[p].test_r2,
    key: p,
  }))

  const tableData = (Object.keys(perf.pollutants) as Pollutant[]).map((p) => ({
    key: p,
    pollutant: p === 'PM25' ? 'PM2.5' : p,
    ...perf.pollutants[p],
  }))

  return (
    <div>
      <PageHeader
        title="AI Emission Prediction"
        subtitle="XGBoost models predicting window-level emission rate from traffic-state features"
      />

      <Alert
        type="warning"
        showIcon
        title="Offline evaluation, not live inference"
        description="This dashboard displays model performance measured on a held-out set of pre-recorded INDRA video windows. It does not perform real-time prediction on a live camera feed in this demo."
        style={{ marginBottom: 20 }}
      />

      <Card variant="borderless" style={{ background: '#111a2c', marginBottom: 20 }}>
        <p style={{ color: '#c3ccdc', fontSize: 14, margin: 0 }}>
          XGBoost models were trained using traffic and distance-related features from 104 INDRA
          traffic videos with video-level validation.
        </p>
        <div style={{ marginTop: 10, display: 'flex', gap: 16, flexWrap: 'wrap', color: '#8a99b8', fontSize: 13 }}>
          <span><strong style={{ color: '#e6edf7' }}>Model type:</strong> {perf.model_type}</span>
          <span><strong style={{ color: '#e6edf7' }}>Scale:</strong> {perf.training_scale}</span>
        </div>
        <div style={{ marginTop: 6, color: '#8a99b8', fontSize: 13 }}>
          <strong style={{ color: '#e6edf7' }}>Validation:</strong> {perf.validation_method}
        </div>
      </Card>

      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col>
          <CopertTag />
        </Col>
        <Col>
          <XgboostTag />
        </Col>
        <Col flex="auto">
          <span style={{ color: '#8a99b8', fontSize: 13 }}>
            COPERT computes emissions from measured per-vehicle distance x factor. XGBoost predicts
            an emission RATE (g/s) directly from aggregate traffic-state features, without needing
            per-vehicle distance tracking — intended for a future live dashboard.
          </span>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Held-Out Test R² by Pollutant" variant="borderless" style={{ background: '#111a2c' }}>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={r2Chart}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="pollutant" stroke={AXIS_COLOR} fontSize={13} />
                <YAxis stroke={AXIS_COLOR} fontSize={12} domain={[-0.1, 1]} />
                <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
                <Bar dataKey="r2" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {r2Chart.map((entry) => (
                    <Cell key={entry.key} fill={POLLUTANT_COLORS[entry.key]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="Detailed Metrics" variant="borderless" style={{ background: '#111a2c' }}>
            <Table
              size="small"
              pagination={false}
              dataSource={tableData}
              columns={[
                { title: 'Pollutant', dataIndex: 'pollutant' },
                { title: 'Test R²', dataIndex: 'test_r2', render: (v: number) => v.toFixed(3) },
                { title: 'Test MAE', dataIndex: 'test_mae', render: (v: number) => v.toExponential(3) },
                { title: 'Test RMSE', dataIndex: 'test_rmse', render: (v: number) => v.toExponential(3) },
                { title: 'CV R² (mean ± std)', key: 'cv', render: (_: unknown, r) => `${r.cv_r2_mean.toFixed(3)} ± ${r.cv_r2_std.toFixed(3)}` },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="Honest Model Caveats" variant="borderless" style={{ background: '#111a2c' }}>
            {Object.entries(perf.caveats).map(([pollutant, text]) => (
              <div key={pollutant} style={{ marginBottom: 10 }}>
                <Tag color="warning">{pollutant === 'PM25' ? 'PM2.5' : pollutant}</Tag>
                <span style={{ color: '#c3ccdc', fontSize: 13 }}>{text}</span>
              </div>
            ))}
            <div className="data-source-tag" style={{ marginTop: 6 }}>Source: {perf.source_file}</div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
