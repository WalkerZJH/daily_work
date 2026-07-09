<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  orientation: { type: String, default: 'horizontal' },
  class: { type: String, default: '' }
})

const classes = computed(() =>
  cn(
    'shrink-0 bg-indigo-100',
    props.orientation === 'vertical' ? 'h-full w-px' : 'h-px w-full',
    props.class
  )
)
</script>

<template>
  <div role="separator" :aria-orientation="orientation" :class="classes" />
</template>
