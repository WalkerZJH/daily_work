export const customerNavSections = [
  {
    label: '客户主线',
    items: [
      { key: 'index', href: 'index.html', icon: '▦', text: '风险工作台' },
      { key: 'clues', href: 'clues.html', icon: '◈', text: '规则巡检结果', badgeClass: 'orange' },
      { key: 'oneshot', href: 'oneshot.html', icon: '+', text: '新进终端监测', badgeClass: 'green' }
    ]
  }
]

export const internalNavSections = [
  {
    label: '内部页面',
    items: [
      { key: 'dashboard', href: 'dashboard.html', icon: '▤', text: '月报与批次', internal: true },
      { key: 'backtest', href: 'backtest.html', icon: '↗', text: '历史命中复盘', internal: true },
      { key: 'algo-architecture', href: 'algo-architecture.html', icon: '⌁', text: '算法链路说明', internal: true },
      { key: 'algo-config', href: 'algo-config.html', icon: '⚙', text: '规则配置状态', internal: true },
      { key: 'verify', href: 'verify.html', icon: '✓', text: '挽回核验', internal: true },
      { key: 'distributor', href: 'distributor.html', icon: '⇄', text: '配送预警', internal: true },
      { key: 'order-detail', href: 'order-detail.html', icon: '#', text: '订单详情', internal: true }
    ]
  }
]

export function isInternalMode(search = window.location.search) {
  const params = new URLSearchParams(search)
  return params.get('internalMode') === 'true' || params.get('internal_mode') === 'true'
}

export function getNavSections(search = window.location.search) {
  return isInternalMode(search) ? [...customerNavSections, ...internalNavSections] : customerNavSections
}

export const navSections = [
  ...customerNavSections,
  {
    label: '内部入口',
    items: internalNavSections.flatMap((section) => section.items)
  }
]
