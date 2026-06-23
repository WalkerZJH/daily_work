<script setup>
import { computed } from 'vue'

const props = defineProps({
  config: { type: Object, default: null },
  configDryRunResult: { type: Object, default: null },
  configPatch: { type: String, required: true }
})

defineEmits(['update:configPatch', 'runConfigDryRun'])

const configRows = computed(() => {
  if (!props.config) return []
  return [
    ['配置版本', props.config.config_version],
    ['近期窗口', `${props.config.windows.recent_days} 天`],
    ['基线窗口', `${props.config.windows.baseline_days} 天`],
    ['需求形态阈值', `ADI ${props.config.demand_shape.adi_threshold} / CV2 ${props.config.demand_shape.cv2_threshold}`],
    ['红/橙/黄阈值', `${props.config.fusion.red_score} / ${props.config.fusion.orange_score} / ${props.config.fusion.yellow_score}`],
    ['最小告警置信度', props.config.fusion.min_confidence_for_alert]
  ]
})
</script>

<template>
  <section class="panel">
    <div class="panel-title">
      <h2>配置读取与影响评估</h2>
      <span class="muted">生产配置只读，页面只做 dry-run patch</span>
    </div>

    <table v-if="configRows.length" class="table">
      <tbody>
        <tr v-for="[key, value] in configRows" :key="key">
          <th>{{ key }}</th>
          <td>{{ value }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">尚未读取后端配置。</div>

    <div class="patch-block">
      <div class="field">
        <label>临时配置 patch JSON</label>
        <textarea
          rows="8"
          :value="configPatch"
          @input="$emit('update:configPatch', $event.target.value)"
        ></textarea>
      </div>
      <button class="btn btn-outline" type="button" @click="$emit('runConfigDryRun')">
        运行配置影响 dry-run
      </button>
    </div>

    <div v-if="configDryRunResult" class="delta">
      <h3>影响结果</h3>
      <table class="table">
        <tbody>
          <tr>
            <th>线索数量变化</th>
            <td>{{ configDryRunResult.delta.clue_count }}</td>
          </tr>
          <tr>
            <th>等级分布变化</th>
            <td>{{ configDryRunResult.delta.risk_level_distribution }}</td>
          </tr>
          <tr>
            <th>Detector 命中变化</th>
            <td>{{ configDryRunResult.delta.detector_hit_distribution }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.patch-block {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.delta {
  margin-top: 14px;
}

.delta h3 {
  margin: 0 0 8px;
  color: var(--navy);
  font-size: 14px;
}
</style>
