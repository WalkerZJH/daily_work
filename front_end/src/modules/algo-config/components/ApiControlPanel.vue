<script setup>
defineProps({
  apiBase: { type: String, required: true },
  datasetName: { type: String, required: true },
  asOfDate: { type: String, required: true },
  unitKey: { type: String, required: true },
  loading: { type: Boolean, default: false },
  backendStatus: { type: String, default: 'unknown' },
  backendStatusText: { type: String, default: '未检测' }
})

defineEmits([
  'update:apiBase',
  'update:datasetName',
  'update:asOfDate',
  'update:unitKey',
  'refreshAll',
  'runQuality',
  'runDryRun',
  'runUnitDebug',
  'runConfigDryRun'
])

const units = [
  { key: 'ORG_A|PL_A', label: 'ORG_A × PL_A：长期未采购' },
  { key: 'ORG_B|PL_B', label: 'ORG_B × PL_B：新进终端' },
  { key: 'ORG_C|PL_A', label: 'ORG_C × PL_A：品规收窄' },
  { key: 'ORG_B|PL_A', label: 'ORG_B × PL_A：正常对照' }
]
</script>

<template>
  <section class="panel">
    <div class="panel-title">
      <h2>后端联调控制</h2>
      <span class="status" :class="backendStatus">{{ backendStatusText }}</span>
    </div>

    <div class="form-grid">
      <div class="field">
        <label>API Base URL</label>
        <input :value="apiBase" @input="$emit('update:apiBase', $event.target.value)" />
      </div>
      <div class="field">
        <label>数据集</label>
        <select :value="datasetName" @change="$emit('update:datasetName', $event.target.value)">
          <option value="sample">sample</option>
        </select>
      </div>
      <div class="field">
        <label>as_of_date</label>
        <input type="date" :value="asOfDate" @input="$emit('update:asOfDate', $event.target.value)" />
      </div>
      <div class="field">
        <label>单元调试</label>
        <select :value="unitKey" @change="$emit('update:unitKey', $event.target.value)">
          <option v-for="unit in units" :key="unit.key" :value="unit.key">{{ unit.label }}</option>
        </select>
      </div>
    </div>

    <div class="actions">
      <button class="btn btn-primary" type="button" :disabled="loading" @click="$emit('refreshAll')">
        刷新全部
      </button>
      <button class="btn btn-outline" type="button" :disabled="loading" @click="$emit('runDryRun')">
        dry-run
      </button>
      <button class="btn btn-outline" type="button" :disabled="loading" @click="$emit('runUnitDebug')">
        单元调试
      </button>
      <button class="btn btn-gray" type="button" :disabled="loading" @click="$emit('runQuality')">
        数据质量
      </button>
      <button class="btn btn-gray" type="button" :disabled="loading" @click="$emit('runConfigDryRun')">
        配置影响 dry-run
      </button>
    </div>
  </section>
</template>

<style scoped>
.status {
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 900;
  background: #f4f4f5;
  color: var(--text-sub);
}

.status.ok {
  background: var(--green-bg);
  color: #15803d;
}

.status.error {
  background: var(--red-bg);
  color: #b91c1c;
}
</style>
