<script setup>
const groups = [
  {
    id: 'S1',
    title: '数据接入与规范化',
    tone: 'l0',
    nodes: ['数据源', 'Adapter', 'Canonical Schema', '标准视图 / 聚合视图']
  },
  {
    id: 'S2',
    title: '特征工程',
    tone: 'l05',
    nodes: ['Preprocessor Registry', 'Feature Store', 'Feature Snapshot']
  },
  {
    id: 'S3',
    title: '算法检测',
    tone: 'l1',
    nodes: ['Detector Registry', 'Detector Result']
  },
  {
    id: 'S4',
    title: '线索生成',
    tone: 'l3',
    nodes: ['Fusion', 'Evidence Builder', 'RiskClue']
  },
  {
    id: 'S5',
    title: '服务接口',
    tone: 'l5',
    nodes: ['Inspection Service', 'Debug API', 'Dry-run API', 'Backtest API']
  }
]
</script>

<template>
  <div class="pipeline-wrap">
    <div class="pipeline-title">新版并行巡检架构总览</div>
    <div class="pipeline-flow architecture-pipeline">
      <template v-for="(group, index) in groups" :key="group.id">
        <div class="pipeline-node architecture-group">
          <div class="pipeline-node-box" :class="group.tone">
            <div class="pipeline-node-label">{{ group.id }}</div>
            <div class="pipeline-node-name">{{ group.title }}</div>
          </div>
          <div class="architecture-subnodes">
            <span v-for="node in group.nodes" :key="node">{{ node }}</span>
          </div>
        </div>
        <div v-if="index < groups.length - 1" class="pipeline-arrow">→</div>
      </template>
    </div>
    <div class="architecture-note">
      Detector 只读取 FeatureSnapshot；新增预处理或 detector 时注册即可复用，不再把药物分组、治疗周期、替代关系写死在单个算法中。
    </div>
  </div>
</template>

<style scoped>
.pipeline-wrap {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border);
  padding: 24px 20px 18px;
  margin-bottom: 22px;
  overflow-x: auto;
}

.pipeline-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--navy);
  margin-bottom: 18px;
}

.pipeline-flow {
  display: flex;
  align-items: flex-start;
  gap: 0;
}

.pipeline-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.pipeline-node-box {
  width: 100%;
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-mid) 100%);
  border-radius: 8px;
  padding: 8px 10px;
  text-align: center;
  color: #fff;
}

.pipeline-node-box.l0 {
  background: linear-gradient(135deg, #0f3460, #1a4a7a);
}

.pipeline-node-box.l05 {
  background: linear-gradient(135deg, #1d4ed8, #2563eb);
}

.pipeline-node-box.l1 {
  background: linear-gradient(135deg, #0b2a4a, #103d6b);
}

.pipeline-node-box.l3 {
  background: linear-gradient(135deg, #15803d, #16a34a);
}

.pipeline-node-box.l5 {
  background: linear-gradient(135deg, #0f766e, #0d9488);
}

.pipeline-node-label {
  font-size: 11px;
  font-weight: 800;
  color: rgba(255,255,255,.9);
  letter-spacing: .3px;
  margin-bottom: 3px;
}

.pipeline-node-name {
  font-size: 11px;
  color: rgba(255,255,255,.86);
  line-height: 1.3;
  font-weight: 700;
}

.pipeline-arrow {
  display: flex;
  align-items: center;
  padding-top: 14px;
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: 18px;
  margin: 0 8px;
}

.architecture-pipeline {
  min-width: 980px;
  align-items: stretch;
}

.architecture-group {
  min-width: 160px;
}

.architecture-group .pipeline-node-box {
  max-width: 160px;
}

.architecture-subnodes {
  width: 100%;
  max-width: 170px;
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.architecture-subnodes span {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--text-main);
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 700;
  text-align: center;
  line-height: 1.25;
}

.architecture-note {
  margin-top: 16px;
  border: 1px solid #bfdbfe;
  border-radius: var(--radius-sm);
  background: #eff6ff;
  color: #1d4ed8;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
}
</style>
