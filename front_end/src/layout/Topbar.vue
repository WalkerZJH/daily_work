<script setup>
defineProps({
  tag: { type: String, required: true }
})

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
      ◀
    </button>
    <a class="topbar-logo" href="index.html">
      <div class="logo-icon">智</div>
      <div>
        <div class="logo-text">终端不丢智能体</div>
        <div class="logo-sub">供应链风险巡检 · 智能预警</div>
      </div>
    </a>
    <div class="topbar-spacer"></div>
    <span class="topbar-tag">{{ tag }}</span>
    <div class="topbar-user"><div class="avatar">陈</div>营销VP · 陈总</div>
  </header>
</template>
