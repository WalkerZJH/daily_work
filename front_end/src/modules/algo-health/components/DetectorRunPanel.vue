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

async function onCategoryChange() {
  await props.state.loadDetectorsForCategory()
}

async function onScopeChange() {
  await props.state.loadProductLines()
}

async function onDetectorChange() {
  await props.state.loadSelectedConfig()
}
</script>

<template>
  <SectionCard
    title="日报式算法探查"
    subtitle="这里只生成算法候选结果和调试证据，不是正式工单、派单或业务闭环。"
  >
    <div class="form-grid">
      <label>
        <span>数据源</span>
        <select v-model="state.form.source_type">
          <option value="database">database</option>
          <option value="sample">sample</option>
        </select>
      </label>
      <label>
        <span>检测日期</span>
        <input v-model="state.form.as_of_date" type="date" />
      </label>
      <label>
        <span>回看窗口</span>
        <input v-model.number="state.form.lookback_days" type="number" min="1" max="365" />
      </label>
      <label>
        <span>基线窗口</span>
        <input v-model.number="state.form.baseline_days" type="number" min="1" max="730" />
      </label>
      <label>
        <span>row_limit</span>
        <input v-model.number="state.form.row_limit" type="number" min="1" max="5000" />
      </label>
      <label>
        <span>企业</span>
        <select v-model="state.form.enterprise_code" @change="onScopeChange">
          <option value="">全部企业</option>
          <option v-for="item in state.enterpriseOptions" :key="item.code || item.name" :value="item.code">
            {{ item.name }}
          </option>
        </select>
      </label>
      <label>
        <span>省份</span>
        <select v-model="state.form.province_code" @change="onScopeChange">
          <option value="">全部省份</option>
          <option v-for="item in state.provinceOptions" :key="item.code || item.name" :value="item.code">
            {{ item.name }}
          </option>
        </select>
      </label>
      <label>
        <span>产品线</span>
        <select v-model="state.form.product_line_code">
          <option value="">全部产品线</option>
          <option v-for="item in state.productLineOptions" :key="item.code || item.name" :value="item.code">
            {{ item.name }}
          </option>
        </select>
      </label>
    </div>

    <div class="category-tabs">
      <button
        v-for="item in state.categoryOptions"
        :key="item.category_id"
        class="tab-btn"
        :class="{ active: item.category_id === state.form.category }"
        @click="state.form.category = item.category_id; onCategoryChange()"
      >
        {{ item.category_name }}
        <span>{{ item.detector_count }}</span>
      </button>
    </div>

    <div class="detector-list">
      <button
        v-for="item in state.detectorOptions"
        :key="item.detector_id"
        class="detector-btn"
        :class="{ active: item.detector_id === state.form.enabled_detector }"
        @click="state.form.enabled_detector = item.detector_id; onDetectorChange()"
      >
        <strong>{{ item.name_zh }}</strong>
        <span>{{ item.mode }} / {{ item.enabled ? '启用' : '停用' }}</span>
      </button>
    </div>

    <div class="grid-2 config-block">
      <div>
        <h3>当前 detector 配置</h3>
        <JsonBlock :value="state.selectedConfig || {}" />
      </div>
      <div>
        <h3>运行口径</h3>
        <JsonBlock
          :value="{
            as_of_date: state.form.as_of_date,
            lookback_days: state.form.lookback_days,
            baseline_days: state.form.baseline_days,
            enterprise_code: state.form.enterprise_code || null,
            province_code: state.form.province_code || null,
            product_line_code: state.form.product_line_code || null
          }"
        />
      </div>
    </div>

    <div class="button-row">
      <button class="btn btn-primary" :disabled="state.loading" @click="state.runDetectors(false)">
        运行当前 detector
      </button>
      <button class="btn" :disabled="state.loading" @click="state.runDetectors(true, true)">
        运行当前 category
      </button>
      <button class="btn" :disabled="state.catalogLoading" @click="state.loadCatalog()">
        刷新选项
      </button>
    </div>

    <LoadingErrorBlock :loading="state.loading || state.catalogLoading" :error="state.errorMessage" />
  </SectionCard>

  <SectionCard title="日报 summary">
    <DetectorSummaryCards :summary="state.result?.summary" />
  </SectionCard>

  <SectionCard title="风险卡片候选 / detector 结果">
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
    <SectionCard title="evidence / statistics / debug">
      <JsonBlock
        :value="state.selectedRow?.row ? {
          statistics: state.selectedRow.row.statistics || state.selectedRow.row.metrics,
          evidence_items: state.selectedRow.row.evidence_items,
          sample_order_ids: state.selectedRow.row.sample_order_ids,
          related_entities: state.selectedRow.row.related_entities,
          warnings: state.selectedRow.row.warnings,
          narrative: state.selectedRow.row.narrative,
          run_scope: state.selectedRow.row.run_scope
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

.category-tabs,
.detector-list,
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.tab-btn,
.detector-btn {
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text);
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
}

.tab-btn.active,
.detector-btn.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.tab-btn span,
.detector-btn span {
  margin-left: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.config-block {
  margin-top: 14px;
}

h3 {
  font-size: 14px;
  margin: 0 0 8px;
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
