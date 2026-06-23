(function () {
  const navSections = [
    {
      label: '工作台',
      items: [
        { key: 'index', href: 'index.html', icon: '⌂', text: 'VP 今日工作台', badge: '8' },
        { key: 'clues', href: 'clues.html', icon: '⌕', text: '全部风险线索', badge: '39', badgeClass: 'orange' },
        { key: 'watchlist', href: 'watchlist.html', icon: '◉', text: '观察清单（黄）', badge: '14', badgeStyle: 'background:#eab308' }
      ]
    },
    {
      label: '跟踪与核验',
      items: [
        { key: 'verify', href: 'verify.html', icon: '✓', text: '挽回核验', badge: '4', badgeClass: 'orange' },
        { key: 'distributor', href: 'distributor.html', icon: '!', text: '配送商预警', badge: '1' }
      ]
    },
    {
      label: '分析',
      items: [
        { key: 'dashboard', href: 'dashboard.html', icon: '▦', text: '管理驾驶舱' },
        { key: 'backtest', href: 'backtest.html', icon: '↻', text: '回测报告' }
      ]
    },
    {
      label: '系统配置',
      items: [
        { key: 'algo-config', href: 'algo-config.html', icon: '⚙', text: '算法配置管理' },
        { key: 'algo-health', href: 'algo-health.html', icon: '◎', text: '接口诊断' }
      ]
    }
  ]

  const pageDefaults = {
    'index.html': { active: 'index', tag: 'VP 今日工作台 · 本日待办' },
    'clues.html': { active: 'clues', tag: '全部风险线索' },
    'clue-detail.html': { active: 'clues', tag: '风险线索详情' },
    'order-detail.html': { active: 'clues', tag: '订单详情' },
    'watchlist.html': { active: 'watchlist', tag: '观察清单' },
    'verify.html': { active: 'verify', tag: '挽回核验' },
    'distributor.html': { active: 'distributor', tag: '配送商预警' },
    'dashboard.html': { active: 'dashboard', tag: '管理驾驶舱 · 本月统计' },
    'backtest.html': { active: 'backtest', tag: '回测报告' },
    'algo-config.html': { active: 'algo-config', tag: '算法配置管理 · 仅管理员可见' },
    'algo-health.html': { active: 'algo-health', tag: '接口诊断 · 后端联调' }
  }

  function currentPage() {
    return window.location.pathname.split('/').pop() || 'index.html'
  }

  function pageMeta() {
    return pageDefaults[currentPage()] || pageDefaults['index.html']
  }

  function renderTopbar() {
    const target = document.querySelector('[data-layout-topbar]')
    if (!target) return
    const tag = target.dataset.title || pageMeta().tag
    target.outerHTML = `
      <header class="topbar">
        <button class="sidebar-toggle" title="收起 / 展开侧边栏" type="button">☰</button>
        <a class="topbar-logo" href="index.html">
          <div class="logo-icon">终</div>
          <div>
            <div class="logo-text">终端不丢智能体</div>
            <div class="logo-sub">供应链风险巡检 · 智能预警</div>
          </div>
        </a>
        <div class="topbar-spacer"></div>
        <span class="topbar-tag">${tag}</span>
        <div class="topbar-user"><div class="avatar">陈</div>营销VP · 陈总</div>
      </header>`
  }

  function renderSidebar() {
    const target = document.querySelector('[data-layout-sidebar]')
    if (!target) return
    const active = target.dataset.active || pageMeta().active
    target.outerHTML = `
      <nav class="sidebar">
        ${navSections.map(section => `
          <div class="sidebar-section">
            <div class="sidebar-section-label">${section.label}</div>
            ${section.items.map(item => navItem(item, active)).join('')}
          </div>
        `).join('')}
      </nav>`
  }

  function navItem(item, active) {
    const badge = item.badge
      ? `<span class="sidebar-badge ${item.badgeClass || ''}" ${item.badgeStyle ? `style="${item.badgeStyle}"` : ''}>${item.badge}</span>`
      : ''
    return `
      <a href="${item.href}" class="sidebar-item ${item.key === active ? 'active' : ''}">
        <span class="icon">${item.icon}</span> ${item.text}${badge}
      </a>`
  }

  renderTopbar()
  renderSidebar()
  bindSidebarToggle()

  function bindSidebarToggle() {
    let collapsed = false
    try {
      collapsed = window.localStorage.getItem('sidebarCollapsed') === '1'
    } catch (error) {
      collapsed = false
    }
    document.body.classList.toggle('sidebar-collapsed', collapsed)

    const button = document.querySelector('.sidebar-toggle')
    if (!button) return
    button.addEventListener('click', () => {
      const isCollapsed = document.body.classList.toggle('sidebar-collapsed')
      try {
        window.localStorage.setItem('sidebarCollapsed', isCollapsed ? '1' : '0')
      } catch (error) {
        // Ignore storage failures in file:// or strict browser modes.
      }
    })
  }
})()
