(function () {
  const navSections = [
    {
      label: '月报工作台',
      items: [
        { key: 'index', href: 'index.html', icon: '▦', text: '月报工作台', badge: '20' },
        { key: 'clues', href: 'clues.html', icon: '●', text: '风险实体清单', badge: '9', badgeClass: 'orange' },
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
      label: '月报与案例',
      items: [
        { key: 'dashboard', href: 'dashboard.html', icon: '▣', text: '月报与批次' },
        { key: 'backtest', href: 'backtest.html', icon: '↗', text: 'Proof-case 案例' }
      ]
    },
    {
      label: '算法说明',
      items: [
        { key: 'algo-architecture', href: 'algo-architecture.html', icon: '▥', text: '算法链路说明' }
      ]
    }
  ]

  const pageDefaults = {
    'index.html': { active: 'index', tag: '月报工作台 · H6 主视角' },
    'clues.html': { active: 'clues', tag: '风险实体清单' },
    'clue-detail.html': { active: 'clues', tag: 'RiskCard 详情' },
    'order-detail.html': { active: 'clues', tag: '订单详情' },
    'oneshot.html': { active: 'oneshot', tag: '新进终端监测 · oneshot 复购倾向' },
    'verify.html': { active: 'verify', tag: '挽回核验' },
    'distributor.html': { active: 'distributor', tag: '配送商预警' },
    'dashboard.html': { active: 'dashboard', tag: 'MonthlyReport · 批次总览' },
    'backtest.html': { active: 'backtest', tag: 'Proof-case · 历史命中案例' },
    'algo-architecture.html': { active: 'algo-architecture', tag: '算法链路说明' }
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
        <button class="sidebar-toggle" title="收起 / 展开侧边栏" type="button">≡</button>
        <a class="topbar-logo" href="index.html">
          <div class="logo-icon">智</div>
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
