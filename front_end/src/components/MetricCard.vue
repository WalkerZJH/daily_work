<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: '--' },
  tone: { type: String, default: 'neutral' }
})
</script>

<template>
  <div class="metric-card" :class="`metric-card-${tone}`">
    <span>{{ label }}</span>
    <strong>{{ value }}</strong>
  </div>
</template>
