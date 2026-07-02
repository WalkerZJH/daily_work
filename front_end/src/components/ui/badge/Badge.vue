<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  variant: { type: String, default: 'default' },
  class: { type: String, default: '' }
})

const classes = computed(() =>
  cn(
    'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium',
    props.variant === 'default' && 'bg-indigo-600 text-white',
    props.variant === 'secondary' && 'bg-indigo-100 text-indigo-700',
    props.variant === 'outline' && 'border border-indigo-200 bg-white/70 text-slate-700',
    props.variant === 'success' && 'bg-emerald-100 text-emerald-700',
    props.variant === 'warning' && 'bg-amber-100 text-amber-700',
    props.variant === 'danger' && 'bg-rose-100 text-rose-700',
    props.class
  )
)
</script>

<template>
  <span :class="classes"><slot /></span>
</template>
