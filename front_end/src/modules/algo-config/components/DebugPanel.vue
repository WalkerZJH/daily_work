<script setup>
import { computed } from 'vue'

const props = defineProps({
  qualityReport: { type: Object, default: null },
  dryRunResult: { type: Object, default: null },
  unitDebugResult: { type: Object, default: null },
  lastPayload: { type: Object, default: null }
})

const levelDistribution = computed(() => props.dryRunResult?.risk_level_distribution || {})
const detectorDistribution = computed(() => props.dryRunResult?.detector_hit_distribution || {})

function levelBadgeClass(level) {
  if (level === 'red') return 'badge-red'
  if (level === 'orange') return 'badge-orange'
  if (level === 'yellow') return 'badge-yellow'
  return 'badge'
}

function detectorLabel(name) {
  const labels = {
    inactive_terminal: '长期未采购',
    new_terminal: '新进终端',
    ip_interval: '采购间隔异常',
    frequency_drop: '采购频次下降',
    sku_shrink: '品规收窄'
  }
  return labels[name] || name
}
</script>

<template>
  <div class="grid-2">
    <section>
      <div class="grid-4 kpi-grid">
        <div class="kpi danger">
          <span>线索数</span>
          <strong>{{ dryRunResult?.clue_count ?? '--' }}</strong>
        </div>
        <div class="kpi warn">
          <span>红 / 橙 / 黄</span>
          <strong>{{ levelDistribution.red || 0 }}/{{ levelDistribution.orange || 0 }}/{{ levelDistribution.yellow || 0 }}</strong>
        </div>
        <div class="kpi blue">
          <span>处理单元</span>
          <strong>{{ dryRunResult?.unit_count ?? '--' }}</strong>
        </div>
        <div class="kpi ok">
          <span>数据质量错误</span>
          <strong>{{ qualityReport?.error_count ?? '--' }}</strong>
        </div>
      </div>

      <section class="panel">
        <div class="panel-title">
          <h2>全量 dry-run 线索</h2>
          <span class="muted">{{ dryRunResult ? `${dryRunResult.dataset_name} · ${dryRunResult.as_of_date}` : '等待运行' }}</span>
        </div>

        <div v-if="dryRunResult?.top_risk_clues?.length" class="clue-list">
          <article v-for="clue in dryRunResult.top_risk_clues" :key="clue.clue_id" class="clue">
            <div class="clue-head">
              <span class="badge" :class="levelBadgeClass(clue.risk_level)">{{ clue.risk_level }}</span>
              <strong>{{ clue.org_code }} × {{ clue.product_line_code }}</strong>
              <span class="badge badge-blue">score {{ clue.risk_score.toFixed(1) }}</span>
              <span class="badge">conf {{ clue.confidence.toFixed(2) }}</span>
            </div>
            <p>触发：{{ clue.triggered_detectors.map(detectorLabel).join('、') || '无' }}</p>
            <p>trace：{{ clue.debug_trace_id }}</p>
          </article>
        </div>
        <div v-else class="empty">尚未产生线索，或当前配置下没有红/橙/黄风险。</div>
      </section>

      <section class="panel">
        <div class="panel-title">
          <h2>单分析单元调试</h2>
          <span class="muted">baseline / demand shape / detector raw output</span>
        </div>

        <template v-if="unitDebugResult">
          <table class="table">
            <tbody>
              <tr><th>分析单元</th><td>{{ unitDebugResult.baseline_metrics.org_code }} × {{ unitDebugResult.baseline_metrics.product_line_code }}</td></tr>
              <tr><th>需求形态</th><td>{{ unitDebugResult.demand_shape.demand_shape }}，置信度 {{ unitDebugResult.demand_shape.confidence }}</td></tr>
              <tr><th>融合结果</th><td>{{ unitDebugResult.fusion.risk_level }} / {{ unitDebugResult.fusion.risk_score }}</td></tr>
              <tr><th>窗口</th><td>{{ unitDebugResult.baseline_metrics.baseline_start }} ~ {{ unitDebugResult.baseline_metrics.as_of_date }}</td></tr>
              <tr><th>订单数</th><td>recent {{ unitDebugResult.baseline_metrics.recent_orders }} / baseline {{ unitDebugResult.baseline_metrics.baseline_orders }}</td></tr>
              <tr><th>活跃品规</th><td>recent {{ unitDebugResult.baseline_metrics.recent_active_sku_count }} / baseline {{ unitDebugResult.baseline_metrics.baseline_active_sku_count }}</td></tr>
            </tbody>
          </table>

          <table class="table detector-table">
            <thead>
              <tr><th>Detector</th><th>命中</th><th>severity</th><th>confidence</th><th>reason</th></tr>
            </thead>
            <tbody>
              <tr v-for="detector in unitDebugResult.detector_results" :key="detector.detector_name">
                <td>{{ detectorLabel(detector.detector_name) }}</td>
                <td><span class="badge" :class="detector.hit ? 'badge-red' : ''">{{ detector.hit ? 'hit' : 'no' }}</span></td>
                <td>{{ detector.severity.toFixed(1) }}</td>
                <td>{{ detector.confidence.toFixed(2) }}</td>
                <td>{{ detector.reason_code }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <div v-else class="empty">尚未运行单元调试。</div>
      </section>
    </section>

    <aside>
      <section class="panel">
        <div class="panel-title">
          <h2>数据质量</h2>
          <span class="muted">DataQualityChecker</span>
        </div>
        <template v-if="qualityReport">
          <table class="table">
            <tbody>
              <tr><th>数据集</th><td>{{ qualityReport.dataset_name }}</td></tr>
              <tr><th>总行数</th><td>{{ qualityReport.total_rows }}</td></tr>
              <tr><th>错误 / 警告</th><td>{{ qualityReport.error_count }} / {{ qualityReport.warning_count }}</td></tr>
            </tbody>
          </table>
          <div v-if="qualityReport.issues.length" class="issue-list">
            <div v-for="issue in qualityReport.issues" :key="issue.check_name" class="issue">
              <strong>{{ issue.check_name }}</strong>
              <span>{{ issue.message }}</span>
            </div>
          </div>
          <div v-else class="empty compact">未发现质量问题。</div>
        </template>
        <div v-else class="empty">尚未检查。</div>
      </section>

      <section class="panel">
        <div class="panel-title">
          <h2>Detector 命中分布</h2>
          <span class="muted">dry-run summary</span>
        </div>
        <table v-if="dryRunResult" class="table">
          <tbody>
            <tr v-for="(count, name) in detectorDistribution" :key="name">
              <th>{{ detectorLabel(name) }}</th>
              <td>{{ count }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">等待 dry-run。</div>
      </section>

      <section class="panel">
        <div class="panel-title">
          <h2>最近一次 API 响应</h2>
          <span class="muted">raw JSON</span>
        </div>
        <pre class="code-box">{{ JSON.stringify(lastPayload || {}, null, 2) }}</pre>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.kpi-grid {
  margin-bottom: 16px;
}

.kpi {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #fff;
  padding: 14px 16px;
}

.kpi span {
  display: block;
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 5px;
}

.kpi strong {
  color: var(--navy);
  font-size: 26px;
  font-weight: 900;
}

.kpi.danger {
  border-left: 4px solid var(--red);
}

.kpi.warn {
  border-left: 4px solid var(--orange);
}

.kpi.blue {
  border-left: 4px solid var(--blue);
}

.kpi.ok {
  border-left: 4px solid var(--green);
}

.clue-list,
.issue-list {
  display: grid;
  gap: 10px;
}

.clue {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
}

.clue-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.clue-head strong {
  flex: 1;
  color: var(--navy);
}

.clue p {
  margin: 7px 0 0;
  color: var(--text-sub);
  font-size: 12px;
}

.detector-table {
  margin-top: 12px;
}

.issue {
  border: 1px solid #fde68a;
  border-radius: var(--radius-sm);
  background: #fffbeb;
  color: #92400e;
  padding: 9px 10px;
  font-size: 12px;
}

.issue strong,
.issue span {
  display: block;
}

.empty.compact {
  margin-top: 10px;
  padding: 12px;
}
</style>
