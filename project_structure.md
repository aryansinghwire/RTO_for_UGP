RTO_for_UGP/
├── add_node2vec.py
├── build_features.py
├── build_graph.py
├── eval_harness.py
├── india_synth_generator.py
├── profile_data.py
├── sample_subgraph.py
├── train_baselines.py
├── train_fusion.py
├── train_gnn.py
├── train_transformer.py
├── tune_threshold.py
│
├── data/
│   ├── checks.py
│   ├── clean_data.py
│   ├── customer_nodes_training.p
│   ├── customer_nodes_testing.p
│   ├── product_nodes_training.p
│   ├── product_nodes_testing.p
│   ├── event_table_training.p
│   ├── event_table_testing.p
│   │
│   ├── clean/
│   ├── features/
│   ├── features_india/
│   ├── features_india_500k/
│   ├── features_poscontrol/
│   ├── graph/
│   ├── graph_india/
│   ├── graph_india_500k/
│   ├── graph_poscontrol/
│   ├── synth_india/
│   ├── synth_india_500k/
│   └── synth_poscontrol/
│
├── graph/
│   ├── sub_train_test.p
│   └── sub_train_train.p
│
├── catboost_info/
│   ├── catboost_training.json
│   ├── learn_error.tsv
│   ├── time_left.tsv
│   ├── learn/
│   └── tmp/
│
├── checkpoint_india_phase0_complete.md
├── checkpoint_phase0_phase1.md
├── checkpoint_phase0_phase2.md
├── checkpoint_phase0_phase3.md
└── data_profile_report.md