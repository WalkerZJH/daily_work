<script setup>
defineProps({
  rows: { type: Array, default: () => [] },
  selectedId: { type: String, default: '' }
})

defineEmits(['select'])

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(digits)
}
</script>

<template>
  <table class="table resizable-table">
    <thead>
      <tr>
        <th>机构</th>
        <th>产品线</th>
        <th>最后采购日</th>
        <th>未采购天数</th>
        <th>模型</th>
        <th>版本</th>
        <th>P_alive 候选</th>
        <th>主干风险分</th>
        <th>置信度</th>
        <th>警告</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="row in rows"
        :key="row.analysis_unit_id"
        :class="{ 'row-active': row.analysis_unit_id === selectedId }"
        @click="$emit('select', row)"
      >
        <td>{{ row.org_code }}</td>
        <td>{{ row.product_line_code }}</td>
        <td>{{ row.last_purchase_date || '--' }}</td>
        <td>{{ formatNumber(row.days_since_last_purchase, 0) }}</td>
        <td>{{ row.model_name }}</td>
        <td>{{ row.model_version }}</td>
        <td>{{ formatNumber(row.p_alive) }}</td>
        <td>{{ formatNumber(row.backbone_risk_score, 1) }}</td>
        <td>{{ formatNumber(row.confidence) }}</td>
        <td>
          <span v-if="!row.warnings?.length" class="muted">无</span>
          <span v-else class="badge badge-orange">{{ row.warnings.length }}</span>
        </td>
      </tr>
    </tbody>
  </table>
  <div v-if="!rows.length" class="empty">暂无 P_alive 候选结果。</div>
</template>

<style scoped>
.row-active {
  background: #eef6ff;
}

tr {
  cursor: pointer;
}
</style>
