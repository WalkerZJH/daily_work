<script setup>
import DetectorRunPanel from './components/DetectorRunPanel.vue'
import PaliveSmokeTestPanel from './components/PaliveSmokeTestPanel.vue'
import { useDatabaseSmokeTest } from './composables/useDatabaseSmokeTest'
import { useDetectorRun } from './composables/useDetectorRun'

const {
  apiBase,
  form,
  loading,
  errorMessage,
  result,
  freshness,
  selectedRow,
  runSmokeTest,
  checkFreshness
} = useDatabaseSmokeTest()

const detectorState = useDetectorRun(apiBase)
</script>

<template>
  <div class="algo-health-view">
    <div class="page-header">
      <h1>算法日报探查页</h1>
      <div class="subtitle">
        当前页面用于真实数据小窗口算法验证，展示 detector 证据、P_alive 候选和调试信息；结果未经过回测和概率校准，不能作为正式业务预警或工单。
      </div>
    </div>

    <DetectorRunPanel
      :api-base="apiBase"
      :state="detectorState"
      @select-row="detectorState.selectedRow = $event"
    />

    <PaliveSmokeTestPanel
      v-model:api-base="apiBase"
      :form="form"
      :loading="loading"
      :error-message="errorMessage"
      :result="result"
      :freshness="freshness"
      :selected-row="selectedRow"
      @run-smoke-test="runSmokeTest"
      @check-freshness="checkFreshness"
      @select-row="selectedRow = $event"
    />
  </div>
</template>

<style scoped>
.algo-health-view {
  max-width: 1440px;
}
</style>
