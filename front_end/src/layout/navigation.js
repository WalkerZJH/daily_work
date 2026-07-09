export const navSections = [
  {
    label: 'VP 工作台',
    items: [
      { key: 'index', href: 'index.html', icon: '▦', text: 'VP 工作台', badge: '20' },
      { key: 'clues', href: 'clues.html', icon: '◈', text: '今日巡检线索', badge: '9', badgeClass: 'orange' },
      { key: 'oneshot', href: 'oneshot.html', icon: '+', text: '新进终端监测', badge: '6', badgeClass: 'green' }
    ]
  },
  {
    label: '人工复核',
    items: [
      { key: 'verify', href: 'verify.html', icon: '✓', text: '挽回核验', badge: '4', badgeClass: 'orange' },
      { key: 'distributor', href: 'distributor.html', icon: '!', text: '配送商预警', badge: '1' }
    ]
  },
  {
    label: '案例',
    items: [
      { key: 'backtest', href: 'backtest.html', icon: '↗', text: '历史命中复盘' }
    ]
  },
  {
    label: '算法说明',
    items: [
      { key: 'algo-architecture', href: 'algo-architecture.html', icon: '▥', text: '算法链路说明' }
    ]
  }
]
