<script setup>
import { computed } from 'vue'
import { getNavSections } from './navigation'

defineProps({
  active: { type: String, required: true }
})

const navSections = computed(() => getNavSections())

function withCurrentContext(href) {
  const params = new URLSearchParams(window.location.search)
  const query = params.toString()
  return query ? `${href}?${query}` : href
}

function navigateWithCurrentContext(event, href) {
  event.preventDefault()
  window.location.assign(withCurrentContext(href))
}
</script>

<template>
  <nav class="sidebar">
    <div v-for="section in navSections" :key="section.label" class="sidebar-section">
      <div class="sidebar-section-label">{{ section.label }}</div>
      <a
        v-for="item in section.items"
        :key="item.key"
        :href="withCurrentContext(item.href)"
        @click.prevent="navigateWithCurrentContext($event, item.href)"
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
