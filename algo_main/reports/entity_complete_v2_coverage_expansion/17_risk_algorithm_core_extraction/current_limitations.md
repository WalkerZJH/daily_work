# Current Limitations

- SQL and ClickHouse raw readers are interface stubs in this stage.
- The fixture artifact is a stub for contract validation, not a formal model.
- Formal production run still requires a stable exported artifact under the configured artifact directory.
- Product-line mapping is not allowed to silently change entity grain.
- Delivery time detectors remain disabled when delivery or arrival timestamps are missing.
- Price, SKU, and wallet-share detectors require additional business mappings before enablement.
- Proof-case report remains disabled until customer-confirmed feedback exists.
- Customer-facing probability service remains disabled.
