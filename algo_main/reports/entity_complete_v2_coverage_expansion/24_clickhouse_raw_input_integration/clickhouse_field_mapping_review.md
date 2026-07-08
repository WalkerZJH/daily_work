| standard_field | clickhouse_field | confidence | note |
|---|---|---|---|
| order_id | order_detail_id | high | line-level order detail id |
| order_date | purchase_time | high | primary purchase timestamp; filters sentinel 1900 |
| manufacturer_code | manufacturer_code | high | same semantic code |
| manufacturer_display_name | manufacturer_name | high | display dimension |
| hospital_code | hospital_code | high | same semantic code |
| hospital_name | hospital_name | high | display dimension |
| drug_code | drug_code | high | same semantic code |
| drug_name | generic_name | medium | uses generic name; brand_name is optional display context |
| order_quantity | purchase_quantity | high | purchase-side quantity |
| order_amount | purchase_amount | high | purchase-side amount |
| distributor_code | delivery_enterprise_code | high | delivery enterprise code |
| delivery_date | delivery_time | low | many 1970 sentinel values; detector remains disabled |
| arrival_date | received_time | low | many 1970 sentinel values; detector remains disabled |
| region_code | city_code | medium | city-level routing fallback; confirm if province/county preferred |
| region_name | city | medium | city-level routing fallback; confirm if province/county preferred |
| product_line_name | drug_category | low | display fallback only; not portfolio mapping |