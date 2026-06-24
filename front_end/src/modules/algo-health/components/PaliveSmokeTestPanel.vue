<script setup>
import JsonBlock from '../../../components/JsonBlock.vue'
import LoadingErrorBlock from '../../../components/LoadingErrorBlock.vue'
import SectionCard from '../../../components/SectionCard.vue'
import PalivePreviewTable from './PalivePreviewTable.vue'
import SmokeTestSummaryCards from './SmokeTestSummaryCards.vue'

defineProps({
  apiBase: { type: String, required: true },
  form: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  result: { type: Object, default: null },
  freshness: { type: Object, default: null },
  selectedRow: { type: Object, default: null }
})

defineEmits([
  'update:apiBase',
  'run-smoke-test',
  'check-freshness',
  'select-row'
])
</script>

<template>
  <SectionCard
    title="主干算法 smoke test"
    subtitle="当前结果仅用于算法链路验证，未经过真实回测和概率校准，暂不能作为正式业务预警。"
  >
    <div class="form-grid">
      <label>
        <span>后端地址</span>
        <input :value="apiBase" @input="$emit('update:apiBase', $event.target.value)" />
      </label>
      <label>
        <span>source_type</span>
        <input value="database" disabled />
      </label>
      <label>
        <span>as_of_date</span>
        <input v-model="form.as_of_date" type="date" />
      </label>
      <label>
        <span>days</span>
        <input v-model.number="form.days" type="number" min="1" max="60" />
      </label>
      <label>
        <span>row_limit</span>
        <input v-model.number="form.row_limit" type="number" min="1" max="5000" />
      </label>
      <label>
        <span>enterprise_code</span>
        <input v-model="form.enterprise_code" placeholder="可选" />
      </label>
      <label>
        <span>province</span>
        <input v-model="form.province" placeholder="可选" />
      </label>
      <label>
        <span>province_code</span>
        <input v-model="form.province_code" placeholder="可选" />
      </label>
      <label class="checkbox-line">
        <input v-model="form.include_debug_features" type="checkbox" />
        <span>返回 debug_features</span>
      </label>
    </div>

    <div class="button-row">
      <button class="btn btn-primary" :disabled="loading" @click="$emit('run-smoke-test')">
        运行 smoke test
      </button>
      <button class="btn" :disabled="loading" @click="$emit('check-freshness')">
        检查数据新鲜度
      </button>
    </div>

    <LoadingErrorBlock :loading="loading" :error="errorMessage" />
  </SectionCard>

  <SectionCard title="运行结果">
    <SmokeTestSummaryCards :summary="result?.summary" />
    <div v-if="freshness" class="info-banner freshness">
      当前窗口 row_count={{ freshness.row_count }}，
      max_order_time={{ freshness.max_order_time || '--' }}。
      {{ freshness.note }}
    </div>
  </SectionCard>

  <SectionCard title="P_alive 候选结果预览" subtitle="最多展示前 10 条，字段为实验候选输出。">
    <PalivePreviewTable
      :rows="result?.palive_preview || []"
      :selected-id="selectedRow?.analysis_unit_id || ''"
      @select="$emit('select-row', $event)"
    />
  </SectionCard>

  <div class="grid-2">
    <SectionCard title="warning summary">
      <JsonBlock :value="result?.warning_summary || freshness?.warning_summary || {}" />
    </SectionCard>
    <SectionCard title="debug_features">
      <JsonBlock :value="selectedRow?.debug_features || {}" />
    </SectionCard>
  </div>
</template>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

input {
  min-height: 34px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  color: var(--text);
}

.checkbox-line {
  flex-direction: row;
  align-items: center;
  margin-top: 22px;
}

.checkbox-line input {
  min-height: auto;
}

.button-row {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.freshness {
  margin-top: 12px;
}

@media (max-width: 980px) {
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
