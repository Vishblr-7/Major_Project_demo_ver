import { useEffect, useState } from 'react'
import { Spin, Alert, Tag } from 'antd'
import { ArrowDownOutlined, CheckCircleFilled, ClockCircleOutlined } from '@ant-design/icons'
import PageHeader from '../components/PageHeader'
import { api } from '../services/api'
import type { Architecture, ArchitectureStage } from '../types/api'

function StageCard({
  stage,
  implemented,
}: {
  stage: ArchitectureStage
  implemented: boolean
}) {
  return (
    <div
      style={{
        width: '100%',
        maxWidth: 460,
        margin: '0 auto',
        padding: '12px 18px',
        borderRadius: 10,
        background: implemented ? '#111a2c' : '#0e1626',
        border: implemented ? '1px solid #1f6f7a' : '1px dashed #3a4664',
        opacity: implemented ? 1 : 0.75,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, color: implemented ? '#f2f6fc' : '#8a99b8' }}>{stage.stage}</span>
        {implemented ? (
          <CheckCircleFilled style={{ color: '#34d399' }} />
        ) : (
          <ClockCircleOutlined style={{ color: '#8a99b8' }} />
        )}
      </div>
      <div style={{ color: '#8a99b8', fontSize: 12, marginTop: 4 }}>{stage.detail}</div>
    </div>
  )
}

export default function ArchitecturePage() {
  const [arch, setArch] = useState<Architecture | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getArchitecture().then(setArch).catch((e) => setError(String(e)))
  }, [])

  if (error) return <Alert type="error" title="Failed to load architecture" description={error} showIcon />
  if (!arch) return <Spin size="large" style={{ marginTop: 80 }} />

  return (
    <div>
      <PageHeader
        title="System Architecture"
        subtitle="Modules 1 & 2 are implemented and verified. Module 3+ appear as Coming Next."
      />

      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <Tag color="success" style={{ fontSize: 13, padding: '4px 12px' }}>IMPLEMENTED &amp; VERIFIED</Tag>
      </div>

      {arch.implemented.map((stage, i) => (
        <div key={stage.stage}>
          <StageCard stage={stage} implemented />
          {i < arch.implemented.length - 1 && (
            <div style={{ textAlign: 'center', color: '#22d3ee', margin: '6px 0' }}>
              <ArrowDownOutlined />
            </div>
          )}
        </div>
      ))}

      <div
        style={{
          textAlign: 'center',
          margin: '32px 0 16px 0',
          padding: '10px 0',
          borderTop: '2px dashed #3a4664',
          borderBottom: '2px dashed #3a4664',
        }}
      >
        <Tag color="default" style={{ fontSize: 14, padding: '6px 16px', fontWeight: 700 }}>
          NEXT PHASE — NOT YET IMPLEMENTED
        </Tag>
      </div>

      {arch.next_phase.map((stage, i) => (
        <div key={stage.stage}>
          <StageCard stage={stage} implemented={false} />
          {i < arch.next_phase.length - 1 && (
            <div style={{ textAlign: 'center', color: '#3a4664', margin: '6px 0' }}>
              <ArrowDownOutlined />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
