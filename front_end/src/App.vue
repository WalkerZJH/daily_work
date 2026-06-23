<script setup>
import AlgoConfigView from './modules/algo-config/AlgoConfigView.vue'
import Sidebar from './layout/Sidebar.vue'
import Topbar from './layout/Topbar.vue'
</script>

<template>
  <Topbar tag="接口诊断 · 后端联调" />

  <div class="layout">
    <Sidebar active="algo-health" />

    <main class="main">
      <AlgoConfigView />
    </main>
  </div>
</template>
