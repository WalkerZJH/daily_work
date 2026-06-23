<script setup>
import { navSections } from './navigation'

defineProps({
  active: { type: String, required: true }
})
</script>

<template>
  <nav class="sidebar">
    <div v-for="section in navSections" :key="section.label" class="sidebar-section">
      <div class="sidebar-section-label">{{ section.label }}</div>
      <a
        v-for="item in section.items"
        :key="item.key"
        :href="item.href"
        class="sidebar-item"
        :class="{ active: item.key === active }"
      >
        <span class="icon">{{ item.icon }}</span>
        {{ item.text }}
        <span
          v-if="item.badge"
          class="sidebar-badge"
          :class="item.badgeClass"
          :style="item.badgeStyle"
        >
          {{ item.badge }}
        </span>
      </a>
    </div>
  </nav>
</template>
