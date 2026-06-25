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
    subtitle="单个检测日期下，每个 医院×产品线 分析单元只输出 1 条 P_alive 候选结果。"
  >
    <div class="form-grid">
      <label>
        <span>后端地址</span>
        <input :value="apiBase" @input="$emit('update:apiBase', $event.target.value)" />
      </label>
      <label>
        <span>数据源</span>
        <select v-model="form.source_type">
          <option value="database">database</option>
          <option value="csv">csv</option>
        </select>
      </label>
      <label>
        <span>检测日期</span>
        <input v-model="form.as_of_date" type="date" />
      </label>
      <label>
        <span>回看窗口</span>
        <input v-model.number="form.lookback_days" type="number" min="1" max="365" />
      </label>
      <label>
        <span>基线窗口</span>
        <input v-model.number="form.baseline_days" type="number" min="1" max="730" />
      </label>
      <label>
        <span>history_start_date</span>
        <input v-model="form.history_start_date" type="date" />
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
        <span>province_code</span>
        <input v-model="form.province_code" placeholder="可选" />
      </label>
      <label>
        <span>product_line_code</span>
        <input v-model="form.product_line_code" placeholder="可选" />
      </label>
      <label class="checkbox-line">
        <input v-model="form.include_debug_features" type="checkbox" />
        <span>返回完整 debug_features</span>
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

  <SectionCard title="主干 smoke summary">
    <SmokeTestSummaryCards :summary="result?.summary" />
    <div v-if="result?.summary" class="info-banner">
      预测口径：每个 医院×产品线 在检测日期 {{ result.summary.as_of_date }} 输出 1 条 P_alive。
      <strong v-if="result.summary.prediction_count === result.summary.analysis_unit_count">口径正常。</strong>
      <strong v-else class="warning-text">预测结果数与分析单元数不一致，请检查 warning。</strong>
    </div>
    <div v-if="freshness" class="info-banner freshness">
      当前窗口 row_count={{ freshness.row_count }}，max_order_time={{ freshness.max_order_time || '--' }}。{{ freshness.note }}
    </div>
  </SectionCard>

  <SectionCard title="P_alive 候选结果预览" subtitle="最多展示前 10 条；列表默认只返回关键 debug 字段。">
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

input,
select {
  min-height: 34px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  color: var(--text);
  background: #fff;
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

.warning-text {
  color: #b91c1c;
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
