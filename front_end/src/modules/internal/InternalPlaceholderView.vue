<script setup>
import SectionCard from '../../components/SectionCard.vue'

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, required: true },
  description: { type: String, required: true }
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <h1>{{ title }}</h1>
      <div class="subtitle">{{ subtitle }}</div>
    </div>

    <SectionCard title="内部页面占位" subtitle="Vite 页面已恢复，正式业务数据等待 Project API 接入">
      <div class="empty">
        <strong>接口未就绪</strong>
        <p>{{ description }}</p>
      </div>
    </SectionCard>
  </div>
</template>
