<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' }
})
</script>

<template>
  <section class="panel">
    <div class="panel-title">
      <h2>{{ title }}</h2>
      <span v-if="subtitle" class="muted">{{ subtitle }}</span>
      <slot v-else name="title-extra" />
    </div>
    <slot />
  </section>
</template>
