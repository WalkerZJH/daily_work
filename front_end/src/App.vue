<script setup>
import AlgoConfigView from './modules/algo-config/AlgoConfigView.vue'
import AlgoHealthView from './modules/algo-health/AlgoHealthView.vue'
import Sidebar from './layout/Sidebar.vue'
import Topbar from './layout/Topbar.vue'

const pageName = window.location.pathname.split('/').pop() || 'index.html'
const isAlgoHealth = pageName === 'algo-health.html'
</script>

<template>
  <Topbar :tag="isAlgoHealth ? '主干算法 smoke test' : '接口诊断 · 后端联调'" />

  <div class="layout">
    <Sidebar active="algo-health" />

    <main class="main">
      <AlgoHealthView v-if="isAlgoHealth" />
      <AlgoConfigView v-else />
    </main>
  </div>
</template>
