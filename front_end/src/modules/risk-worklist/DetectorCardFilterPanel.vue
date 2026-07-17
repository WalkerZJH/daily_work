<script setup>
import { ref } from 'vue'

const props = defineProps({
  families: { type: Array, default: () => [] },
  appliedFamily: { type: String, default: '' },
  appliedDetector: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['queryAll', 'queryFamily', 'queryDetector'])
const selectedFamily = ref('')

function toggleFamily(familyId) {
  selectedFamily.value = selectedFamily.value === familyId ? '' : familyId
}

function detectorAvailable(detector) {
  return detector.enabled !== false && detector.status === 'implemented'
}
</script>

<template>
  <div class="detector-filter-panel">
    <div class="detector-filter-panel__all">
      <div>
        <strong>全部规则线索</strong>
        <p>查看当前生产企业、当前观察日期下所有已命中的 Detector 规则线索。</p>
      </div>
      <button type="button" class="btn btn-primary" :disabled="loading" @click="emit('queryAll')">查询全部规则</button>
    </div>

    <div class="detector-family-grid" :class="{ 'detector-family-grid--focused': selectedFamily }">
      <section
        v-for="family in families"
        :id="`detector-family-panel-${family.id}`"
        :key="family.id"
        class="detector-family-card"
        :class="[
          `detector-family-card--${family.id}`,
          {
            'detector-family-card--focused': selectedFamily === family.id,
            'detector-family-card--compact': selectedFamily && selectedFamily !== family.id,
            'detector-family-card--applied': appliedFamily === family.id
          }
        ]"
      >
        <button
          type="button"
          class="detector-family-card__toggle"
          :aria-expanded="selectedFamily === family.id"
          :aria-controls="`detector-family-rules-${family.id}`"
          @click="toggleFamily(family.id)"
        >
          <span>{{ family.label }}</span>
          <small v-if="!selectedFamily || selectedFamily === family.id">{{ family.detectors.length }} 个 Detector · 查看规则 →</small>
        </button>

        <div v-if="selectedFamily === family.id" :id="`detector-family-rules-${family.id}`" class="detector-family-card__body">
          <div class="detector-family-card__heading">
            <p>{{ family.summary }}</p>
            <button type="button" class="btn btn-primary btn-sm" :disabled="loading" @click="emit('queryFamily', family.id)">查询该大类</button>
          </div>
          <div class="detector-card-list">
            <article
              v-for="detector in family.detectors"
              :key="detector.detectorId"
              class="detector-card"
              :class="{ 'detector-card--disabled': !detectorAvailable(detector), 'detector-card--applied': appliedDetector === detector.detectorId }"
            >
              <div>
                <h3>{{ detector.detectorName }}</h3>
                <p>{{ detector.description || detector.caveat || '当前 Catalog 暂未提供规则说明。' }}</p>
                <small>{{ detector.detectorId }}</small>
              </div>
              <button
                v-if="detectorAvailable(detector)"
                type="button"
                class="btn btn-sm"
                :disabled="loading"
                :aria-label="`查询${detector.detectorName}`"
                @click="emit('queryDetector', family.id, detector.detectorId)"
              >查询</button>
              <span v-else class="detector-card__disabled-label">暂不可用</span>
            </article>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.detector-filter-panel { display: grid; gap: 18px; }
.detector-filter-panel__all { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 18px; border: 1px solid var(--border-color, #d8dde6); border-radius: 14px; background: var(--surface-muted, #f7f8fa); }
.detector-filter-panel__all p, .detector-family-card p, .detector-card p { margin: 5px 0 0; color: var(--text-muted, #667085); }
.detector-family-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; align-items: stretch; }
.detector-family-grid--focused { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.detector-family-card { --family-start: #2563eb; --family-end: #38bdf8; --family-soft: #eff6ff; --family-ink: #1e40af; min-height: 180px; overflow: hidden; border: 1px solid color-mix(in srgb, var(--family-start) 78%, #fff); border-radius: 16px; color: #fff; background: linear-gradient(135deg, var(--family-start), var(--family-end)); box-shadow: 0 12px 26px color-mix(in srgb, var(--family-start) 20%, transparent); transition: min-height 220ms ease-out, background 220ms ease-out, border-color 220ms ease-out, box-shadow 220ms ease-out; }
.detector-family-card--price { --family-start: #2563eb; --family-end: #38bdf8; --family-soft: #eff6ff; --family-ink: #1e40af; }
.detector-family-card--fulfillment { --family-start: #059669; --family-end: #34d399; --family-soft: #ecfdf5; --family-ink: #065f46; }
.detector-family-card--terminal { --family-start: #f97316; --family-end: #fbbf24; --family-soft: #fff7ed; --family-ink: #9a3412; }
.detector-family-card--sales { --family-start: #e11d48; --family-end: #fb7185; --family-soft: #fff1f2; --family-ink: #9f1239; }
.detector-family-card__toggle { width: 100%; min-height: 180px; display: flex; flex-direction: column; justify-content: space-between; gap: 24px; padding: 22px; border: 0; color: inherit; text-align: left; background: transparent; cursor: pointer; }
.detector-family-card__toggle span { font-size: 20px; font-weight: 700; }
.detector-family-card__toggle small { color: rgba(255, 255, 255, .88); }
.detector-family-card__toggle:focus-visible { outline: 3px solid #fff; outline-offset: -5px; }
.detector-family-card--focused { grid-column: 1 / -1; grid-row: 1; min-height: 340px; color: var(--family-ink); background: linear-gradient(135deg, var(--family-soft), #fff 72%); border-width: 2px; box-shadow: 0 16px 34px color-mix(in srgb, var(--family-start) 18%, transparent); }
.detector-family-card--focused .detector-family-card__toggle { min-height: auto; padding-bottom: 8px; }
.detector-family-card--focused .detector-family-card__toggle small { color: color-mix(in srgb, var(--family-ink) 78%, #fff); }
.detector-family-card--compact { grid-row: 2; min-height: 110px; }
.detector-family-card--compact .detector-family-card__toggle { min-height: 110px; padding: 18px; }
.detector-family-card--applied { box-shadow: inset 0 0 0 3px rgba(255, 255, 255, .88), 0 12px 26px color-mix(in srgb, var(--family-start) 20%, transparent); }
.detector-family-card__body { padding: 0 22px 22px; animation: detector-card-fade 200ms ease-out; }
.detector-family-card__heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.detector-family-card__heading .btn-primary { border-color: var(--family-start); background: var(--family-start); }
.detector-card-list { display: grid; gap: 10px; }
.detector-card { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 15px; border: 1px solid #d8dde6; border-radius: 12px; background: #f8fafc; }
.detector-card h3 { margin: 0; font-size: 16px; }
.detector-card small { color: #7b8496; }
.detector-card--disabled { opacity: .68; }
.detector-card--applied { border-color: #3b82f6; background: #eff6ff; }
.detector-card__disabled-label { white-space: nowrap; color: #7b8496; font-size: 13px; }
@keyframes detector-card-fade { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 1000px) { .detector-family-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .detector-family-grid:not(.detector-family-grid--focused) .detector-family-card:first-child { grid-column: span 3; } }
@media (max-width: 680px) { .detector-filter-panel__all, .detector-family-card__heading, .detector-card { align-items: stretch; flex-direction: column; } .detector-family-grid, .detector-family-grid--focused { grid-template-columns: 1fr; } .detector-family-card--focused, .detector-family-card--compact { grid-column: auto; grid-row: auto; } }
@media (prefers-reduced-motion: reduce) { .detector-family-card { transition: none; } .detector-family-card__body { animation: none; } }
</style>
