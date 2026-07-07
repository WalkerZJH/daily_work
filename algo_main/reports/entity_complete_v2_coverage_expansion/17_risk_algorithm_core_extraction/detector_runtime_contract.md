# Detector Runtime Contract

Enabled rule v1 detectors:

- terminal loss warning;
- interval overdue warning;
- frequency drop warning;
- new terminal detection.

Weak enabled when data quality allows:

- quantity drop warning;
- low delivery rate warning only if explicitly enabled and quality-gated.

Disabled or deferred:

- delivery time response detectors when delivery/arrival dates are missing or unstable;
- price detectors without comparable reference price;
- SKU narrowing without product-line or portfolio mapping;
- wallet share without complete platform share context.

Detector output is evidence only:

- severity is not probability;
- confidence is not probability;
- no distributor responsibility claim;
- no competitor replacement claim;
- no policy loss claim;
- no definitive churn claim.
