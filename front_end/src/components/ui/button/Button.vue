<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  type: { type: String, default: 'button' },
  variant: { type: String, default: 'default' },
  size: { type: String, default: 'default' },
  disabled: { type: Boolean, default: false },
  class: { type: String, default: '' }
})

const classes = computed(() =>
  cn(
    'inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300 disabled:pointer-events-none disabled:opacity-50',
    props.size === 'sm' ? 'h-8 px-3' : 'h-10 px-4 py-2',
    props.variant === 'default' && 'bg-indigo-600 text-white shadow-sm shadow-indigo-200 hover:bg-indigo-700 active:scale-[0.98]',
    props.variant === 'secondary' && 'bg-violet-100 text-violet-800 hover:bg-violet-200 active:scale-[0.98]',
    props.variant === 'outline' && 'border border-indigo-200 bg-white/80 text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 active:scale-[0.98]',
    props.variant === 'ghost' && 'text-slate-600 hover:bg-indigo-50 hover:text-indigo-700 active:scale-[0.98]',
    props.variant === 'success' && 'bg-emerald-600 text-white shadow-sm shadow-emerald-100 hover:bg-emerald-700 active:scale-[0.98]',
    props.variant === 'destructive' && 'bg-rose-600 text-white shadow-sm shadow-rose-100 hover:bg-rose-700 active:scale-[0.98]',
    props.class
  )
)
</script>

<template>
  <button :type="type" :disabled="disabled" :class="classes">
    <slot />
  </button>
</template>
