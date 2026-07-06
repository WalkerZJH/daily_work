2026-07-06T01:23:43.679130+00:00 stage=start
2026-07-06T01:23:43.696977+00:00 stage=load_feature_label_frame
2026-07-06T01:24:34.951058+00:00 stage=leakage_audit closed_rows=3396221
2026-07-06T01:24:35.392704+00:00 stage=feature_group_ablation
2026-07-06T01:24:35.394128+00:00 stage=feature_group_ablation feature_set=base_recency_frequency
2026-07-06T01:27:35.442954+00:00 stage=feature_group_ablation feature_set=base_plus_interval
2026-07-06T01:33:44.871187+00:00 stage=feature_group_ablation feature_set=base_plus_demand_shape
2026-07-06T01:37:14.460783+00:00 stage=feature_group_ablation feature_set=base_plus_manufacturer_hospital_context
2026-07-06T01:41:48.212974+00:00 stage=feature_group_ablation feature_set=base_plus_manufacturer_drug_context
2026-07-06T01:44:52.707705+00:00 stage=feature_group_ablation feature_set=base_plus_hospital_drug_choice_set_context
2026-07-06T01:47:28.553285+00:00 stage=feature_group_ablation feature_set=base_plus_switching_context
2026-07-06T01:50:03.683758+00:00 stage=feature_group_ablation feature_set=all_safe_features_without_choice_set
2026-07-06T01:56:34.575568+00:00 stage=feature_group_ablation feature_set=all_safe_features_with_choice_set
2026-07-06T02:02:26.784684+00:00 stage=feature_group_ablation feature_set=all_features
2026-07-06T02:08:46.200399+00:00 stage=model_family_comparison
2026-07-06T02:08:46.202634+00:00 stage=model_family feature_set=base_recency_frequency model=logistic_regression
2026-07-06T02:11:01.358120+00:00 stage=model_family feature_set=base_recency_frequency model=xgboost_small
2026-07-06T02:13:13.498543+00:00 stage=model_family feature_set=base_recency_frequency model=lightgbm_small
2026-07-06T02:15:35.730330+00:00 stage=model_family feature_set=base_recency_frequency model=catboost_small
2026-07-06T02:21:50.561728+00:00 stage=model_family feature_set=base_plus_interval model=logistic_regression
2026-07-06T02:22:50.969297+00:00 stage=model_family feature_set=base_plus_interval model=xgboost_small
2026-07-06T02:27:36.698637+00:00 stage=model_family feature_set=base_plus_interval model=lightgbm_small
2026-07-06T02:31:29.335357+00:00 stage=model_family feature_set=base_plus_interval model=catboost_small
2026-07-06T02:38:10.281869+00:00 stage=model_family feature_set=all_safe_features_without_choice_set model=logistic_regression
2026-07-06T02:40:15.106020+00:00 stage=model_family feature_set=all_safe_features_without_choice_set model=xgboost_small
2026-07-06T02:45:10.133790+00:00 stage=model_family feature_set=all_safe_features_without_choice_set model=lightgbm_small
2026-07-06T02:49:24.871533+00:00 stage=model_family feature_set=all_safe_features_without_choice_set model=catboost_small
2026-07-06T02:57:39.413243+00:00 stage=model_family feature_set=all_safe_features_with_choice_set model=logistic_regression
2026-07-06T03:00:01.001941+00:00 stage=model_family feature_set=all_safe_features_with_choice_set model=xgboost_small
2026-07-06T03:05:03.311714+00:00 stage=model_family feature_set=all_safe_features_with_choice_set model=lightgbm_small
2026-07-06T03:09:37.033818+00:00 stage=model_family feature_set=all_safe_features_with_choice_set model=catboost_small
2026-07-06T03:17:05.915564+00:00 stage=xgboost_tuning
2026-07-06T03:17:05.916635+00:00 stage=xgb_tuning config=1/5
2026-07-06T03:18:00.390360+00:00 stage=xgb_tuning config=2/5
2026-07-06T03:18:56.083866+00:00 stage=xgb_tuning config=3/5
2026-07-06T03:19:56.489030+00:00 stage=xgb_tuning config=4/5
2026-07-06T03:20:48.228188+00:00 stage=xgb_tuning config=5/5
2026-07-06T03:21:40.044325+00:00 stage=xgb_tuning_test selected_config=5
2026-07-06T03:27:10.552469+00:00 stage=calibration
2026-07-06T03:30:13.222014+00:00 stage=generalization
2026-07-06T03:30:17.140287+00:00 stage=learning_curve end_year=2020 horizon=H12
2026-07-06T03:30:27.762718+00:00 stage=learning_curve end_year=2020 horizon=H3
2026-07-06T03:30:35.729782+00:00 stage=learning_curve end_year=2020 horizon=H6
2026-07-06T03:30:55.967403+00:00 stage=learning_curve end_year=2021 horizon=H12
2026-07-06T03:31:08.553446+00:00 stage=learning_curve end_year=2021 horizon=H3
2026-07-06T03:31:19.467734+00:00 stage=learning_curve end_year=2021 horizon=H6
2026-07-06T03:31:42.645539+00:00 stage=learning_curve end_year=2022 horizon=H12
2026-07-06T03:31:59.412950+00:00 stage=learning_curve end_year=2022 horizon=H3
2026-07-06T03:32:16.484305+00:00 stage=learning_curve end_year=2022 horizon=H6
2026-07-06T03:32:41.560093+00:00 stage=learning_curve end_year=2023 horizon=H12
2026-07-06T03:33:06.316775+00:00 stage=learning_curve end_year=2023 horizon=H3
2026-07-06T03:33:28.385384+00:00 stage=learning_curve end_year=2023 horizon=H6
2026-07-06T03:33:57.519341+00:00 stage=learning_curve end_year=2024 horizon=H3
2026-07-06T03:34:31.609350+00:00 stage=learning_curve end_year=2024 horizon=H6
2026-07-06T03:35:08.750650+00:00 stage=manufacturer_holdout manufacturer=C458C50660B24C6B96A91FEBAAE8E5C8 horizon=H12
2026-07-06T03:35:14.660155+00:00 stage=manufacturer_holdout manufacturer=C458C50660B24C6B96A91FEBAAE8E5C8 horizon=H3
2026-07-06T03:35:29.249060+00:00 stage=manufacturer_holdout manufacturer=C458C50660B24C6B96A91FEBAAE8E5C8 horizon=H6
2026-07-06T03:35:46.334442+00:00 stage=manufacturer_holdout manufacturer=1D93E15EBB9B4F14A1C18E0CD1750A0A horizon=H12
2026-07-06T03:35:53.519358+00:00 stage=manufacturer_holdout manufacturer=1D93E15EBB9B4F14A1C18E0CD1750A0A horizon=H3
2026-07-06T03:36:07.198255+00:00 stage=manufacturer_holdout manufacturer=1D93E15EBB9B4F14A1C18E0CD1750A0A horizon=H6
2026-07-06T03:36:23.026480+00:00 stage=manufacturer_holdout manufacturer=263F9947B4FA4F8DB61C9FF48D5A942A horizon=H12
2026-07-06T03:36:31.334425+00:00 stage=manufacturer_holdout manufacturer=263F9947B4FA4F8DB61C9FF48D5A942A horizon=H3
2026-07-06T03:36:47.516152+00:00 stage=manufacturer_holdout manufacturer=263F9947B4FA4F8DB61C9FF48D5A942A horizon=H6
2026-07-06T03:37:06.101263+00:00 stage=manufacturer_holdout manufacturer=9701EFF559DF4862AF18CF0DC1B6962D horizon=H12
2026-07-06T03:37:14.087902+00:00 stage=manufacturer_holdout manufacturer=9701EFF559DF4862AF18CF0DC1B6962D horizon=H3
2026-07-06T03:37:29.006432+00:00 stage=manufacturer_holdout manufacturer=9701EFF559DF4862AF18CF0DC1B6962D horizon=H6
2026-07-06T03:38:24.723854+00:00 stage=candidate_policy_v2
2026-07-06T03:38:39.262796+00:00 stage=done
