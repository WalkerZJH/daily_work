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


def test_display_lookup_status_gates_frontend_dynamic_payloads(tmp_path: Path) -> None:
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
    adapter_url = adapter_module.as_uri()
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
        if (calls.length !== 1) throw new Error(`${{name}} should only request readiness status: ${{calls.join(',')}}`);
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
        if (calls.length === 1) return response(200, {{ ready: true }});
        return response(200, {{
          batch_context: {{
            report_month: '2026-07',
            score_as_of_date: '2026-07-31',
            data_watermark_at: '2026-07-07 13:32',
            score_batch_id: 'batch',
            result_batch_id: 'batch',
            primary_horizon: 'H6',
            primary_horizon_label: '主视角'
          }},
          overview_metrics: [],
          model_metrics: [],
          fill_policy: {{
            manufacturer_code: 'm1',
            workbench_target_count: 20,
            global_current_month_hospital_drug_count: 1,
            fill_reason: 'ready'
          }},
          rows: [{{
            row_id: 'row-1',
            entity_id: '',
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
            fill_source: '主干风险模型',
            source_type: 'global 命中',
            action: '进入工作台'
          }}]
        }});
      }};

      const readyData = await mod.loadWorkbenchData();
      if (!readyData) throw new Error('ready=true should allow project payload');
      if (calls.length !== 2) throw new Error(`ready=true should request status and payload: ${{calls.join(',')}}`);
      const row = readyData.workbenchDisplayRows[0];
      if (row.hospitalDrugKey !== 'Lookup Hospital × Lookup Drug') {{
        throw new Error(`display names were not preferred: ${{row.hospitalDrugKey}}`);
      }}
      if (row.manufacturer !== 'Lookup Manufacturer' || row.region !== 'Lookup Region') {{
        throw new Error('manufacturer or region display names were not preferred');
      }}
    """
    run_node(script)


def test_frontend_has_no_forbidden_result_source_paths() -> None:
    files = list((FRONTEND / "src").rglob("*")) + list((FRONTEND / "layout").rglob("*"))
    files += [path for path in FRONTEND.glob("*.html")]
    offenders: list[str] = []
    forbidden = ["algo_main", "risk_result_batch", "risk_model_core"]
    for path in files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(FRONTEND).as_posix()}::{token}")
    assert offenders == []
