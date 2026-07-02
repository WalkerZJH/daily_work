<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  interactive: { type: Boolean, default: false },
  padded: { type: Boolean, default: true },
  class: { type: String, default: '' }
})

const classes = computed(() =>
  cn('section-card', props.interactive && 'interactive-card', props.padded && 'p-4', props.class)
)
</script>

<template>
  <section :class="classes">
    <slot />
  </section>
</template>
