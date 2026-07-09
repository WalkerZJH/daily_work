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
    tag: 'VP 工作台 · 今日巡检线索',
    component: MonthlyWorkbenchView
  },
  'dashboard.html': {
    active: 'dashboard',
    tag: '月报与批次',
    component: MonthlyReportView
  },
  'clues.html': {
    active: 'clues',
    tag: '今日巡检线索',
    component: RiskEntityListView
  },
  'clue-detail.html': {
    active: 'clues',
    tag: '规则线索详情',
    component: RiskEntityDetailView
  },
  'oneshot.html': {
    active: 'oneshot',
    tag: '新进终端监测 · 首采记录',
    component: OneshotMonitorView
  },
  'backtest.html': {
    active: 'backtest',
    tag: '月报命中复盘',
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
