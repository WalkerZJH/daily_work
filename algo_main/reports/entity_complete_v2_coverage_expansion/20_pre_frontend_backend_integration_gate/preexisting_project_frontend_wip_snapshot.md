# Pre-existing Project/Frontend WIP Snapshot

- project_wip_present: True
- frontend_wip_present: True
- based_on_working_tree: true
- audit_mode: read_only_for_project_and_front_end
- stage_commit_revert_project_frontend: forbidden

This audit uses the current working tree for contract review. Pre-existing
`project/` and `front_end/` WIP is not treated as an integration blocker by
itself. If a file cannot be read or the WIP makes a contract ambiguous, the
specific page/API is marked `CONDITIONAL_READY` or `BLOCKED`.

## git status --short -- project front_end

```text
D front_end/algo-config.html
 D front_end/algo-health.html
 M front_end/app.js
 M front_end/backtest.html
 M front_end/clue-detail.html
 M front_end/clues.html
 M front_end/components.json
 M front_end/dashboard.html
 M front_end/index.html
 M front_end/layout/layout.js
 M front_end/package-lock.json
 M front_end/package.json
 M front_end/src/App.vue
 M front_end/src/layout/Topbar.vue
 M front_end/src/layout/navigation.js
 M front_end/src/main.js
 D front_end/src/modules/algo-config/AlgoConfigView.vue
 D front_end/src/modules/algo-config/architecture.js
 D front_end/src/modules/algo-config/components/ApiControlPanel.vue
 D front_end/src/modules/algo-config/components/ArchitectureDiagram.vue
 D front_end/src/modules/algo-config/components/ConfigPanel.vue
 D front_end/src/modules/algo-config/components/DebugPanel.vue
 D front_end/src/modules/algo-config/components/RuntimeWarnings.vue
 D front_end/src/modules/algo-config/composables/useAlgoConfigApi.js
 D front_end/src/modules/algo-health/AlgoHealthView.vue
 D front_end/src/modules/algo-health/components/DetectorResultTable.vue
 D front_end/src/modules/algo-health/components/DetectorRunPanel.vue
 D front_end/src/modules/algo-health/components/DetectorSummaryCards.vue
 D front_end/src/modules/algo-health/components/PalivePreviewTable.vue
 D front_end/src/modules/algo-health/components/PaliveSmokeTestPanel.vue
 D front_end/src/modules/algo-health/components/SmokeTestSummaryCards.vue
 D front_end/src/modules/algo-health/composables/useDatabaseSmokeTest.js
 D front_end/src/modules/algo-health/composables/useDetectorRun.js
 M front_end/src/services/backendApi.js
 D front_end/src/style.css
 D front_end/src/styles/base.css
 D front_end/src/styles/components.css
 D front_end/src/styles/layout.css
 D front_end/src/styles/utilities.css
 M front_end/vite.config.js
 D front_end/watchlist.html
 M project/app/main.py
 M project/docs/API.md
?? front_end/algo-architecture.html
?? front_end/oneshot.html
?? front_end/src/modules/algo-architecture/
?? front_end/src/modules/monthly-demo/
?? front_end/src/modules/monthly-report/
?? front_end/src/modules/monthly-workbench/
?? front_end/src/modules/oneshot-monitor/
?? front_end/src/modules/risk-worklist/
?? front_end/src/styles/library/
?? front_end/src/styles/main.scss
?? project/app/api/routes_frontend_pages.py
?? project/app/schemas/frontend_pages.py
?? project/app/services/frontend_page_service.py
?? project/tests/test_frontend_pages_api.py
```

## git diff --name-status -- project front_end

```text
D	front_end/algo-config.html
D	front_end/algo-health.html
M	front_end/app.js
M	front_end/backtest.html
M	front_end/clue-detail.html
M	front_end/clues.html
M	front_end/components.json
M	front_end/dashboard.html
M	front_end/index.html
M	front_end/layout/layout.js
M	front_end/package-lock.json
M	front_end/package.json
M	front_end/src/App.vue
M	front_end/src/layout/Topbar.vue
M	front_end/src/layout/navigation.js
M	front_end/src/main.js
D	front_end/src/modules/algo-config/AlgoConfigView.vue
D	front_end/src/modules/algo-config/architecture.js
D	front_end/src/modules/algo-config/components/ApiControlPanel.vue
D	front_end/src/modules/algo-config/components/ArchitectureDiagram.vue
D	front_end/src/modules/algo-config/components/ConfigPanel.vue
D	front_end/src/modules/algo-config/components/DebugPanel.vue
D	front_end/src/modules/algo-config/components/RuntimeWarnings.vue
D	front_end/src/modules/algo-config/composables/useAlgoConfigApi.js
D	front_end/src/modules/algo-health/AlgoHealthView.vue
D	front_end/src/modules/algo-health/components/DetectorResultTable.vue
D	front_end/src/modules/algo-health/components/DetectorRunPanel.vue
D	front_end/src/modules/algo-health/components/DetectorSummaryCards.vue
D	front_end/src/modules/algo-health/components/PalivePreviewTable.vue
D	front_end/src/modules/algo-health/components/PaliveSmokeTestPanel.vue
D	front_end/src/modules/algo-health/components/SmokeTestSummaryCards.vue
D	front_end/src/modules/algo-health/composables/useDatabaseSmokeTest.js
D	front_end/src/modules/algo-health/composables/useDetectorRun.js
M	front_end/src/services/backendApi.js
D	front_end/src/style.css
D	front_end/src/styles/base.css
D	front_end/src/styles/components.css
D	front_end/src/styles/layout.css
D	front_end/src/styles/utilities.css
M	front_end/vite.config.js
D	front_end/watchlist.html
M	project/app/main.py
M	project/docs/API.md
```

## git ls-files --others --exclude-standard project front_end

```text
front_end/algo-architecture.html
front_end/oneshot.html
front_end/src/modules/algo-architecture/AlgoArchitectureView.vue
front_end/src/modules/monthly-demo/demoData.js
front_end/src/modules/monthly-demo/pageDataAdapter.js
front_end/src/modules/monthly-report/MonthlyReportView.vue
front_end/src/modules/monthly-report/ProofCaseView.vue
front_end/src/modules/monthly-workbench/MonthlyWorkbenchView.vue
front_end/src/modules/oneshot-monitor/OneshotMonitorView.vue
front_end/src/modules/risk-worklist/RiskEntityDetailView.vue
front_end/src/modules/risk-worklist/RiskEntityListView.vue
front_end/src/styles/library/_base.scss
front_end/src/styles/library/_components.scss
front_end/src/styles/library/_layout.scss
front_end/src/styles/library/_modules.scss
front_end/src/styles/library/_tokens.scss
front_end/src/styles/library/_utilities.scss
front_end/src/styles/main.scss
project/app/api/routes_frontend_pages.py
project/app/schemas/frontend_pages.py
project/app/services/frontend_page_service.py
project/tests/test_frontend_pages_api.py
```
