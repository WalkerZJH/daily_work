<script setup>
import { computed } from 'vue'
import { useManufacturerScope } from '../context/manufacturerScope'

defineProps({
  tag: { type: String, required: true }
})

const manufacturerScope = useManufacturerScope()
const manufacturerOptions = manufacturerScope.manufacturerOptions
const selectedManufacturerCode = computed({
  get: () => manufacturerScope.manufacturerCode.value,
  set: (value) => manufacturerScope.selectManufacturer(value)
})

function hrefWithCurrentContext(href) {
  const query = new URLSearchParams(window.location.search).toString()
  return query ? `${href}?${query}` : href
}

function navigateWithCurrentContext(event, href) {
  event.preventDefault()
  window.location.assign(hrefWithCurrentContext(href))
}

function toggleSidebar() {
  const isCollapsed = document.body.classList.toggle('sidebar-collapsed')
  try {
    window.localStorage.setItem('sidebarCollapsed', isCollapsed ? '1' : '0')
  } catch (error) {
    // Ignore storage failures in strict browser modes.
  }
}

try {
  document.body.classList.toggle(
    'sidebar-collapsed',
    window.localStorage.getItem('sidebarCollapsed') === '1'
  )
} catch (error) {
  document.body.classList.remove('sidebar-collapsed')
}
</script>

<template>
  <header class="topbar">
    <button class="sidebar-toggle" title="收起 / 展开侧边栏" type="button" @click="toggleSidebar">
      ≡
    </button>
    <a class="topbar-logo" :href="hrefWithCurrentContext('index.html')" @click.prevent="navigateWithCurrentContext($event, 'index.html')">
      <div class="logo-icon">智</div>
      <div>
        <div class="logo-text">终端不丢智能体</div>
        <div class="logo-sub">供应链风险巡检 · 智能预警</div>
      </div>
    </a>
    <div class="topbar-spacer"></div>
    <label class="topbar-manufacturer">
      <span>生产企业</span>
      <select v-model="selectedManufacturerCode" aria-label="全局生产企业" :disabled="manufacturerScope.isLoading.value">
        <option v-if="manufacturerScope.isLoading.value && !manufacturerOptions.length" :value="selectedManufacturerCode" disabled>正在加载生产企业…</option>
        <option v-else-if="!manufacturerOptions.length" :value="selectedManufacturerCode" disabled>暂无可用生产企业</option>
        <option v-for="item in manufacturerOptions" :key="item.code" :value="item.code">{{ item.name }}</option>
      </select>
    </label>
    <span class="topbar-tag">{{ tag }}</span>
    <div class="topbar-user"><div class="avatar">陈</div>营销VP · 陈总</div>
  </header>
</template>
