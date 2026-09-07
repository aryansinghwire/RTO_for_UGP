# Source Guide — When to Use Which File

## 00_PROJECT_MASTER_CONTEXT.md
Use first for:
- project overview;
- return vs RTO distinction;
- current conclusions;
- architecture decisions;
- major numbers;
- how the three sources relate.

## 01_RETURN_GNN_PROJECT_FINDINGS.md
Use for:
- project-specific experimental results;
- GraphSAGE vs Graph Transformer;
- cold-start results;
- why Node2Vec/fusion were rejected;
- why GEA/KAN were not implemented;
- AUC/F1 rationale.

## 02_RETURNFORMER_PAPER_RAG.md
Use for:
- exact Returnformer architecture;
- Node2Vec;
- attention fusion;
- Graph Transformer;
- GEA;
- KAN;
- paper training settings;
- paper metrics;
- paper ablations/sensitivity;
- paper limitations.

## 03_RTO_RISK_ENGINE_PRD_RAG.md
Use for:
- MVP scope;
- India RTO definition;
- schema adaptation;
- synthetic data rules;
- product requirements;
- latency/compliance/multitenancy;
- release phases;
- real-time extension.

## Original PDFs
The original PDFs should be retained separately when exact wording, figures, page layout, citations, full references, or detailed equations are required.

## Important evidence hierarchy
1. For project experiment results: use `01_RETURN_GNN_PROJECT_FINDINGS.md`.
2. For what the research paper claims: use `02_RETURNFORMER_PAPER_RAG.md`.
3. For product requirements: use `03_RTO_RISK_ENGINE_PRD_RAG.md`.
4. For combined reasoning: use `00_PROJECT_MASTER_CONTEXT.md`.

Do not conflate:
- paper AUC 0.844 with project GraphSAGE AUC 0.876;
- post-delivery returns with pre-delivery RTO;
- synthetic-data validation with real-world accuracy;
- the paper's proposed architecture with the project's empirically validated GraphSAGE result.
