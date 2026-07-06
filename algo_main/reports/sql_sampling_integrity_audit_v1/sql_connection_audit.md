# SQL Connection Audit

## Connection Status

- SQL_DATABASE_URL configured: True
- SQL_DATABASE_URL masked: `mssql+pyodbc://<user>:***@<host>/ylzc_gyl`
- SQL_TABLE: `BS_Agent_DingDan`
- helper reused: alg.cleaning.bs_agent_dingdan.load_env + configs/data_schema/bs_agent_dingdan_schema.yaml
- SQL connection status: success
- failure reason: none

## Notebook / Pipeline Evidence

- Notebook evidence: notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb uses sample_mode=True, max_rows=100000
- Pipeline evidence: alg.cleaning.bs_agent_dingdan_pipeline._read_sql_projected uses SELECT TOP (...) when max_rows/sample_mode is set

No password or full connection string is written by this audit.
