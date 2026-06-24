<script setup>
import { onMounted } from 'vue'

import JsonBlock from '../../../components/JsonBlock.vue'
import LoadingErrorBlock from '../../../components/LoadingErrorBlock.vue'
import SectionCard from '../../../components/SectionCard.vue'
import DetectorResultTable from './DetectorResultTable.vue'
import DetectorSummaryCards from './DetectorSummaryCards.vue'

const props = defineProps({
  apiBase: { type: String, required: true },
  state: { type: Object, required: true }
})

defineEmits(['select-row'])

onMounted(() => {
  props.state.loadCatalog()
})
</script>

<template>
  <SectionCard
    title="Detector 推理链路检查"
    subtitle="当前结果仅用于算法链路验证，不是正式业务预警或工单。"
  >
    <div class="form-grid">
      <label>
        <span>source_type</span>
        <select v-model="state.form.source_type">
          <option value="sample">sample</option>
          <option value="database">database</option>
        </select>
      </label>
      <label>
        <span>dataset_name</span>
        <input v-model="state.form.dataset_name" :disabled="state.form.source_type === 'database'" />
      </label>
      <label>
        <span>as_of_date</span>
        <input v-model="state.form.as_of_date" type="date" />
      </label>
      <label>
        <span>days</span>
        <input v-model.number="state.form.days" type="number" min="1" max="60" />
      </label>
      <label>
        <span>row_limit</span>
        <input v-model.number="state.form.row_limit" type="number" min="1" max="5000" />
      </label>
      <label>
        <span>类别过滤</span>
        <select v-model="state.form.category">
          <option value="">全部</option>
          <option v-for="category in state.categories" :key="category" :value="category">
            {{ category }}
          </option>
        </select>
      </label>
      <label>
        <span>单独运行 detector</span>
        <select v-model="state.form.enabled_detector">
          <option value="">全部</option>
          <option v-for="item in state.visibleCatalog" :key="item.detector_id" :value="item.detector_id">
            {{ item.name_zh || item.name }} / {{ item.status }}
          </option>
        </select>
      </label>
      <label>
        <span>enterprise_code</span>
        <input v-model="state.form.enterprise_code" placeholder="可选" />
      </label>
      <label>
        <span>province_code</span>
        <input v-model="state.form.province_code" placeholder="可选" />
      </label>
    </div>

    <div class="button-row">
      <button class="btn btn-primary" :disabled="state.loading" @click="state.runDetectors(false)">
        运行所选 detector
      </button>
      <button class="btn" :disabled="state.loading" @click="state.runDetectors(true)">
        运行全部 detector
      </button>
      <button class="btn" :disabled="state.catalogLoading" @click="state.loadCatalog()">
        刷新 catalog
      </button>
    </div>

    <LoadingErrorBlock :loading="state.loading || state.catalogLoading" :error="state.errorMessage" />
  </SectionCard>

  <SectionCard title="Detector summary">
    <DetectorSummaryCards :summary="state.result?.summary" />
  </SectionCard>

  <SectionCard title="Detector 结果">
    <DetectorResultTable
      :rows="state.result?.detector_results || []"
      :selected-key="state.selectedRow?.key || ''"
      @select="$emit('select-row', $event)"
    />
  </SectionCard>

  <div class="grid-2">
    <SectionCard title="warning summary">
      <JsonBlock :value="state.result?.warning_summary || {}" />
    </SectionCard>
    <SectionCard title="metrics / evidence / warnings">
      <JsonBlock
        :value="state.selectedRow?.row ? {
          metrics: state.selectedRow.row.metrics,
          evidence_items: state.selectedRow.row.evidence_items,
          warnings: state.selectedRow.row.warnings,
          narrative: state.selectedRow.row.narrative
        } : {}"
      />
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

.button-row {
  display: flex;
  gap: 10px;
  margin-top: 14px;
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
