<script setup>
const props = defineProps({
  modelValue: { type: String, default: '' },
  availableDates: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

function todayIso() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

function handleInput(event) {
  const value = event.target.value
  const allowed = new Set(props.availableDates || [])
  if (value > todayIso()) return
  if (allowed.size && !allowed.has(value)) return
  emit('update:modelValue', value)
}
</script>

<template>
  <label class="square-date-picker">
    <span v-if="label">{{ label }}</span>
    <input
      type="date"
      :value="modelValue"
      :max="todayIso()"
      :disabled="disabled"
      @input="handleInput"
    />
  </label>
</template>
