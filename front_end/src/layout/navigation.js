export const navSections = [
  {
    label: '工作台',
    items: [
      { key: 'index', href: 'index.html', icon: '⌁', text: 'VP 今日工作台', badge: '8' },
      { key: 'clues', href: 'clues.html', icon: '⌕', text: '全部风险线索', badge: '39', badgeClass: 'orange' },
      { key: 'watchlist', href: 'watchlist.html', icon: '◌', text: '观察清单（黄）', badge: '14', badgeStyle: 'background:#eab308' }
    ]
  },
  {
    label: '跟进与核验',
    items: [
      { key: 'verify', href: 'verify.html', icon: '✓', text: '挽回核验', badge: '4', badgeClass: 'orange' },
      { key: 'distributor', href: 'distributor.html', icon: '!', text: '配送商预警', badge: '1' }
    ]
  },
  {
    label: '分析',
    items: [
      { key: 'dashboard', href: 'dashboard.html', icon: '▣', text: '管理驾驶舱' },
      { key: 'backtest', href: 'backtest.html', icon: '↗', text: '回测报告' }
    ]
  },
  {
    label: '系统配置',
    items: [
      { key: 'algo-config', href: 'algo-config.html', icon: '⚙', text: '算法配置管理' },
      { key: 'algo-health', href: 'algo-health.html', icon: '●', text: '接口诊断' }
    ]
  }
]
