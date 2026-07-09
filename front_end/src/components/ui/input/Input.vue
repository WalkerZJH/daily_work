<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: String, default: '' }
})

const model = defineModel()
const classes = computed(() =>
  cn(
    'flex h-10 w-full rounded-lg border border-indigo-100 bg-white/90 px-3 py-2 text-sm text-slate-800 shadow-sm transition-colors placeholder:text-slate-400 focus-visible:border-indigo-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-100 disabled:cursor-not-allowed disabled:opacity-50',
    props.class
  )
)
</script>

<template>
  <input v-model="model" :class="classes" />
</template>
