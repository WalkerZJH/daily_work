from __future__ import annotations


class ViewBuilder:
    """Describe future canonical MySQL views without connecting to a database."""

    def describe_views(self) -> dict[str, str]:
        return {
            "v_canonical_orders": self.v_canonical_orders(),
            "v_unit_order_events": self.v_unit_order_events(),
            "v_unit_monthly_agg": self.v_unit_monthly_agg(),
            "v_unit_baseline_snapshot": self.v_unit_baseline_snapshot(),
        }

    @staticmethod
    def v_canonical_orders() -> str:
        return """
CREATE OR REPLACE VIEW v_canonical_orders AS
SELECT
  source_order_id AS order_id,
  source_drug_code AS drug_code,
  source_org_code AS org_code,
  source_order_time AS order_time,
  source_purchase_qty AS purchase_qty,
  source_purchase_amount AS purchase_amount,
  source_purchase_price AS purchase_price,
  source_manufacturer AS manufacturer,
  source_delivery_qty AS delivery_qty,
  source_delivery_time AS delivery_time,
  source_receipt_qty AS receipt_qty,
  source_receipt_time AS receipt_time
FROM source_orders_placeholder;
""".strip()

    @staticmethod
    def v_unit_order_events() -> str:
        return """
CREATE OR REPLACE VIEW v_unit_order_events AS
SELECT
  o.order_id,
  o.org_code,
  m.product_line_code,
  m.product_line_name,
  o.drug_code,
  o.order_time,
  o.purchase_qty,
  o.purchase_amount
FROM v_canonical_orders o
JOIN product_line_mapping_placeholder m ON o.drug_code = m.drug_code;
""".strip()

    @staticmethod
    def v_unit_monthly_agg() -> str:
        return """
CREATE OR REPLACE VIEW v_unit_monthly_agg AS
SELECT
  org_code,
  product_line_code,
  DATE_FORMAT(order_time, '%Y-%m-01') AS month_start,
  COUNT(DISTINCT order_id) AS order_count,
  COUNT(DISTINCT drug_code) AS active_drug_count,
  SUM(purchase_qty) AS purchase_qty
FROM v_unit_order_events
GROUP BY org_code, product_line_code, DATE_FORMAT(order_time, '%Y-%m-01');
""".strip()

    @staticmethod
    def v_unit_baseline_snapshot() -> str:
        return """
CREATE OR REPLACE VIEW v_unit_baseline_snapshot AS
SELECT
  org_code,
  product_line_code,
  MAX(order_time) AS last_order_time,
  COUNT(DISTINCT order_id) AS historical_order_count,
  COUNT(DISTINCT drug_code) AS historical_drug_count
FROM v_unit_order_events
GROUP BY org_code, product_line_code;
""".strip()
