<script setup>
import { provideManufacturerScope } from './context/manufacturerScope'
import Sidebar from './layout/Sidebar.vue'
import Topbar from './layout/Topbar.vue'
import MonthlyWorkbenchView from './modules/monthly-workbench/MonthlyWorkbenchView.vue'
import RiskEntityListView from './modules/risk-worklist/RiskEntityListView.vue'
import RiskEntityDetailView from './modules/risk-worklist/RiskEntityDetailView.vue'
import MonthlyReportView from './modules/monthly-report/MonthlyReportView.vue'
import ProofCaseView from './modules/monthly-report/ProofCaseView.vue'
import OneshotMonitorView from './modules/oneshot-monitor/OneshotMonitorView.vue'
import AlgoArchitectureView from './modules/algo-architecture/AlgoArchitectureView.vue'
import InternalPlaceholderView from './modules/internal/InternalPlaceholderView.vue'

const pageName = window.location.pathname.split('/').pop() || 'index.html'
const params = new URLSearchParams(window.location.search)
provideManufacturerScope({
  backendBaseUrl: params.get('backendBaseUrl'),
  userId: params.get('user_id') || params.get('userId'),
  demoMode: params.get('demoMode'),
  manufacturerCode: params.get('manufacturer_code')
})

const detailTag = params.get('id') || params.get('riskEntityId')
  ? '候选对象详情'
  : params.get('clueId')
    ? '规则线索详情'
    : '详情'

const routeMap = {
  'index.html': {
    active: 'index',
    tag: '候选对象排序工作台',
    component: MonthlyWorkbenchView
  },
  'dashboard.html': {
    active: 'dashboard',
    tag: '月报与批次',
    component: MonthlyReportView
  },
  'clues.html': {
    active: 'clues',
    tag: '规则巡检结果',
    component: RiskEntityListView
  },
  'clue-detail.html': {
    active: 'clues',
    tag: detailTag,
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
  },
  'algo-architecture.html': {
    active: 'algo-architecture',
    tag: '内部 · 算法链路说明',
    component: AlgoArchitectureView
  },
  'algo-config.html': {
    active: 'algo-config',
    tag: '内部 · 规则配置状态',
    component: InternalPlaceholderView,
    props: {
      title: '规则配置状态',
      subtitle: '内部配置页 · 参数修改在下一次 detector 巡检后生效',
      description: '当前页面保留内部入口，不在客户主导航展示；正式模式不伪造规则配置或运行结果。'
    }
  },
  'verify.html': {
    active: 'verify',
    tag: '内部 · 挽回核验',
    component: InternalPlaceholderView,
    props: {
      title: '挽回核验',
      subtitle: '工单反馈与核验页面 · 当前为内部占位',
      description: '等待 Project API 提供正式核验数据；当前不使用 demoData 填充业务结果。'
    }
  },
  'distributor.html': {
    active: 'distributor',
    tag: '内部 · 配送预警',
    component: InternalPlaceholderView,
    props: {
      title: '配送预警',
      subtitle: '配送链路风险页面 · 当前为内部占位',
      description: '等待正式配送预警 API 接入；当前不展示静态业务样例。'
    }
  },
  'order-detail.html': {
    active: 'order-detail',
    tag: '内部 · 订单详情',
    component: InternalPlaceholderView,
    props: {
      title: '订单详情',
      subtitle: '订单事实核验页面 · 当前为内部占位',
      description: '等待正式订单详情 API 接入；当前不读取本地订单或 result-batch 文件。'
    }
  }
}

const route = routeMap[pageName] || routeMap['index.html']
</script>

<template>
  <Topbar :tag="route.tag" />

  <div class="layout">
    <Sidebar :active="route.active" />

    <main class="main">
      <component :is="route.component" v-bind="route.props || {}" />
    </main>
  </div>
</template>
