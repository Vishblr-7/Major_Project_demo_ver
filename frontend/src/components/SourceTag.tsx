import { Tag } from 'antd'

export function CopertTag() {
  return (
    <Tag color="cyan" style={{ fontWeight: 600 }}>
      COPERT-derived estimate
    </Tag>
  )
}

export function XgboostTag() {
  return (
    <Tag color="purple" style={{ fontWeight: 600 }}>
      XGBoost ML prediction
    </Tag>
  )
}
