<script setup>
import Sidebar from './layout/Sidebar.vue'
import Topbar from './layout/Topbar.vue'
import MonthlyWorkbenchView from './modules/monthly-workbench/MonthlyWorkbenchView.vue'
import RiskEntityListView from './modules/risk-worklist/RiskEntityListView.vue'
import RiskEntityDetailView from './modules/risk-worklist/RiskEntityDetailView.vue'
import MonthlyReportView from './modules/monthly-report/MonthlyReportView.vue'
import ProofCaseView from './modules/monthly-report/ProofCaseView.vue'
import OneshotMonitorView from './modules/oneshot-monitor/OneshotMonitorView.vue'

const pageName = window.location.pathname.split('/').pop() || 'index.html'

const routeMap = {
  'index.html': {
    active: 'index',
    tag: '月报工作台 · H6 主视角',
    component: MonthlyWorkbenchView
  },
  'dashboard.html': {
    active: 'dashboard',
    tag: 'MonthlyReport · 批次总览',
    component: MonthlyReportView
  },
  'clues.html': {
    active: 'clues',
    tag: 'RiskEntity · 风险实体清单',
    component: RiskEntityListView
  },
  'clue-detail.html': {
    active: 'clues',
    tag: 'RiskCard · 风险卡详情',
    component: RiskEntityDetailView
  },
  'oneshot.html': {
    active: 'oneshot',
    tag: '新进终端监测 · oneshot 复购倾向',
    component: OneshotMonitorView
  },
  'backtest.html': {
    active: 'backtest',
    tag: 'Proof-case · 历史命中案例',
    component: ProofCaseView
  }
}

const route = routeMap[pageName] || routeMap['index.html']
</script>

<template>
  <Topbar :tag="route.tag" />

  <div class="layout">
    <Sidebar :active="route.active" />

    <main class="main">
      <component :is="route.component" />
    </main>
  </div>
</template>
