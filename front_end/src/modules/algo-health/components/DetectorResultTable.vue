<script setup>
defineProps({
  rows: { type: Array, default: () => [] },
  selectedKey: { type: String, default: '' }
})

defineEmits(['select'])

function rowKey(row, index) {
  return `${row.detector_id}-${row.reason_code}-${index}`
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(digits)
}
</script>

<template>
  <table class="table">
    <thead>
      <tr>
        <th>Detector</th>
        <th>类别</th>
        <th>状态</th>
        <th>命中</th>
        <th>严重度</th>
        <th>置信度</th>
        <th>原因码</th>
        <th>中文解释</th>
        <th>Warnings</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="(row, index) in rows"
        :key="rowKey(row, index)"
        :class="{ 'row-active': rowKey(row, index) === selectedKey }"
        @click="$emit('select', { row, key: rowKey(row, index) })"
      >
        <td>{{ row.name_zh }}</td>
        <td>{{ row.category }}</td>
        <td>{{ row.status }}</td>
        <td>
          <span :class="row.hit ? 'badge badge-red' : 'badge'">{{ row.hit ? '命中' : '未命中' }}</span>
        </td>
        <td>{{ formatNumber(row.severity, 1) }}</td>
        <td>{{ formatNumber(row.confidence, 2) }}</td>
        <td>{{ row.reason_code }}</td>
        <td class="narrative-cell">{{ row.narrative }}</td>
        <td>
          <span v-if="!row.warnings?.length" class="muted">无</span>
          <span v-else class="badge badge-orange">{{ row.warnings.length }}</span>
        </td>
      </tr>
    </tbody>
  </table>
  <div v-if="!rows.length" class="empty">暂无 detector 推理结果。</div>
</template>

<style scoped>
.row-active {
  background: #eef6ff;
}

tr {
  cursor: pointer;
}

.narrative-cell {
  max-width: 420px;
  white-space: normal;
  line-height: 1.45;
}
</style>

