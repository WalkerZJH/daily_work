from __future__ import annotations

from typing import Any


class DetectorNarrativeService:
    def build(
        self,
        *,
        detector_id: str,
        hit: bool,
        reason_code: str,
        metrics: dict[str, Any],
        warnings: list[str],
    ) -> str:
        if reason_code == "MISSING_REQUIRED_FIELDS":
            missing = metrics.get("missing_fields") or []
            return (
                "当前证据不足：数据缺少字段"
                f" {', '.join(missing)}，无法完成该规则判断，需要补充数据或确认字段映射。"
            )
        if warnings and not hit:
            return self._insufficient(detector_id, warnings)
        if detector_id == "low_delivery_rate_warning":
            return self._low_delivery_rate(hit, metrics)
        if detector_id == "delivery_delay_warning":
            return self._delivery_delay(hit, metrics)
        if detector_id == "delivery_rejection_warning":
            return self._delivery_rejection(hit, metrics)
        if detector_id == "low_price_warning":
            return self._low_price(hit, metrics)
        if detector_id == "price_spread_warning":
            return self._price_spread(hit, metrics)
        if detector_id == "terminal_lost_warning":
            return self._terminal_lost(hit, metrics)
        if detector_id == "new_terminal_warning":
            return self._new_terminal(hit, metrics)
        if detector_id == "purchase_quantity_fluctuation_warning":
            return self._quantity_fluctuation(hit, metrics)
        if detector_id == "purchase_frequency_fluctuation_warning":
            return self._frequency_fluctuation(hit, metrics)
        return "当前 detector 为接口预留或保留项，暂未形成可运行的规则解释。"

    @staticmethod
    def _insufficient(detector_id: str, warnings: list[str]) -> str:
        return f"当前证据不足：{detector_id} 未命中，原因包括 {', '.join(warnings)}。"

    @staticmethod
    def _low_delivery_rate(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前配送率未低于配置阈值，或数据不足以判断。"
        return (
            f"该订单配送率为 {_pct(metrics.get('delivery_rate'))}，低于当前配置阈值 "
            f"{_pct(metrics.get('threshold'))}。建议先核实配送数量是否完整回填，再联系配送企业确认是否存在断货、物流或拒配问题。"
        )

    @staticmethod
    def _delivery_delay(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前未发现超过阈值的配送响应延迟，或数据不足以判断。"
        return (
            f"该订单从下单到配送约 {metrics.get('delivery_delay_hours')} 小时，超过当前阈值 "
            f"{metrics.get('threshold_hours')} 小时，存在响应不及时风险。建议排查是否为季节性供货紧张或配送计划异常。"
        )

    @staticmethod
    def _delivery_rejection(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前订单状态未发现拒绝、退货、无法配送、缺货、驳回、拒收或撤单等关键词。"
        return (
            f"订单状态出现拒绝响应类关键词，命中状态为 {metrics.get('order_status')}。"
            "建议联系配送企业确认原因，并核实是否需要调整配送安排。"
        )

    @staticmethod
    def _low_price(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中或证据不足：当前未配置预警价时不会编造预警价，也不会强行触发低价预警。"
        return (
            f"该订单单位可比价 {metrics.get('comparable_unit_price')} 低于预警价 {metrics.get('warning_price')}，"
            f"降幅约 {_pct(metrics.get('price_discount_ratio'))}，可能影响价格体系。建议先核实平台成交价和预警价配置，再横向对比其他省份或医院的价格。"
        )

    @staticmethod
    def _price_spread(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前窗口内单位可比价价差未超过配置阈值，或数据不足以判断。"
        return (
            f"同一产品线单位可比价最低 {metrics.get('min_price')}、最高 {metrics.get('max_price')}，"
            f"价差倍数 {metrics.get('price_spread_ratio')}，超过阈值 {metrics.get('threshold')}。建议核实各省价格数据是否为真实成交价。"
        )

    @staticmethod
    def _terminal_lost(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前未采购天数尚未超过历史采购周期阈值，或历史样本不足。"
        return (
            f"该医院已 {metrics.get('days_since_last_order')} 天未采购，超过历史平均采购周期 "
            f"{metrics.get('avg_purchase_cycle_days')} 天对应阈值，存在终端丢失风险。建议联系医院确认是否停用、换药、价格原因或配送原因。"
        )

    @staticmethod
    def _new_terminal(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前未发现首次有效采购或 180 天后恢复采购达到数量阈值的记录。"
        return (
            f"该医院近期出现有效首次采购或 180 天后恢复采购，采购数量为 {metrics.get('purchase_qty')}。"
            "建议确认是否为新开发客户，并跟踪后续复购稳定性。"
        )

    @staticmethod
    def _quantity_fluctuation(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前采购量未超过近 6 月均值阈值，也未出现明显环比骤降。"
        return (
            f"采购量出现异常波动，当前倍数或变化比例为 {metrics.get('fluctuation_ratio')}。"
            "建议核实是否为合并下单、囤货或库存策略变化。"
        )

    @staticmethod
    def _frequency_fluctuation(hit: bool, metrics: dict[str, Any]) -> str:
        if not hit:
            return "该规则未命中：当前采购频次未超过近 6 月平均频次阈值，也未出现明显环比骤降。"
        return (
            f"采购频次出现异常波动，当前倍数或变化比例为 {metrics.get('fluctuation_ratio')}。"
            "建议结合终端丢失、新进和季节性需求一起核实。"
        )


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "--"
