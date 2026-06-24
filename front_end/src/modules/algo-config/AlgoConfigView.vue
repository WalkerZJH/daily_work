<script setup>
import { onMounted } from 'vue'

import LoadingErrorBlock from '../../components/LoadingErrorBlock.vue'
import SectionCard from '../../components/SectionCard.vue'
import ApiControlPanel from './components/ApiControlPanel.vue'
import ArchitectureDiagram from './components/ArchitectureDiagram.vue'
import ConfigPanel from './components/ConfigPanel.vue'
import DebugPanel from './components/DebugPanel.vue'
import RuntimeWarnings from './components/RuntimeWarnings.vue'
import { endpoints, useAlgoConfigApi } from './composables/useAlgoConfigApi'

const {
  apiBase,
  datasetName,
  asOfDate,
  unitKey,
  loading,
  backendStatus,
  backendStatusText,
  errorMessage,
  config,
  qualityReport,
  dryRunResult,
  unitDebugResult,
  configDryRunResult,
  lastPayload,
  configPatch,
  runQuality,
  runDryRun,
  runUnitDebug,
  runConfigDryRun,
  refreshAll
} = useAlgoConfigApi()

onMounted(() => {
  refreshAll()
})
</script>

<template>
  <div class="algo-config-view">
    <div class="page-header">
      <h1>算法接口诊断</h1>
      <div class="subtitle">
        后端健康检查 · dry-run · 单元调试 · FeatureSnapshot 验证 · 仅供开发联调使用
      </div>
    </div>

    <ApiControlPanel
      v-model:api-base="apiBase"
      v-model:dataset-name="datasetName"
      v-model:as-of-date="asOfDate"
      v-model:unit-key="unitKey"
      :loading="loading"
      :backend-status="backendStatus"
      :backend-status-text="backendStatusText"
      @refresh-all="refreshAll"
      @run-quality="runQuality"
      @run-dry-run="runDryRun"
      @run-unit-debug="runUnitDebug"
      @run-config-dry-run="runConfigDryRun"
    />

    <RuntimeWarnings />

    <LoadingErrorBlock :loading="loading" :error="errorMessage" />

    <ArchitectureDiagram />

    <div class="grid-2 content-grid">
      <DebugPanel
        :quality-report="qualityReport"
        :dry-run-result="dryRunResult"
        :unit-debug-result="unitDebugResult"
        :last-payload="lastPayload"
      />

      <aside class="side-stack">
        <ConfigPanel
          v-model:config-patch="configPatch"
          :config="config"
          :config-dry-run-result="configDryRunResult"
          @run-config-dry-run="runConfigDryRun"
        />

        <SectionCard title="已暴露接口" subtitle="用于页面观察和测试">
          <table class="table">
            <tbody>
              <tr v-for="endpoint in endpoints" :key="endpoint.path">
                <th>{{ endpoint.method }}</th>
                <td>
                  <code>{{ endpoint.path }}</code>
                  <div class="muted">{{ endpoint.desc }}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </SectionCard>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.algo-config-view {
  max-width: 1440px;
}

code {
  color: var(--blue-deep);
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}
</style>
