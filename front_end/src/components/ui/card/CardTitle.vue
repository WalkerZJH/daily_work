<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: String, default: '' }
})

const classes = computed(() => cn('text-base font-semibold text-slate-800', props.class))
</script>

<template>
  <h3 :class="classes">
    <slot />
  </h3>
</template>
