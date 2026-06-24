<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})
</script>

<template>
  <div v-if="loading || error" class="state-stack">
    <div v-if="loading" class="info-banner">正在请求后端接口...</div>
    <div v-if="error" class="error-banner">{{ error }}</div>
  </div>
</template>
