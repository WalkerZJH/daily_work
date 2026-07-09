from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def run_node(script: str) -> None:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def adapter_module_source(tmp_path: Path) -> str:
    source = (FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js").read_text(encoding="utf-8")
    source = source.replace(
        "from '../../services/backendApi'",
        f"from '{(FRONTEND / 'src' / 'services' / 'backendApi.js').as_uri()}'",
    )
    source = source.replace(
        "from './demoData'",
        f"from '{(FRONTEND / 'src' / 'modules' / 'monthly-demo' / 'demoData.js').as_uri()}'",
    )
    adapter_module = tmp_path / "pageDataAdapter.test.mjs"
    adapter_module.write_text(source, encoding="utf-8")
    return adapter_module.as_uri()


def test_display_lookup_status_gates_frontend_dynamic_payloads(tmp_path: Path) -> None:
    adapter_url = adapter_module_source(tmp_path)
    script = f"""
      globalThis.window = {{
        setTimeout,
        clearTimeout,
        location: {{ search: '' }},
        __BACKEND_BASE_URL__: 'http://project-api.test',
        localStorage: {{ getItem: () => null }}
      }};

      const mod = await import('{adapter_url}');

      function response(status, payload) {{
        return {{
          ok: status >= 200 && status < 300,
          status,
          statusText: String(status),
          text: async () => payload === undefined ? '' : JSON.stringify(payload)
        }};
      }}

      async function expectFallback(name, fetchImpl) {{
        const calls = [];
        globalThis.fetch = async (url, options) => {{
          calls.push(String(url));
          return fetchImpl(url, options);
        }};
        const data = await mod.loadWorkbenchData();
        if (data !== null) throw new Error(`${{name}} should use demo fallback`);
        if (calls.length !== 1) throw new Error(`${{name}} should only request display lookup status: ${{calls.join(',')}}`);
        if (!calls[0].endsWith('/api/v1/display-lookup/status')) throw new Error(`${{name}} wrong first call: ${{calls[0]}}`);
      }}

      await expectFallback('ready=false', async () => response(200, {{ ready: false }}));
      await expectFallback('404', async () => response(404, {{ detail: 'not found' }}));
      await expectFallback('network-error', async () => {{ throw new Error('network down'); }});
      await expectFallback('timeout', async () => {{
        const error = new Error('aborted');
        error.name = 'AbortError';
        throw error;
      }});

      const calls = [];
      globalThis.fetch = async (url) => {{
        calls.push(String(url));
        if (String(url).endsWith('/api/v1/display-lookup/status')) return response(200, {{ ready: true }});
        if (String(url).endsWith('/api/v1/workbench')) return response(200, {{
          batch_context: {{
            report_month: '2026-07',
            score_as_of_date: '2026-07-31',
            data_watermark_at: '2026-07-07 13:32',
            score_batch_id: 'batch',
            result_batch_id: 'batch',
            primary_horizon: 'H6',
            primary_horizon_label: 'main'
          }},
          overview_metrics: [],
          fill_policy: {{
            manufacturer_code: 'm1',
            workbench_target_count: 20,
            global_current_month_hospital_drug_count: 1,
            fill_reason: 'ready'
          }},
          rows: [{{
            row_id: 'row-1',
            entity_id: 'entity-1',
            manufacturer_code: 'm1',
            manufacturer_display_name: 'Lookup Manufacturer',
            hospital_code: 'h1',
            hospital_display_name: 'Lookup Hospital',
            drug_group: 'd1',
            drug_display_name: 'Lookup Drug',
            region_display_name: 'Lookup Region',
            risk_probability: 0.62,
            average_consumption_in_window: 1000,
            business_score: 620,
            fill_source: 'monthly',
            source_type: 'monthly',
            action: 'detail'
          }}]
        }});
        if (String(url).endsWith('/api/v1/daily-detector/status')) return response(404, {{ detail: 'not found' }});
        throw new Error(`unexpected url ${{url}}`);
      }};

      const readyData = await mod.loadWorkbenchData();
      if (!readyData) throw new Error('ready=true should allow project payload');
      if (calls.length !== 3) throw new Error(`ready=true should request display status, workbench and detector status: ${{calls.join(',')}}`);
      const row = readyData.workbenchDisplayRows[0];
      if (row.hospitalDrugKey !== 'Lookup Hospital × Lookup Drug') {{
        throw new Error(`display names were not preferred: ${{row.hospitalDrugKey}}`);
      }}
      if (row.manufacturer !== 'Lookup Manufacturer' || row.region !== 'Lookup Region') {{
        throw new Error('manufacturer or region display names were not preferred');
      }}
      if (row.lossValue !== 620 || row.lossValueText !== '¥620') {{
        throw new Error(`loss value was not mapped from compatible score field: ${{row.lossValueText}}`);
      }}
    """
    run_node(script)


def test_daily_detector_status_falls_back_to_demo_mock(tmp_path: Path) -> None:
    adapter_url = adapter_module_source(tmp_path)
    script = f"""
      globalThis.window = {{
        setTimeout,
        clearTimeout,
        location: {{ search: '' }},
        __BACKEND_BASE_URL__: 'http://project-api.test',
        localStorage: {{ getItem: () => null }}
      }};

      const mod = await import('{adapter_url}');

      function response(status, payload) {{
        return {{
          ok: status >= 200 && status < 300,
          status,
          statusText: String(status),
          text: async () => payload === undefined ? '' : JSON.stringify(payload)
        }};
      }}

      async function expectFallback(name, fetchImpl) {{
        const calls = [];
        globalThis.fetch = async (url, options) => {{
          calls.push(String(url));
          return fetchImpl(url, options);
        }};
        const data = await mod.loadRuleCluesData();
        if (data !== null) throw new Error(`${{name}} should keep page-level demo fallback`);
        if (calls.length !== 1) throw new Error(`${{name}} should only request daily detector readiness: ${{calls.join(',')}}`);
        if (!calls[0].endsWith('/api/v1/daily-detector/status')) throw new Error(`${{name}} wrong first call: ${{calls[0]}}`);
      }}

      await expectFallback('ready=false', async () => response(200, {{ ready: false }}));
      await expectFallback('404', async () => response(404, {{ detail: 'not found' }}));
      await expectFallback('network-error', async () => {{ throw new Error('network down'); }});
      await expectFallback('timeout', async () => {{
        const error = new Error('aborted');
        error.name = 'AbortError';
        throw error;
      }});
    """
    run_node(script)


def test_daily_detector_ready_true_consumes_project_detector_payloads(tmp_path: Path) -> None:
    adapter_url = adapter_module_source(tmp_path)
    script = f"""
      globalThis.window = {{
        setTimeout,
        clearTimeout,
        location: {{ search: '' }},
        __BACKEND_BASE_URL__: 'http://project-api.test',
        localStorage: {{ getItem: () => null }}
      }};

      const mod = await import('{adapter_url}');

      function response(status, payload) {{
        return {{
          ok: status >= 200 && status < 300,
          status,
          statusText: String(status),
          text: async () => payload === undefined ? '' : JSON.stringify(payload)
        }};
      }}

      const calls = [];
      globalThis.fetch = async (url) => {{
        const href = String(url);
        calls.push(href);
        if (href.endsWith('/api/v1/daily-detector/status')) return response(200, {{
          ready: true,
          run_date: '2026-07-09',
          report_month: '2026-07',
          clue_count: 2,
          attached_high_risk_count: 1,
          scanned_entity_count: 10
        }});
        if (href.includes('/api/v1/daily-detector/clues')) return response(200, {{
          ready: true,
          items: [
            {{
              detector_clue_id: 'clue-1',
              risk_entity_id: 'risk-1',
              is_monthly_high_risk_entity: true,
              hospital_display_name: 'Monthly Hospital',
              drug_display_name: 'Monthly Drug',
              detector_name: 'Interval Rule',
              detector_family: 'purchase rhythm',
              detector_score: 0.88,
              detector_level: 'high',
              hit_flag: true,
              root_cause_label: 'gap',
              evidence_text: 'evidence',
              run_date: '2026-07-09',
              monthly_risk_probability: 0.77,
              monthly_loss_value: 7700
            }},
            {{
              detector_clue_id: 'clue-2',
              is_monthly_high_risk_entity: false,
              hospital_display_name: 'Rule Hospital',
              drug_display_name: 'Rule Drug',
              detector_name: 'Rule Only',
              detector_family: 'daily rule',
              detector_score: 0.41,
              detector_level: 'watch',
              hit_flag: true,
              root_cause_label: 'rule',
              evidence_text: 'rule-only evidence',
              run_date: '2026-07-09'
            }}
          ]
        }});
        if (href.endsWith('/api/v1/detectors/catalog')) return response(200, {{
          ready: true,
          items: [{{ detector_id: 'interval', detector_name: 'Interval Rule', detector_family: 'purchase rhythm', status: 'implemented' }}]
        }});
        if (href.endsWith('/api/v1/detectors/config-status')) return response(200, {{
          effective_config_version: 'v1',
          latest_run_date: '2026-07-09',
          pending_config_exists: true,
          next_run_required: true
        }});
        throw new Error(`unexpected url ${{href}}`);
      }};

      const data = await mod.loadRuleCluesData();
      if (!data) throw new Error('ready=true should return detector context');
      if (!calls.some((url) => url.includes('/api/v1/daily-detector/clues'))) {{
        throw new Error(`daily detector clues endpoint was not requested: ${{calls.join(',')}}`);
      }}
      if (data.dailyDetectorClues.length !== 2) throw new Error('daily clues were not mapped');
      const monthly = data.dailyDetectorClues.find((item) => item.id === 'clue-1');
      const ruleOnly = data.dailyDetectorClues.find((item) => item.id === 'clue-2');
      if (!monthly?.isMonthlyHighRiskEntity || monthly.sourceType !== 'monthly_high_risk') throw new Error('monthly clue source was not mapped');
      if (ruleOnly?.isMonthlyHighRiskEntity || ruleOnly.sourceType !== 'daily_rule_clue') throw new Error('rule-only clue source was not mapped');
      if (monthly.detectorScoreLabel !== '规则巡检分' || ruleOnly.detectorScoreLabel !== '规则巡检分') throw new Error('detector score label is wrong');
      if (ruleOnly.monthlyRiskProbabilityText !== '-') throw new Error('rule-only clue should not display monthly probability');
      if (data.detectorConfigStatus.message.indexOf('下一次 detector 巡检运行后生效') === -1) throw new Error('config status message missing');
    """
    run_node(script)


def test_frontend_has_no_forbidden_result_source_paths() -> None:
    files = list((FRONTEND / "src").rglob("*")) + list((FRONTEND / "layout").rglob("*"))
    files += [path for path in FRONTEND.glob("*.html")]
    offenders: list[str] = []
    forbidden = ["algo_main", "risk_result_batch", "risk_model_core", "daily_work/prototype"]
    for path in files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(FRONTEND).as_posix()}::{token}")
    assert offenders == []
