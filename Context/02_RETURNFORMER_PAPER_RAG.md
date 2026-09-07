# Returnformer — Compact Technical Reference

## Citation
Cao, Q.; Zhang, N.; Li, H. “Returnformer: A Graph Transformer-Based Model for Predicting Product Returns in E-Commerce.” *Entropy* 2026, 28, 72. DOI: 10.3390/e28010072.

## Research objective
Predict product-return behaviour before payment using customer–product interaction structure.

The paper argues that customer return behaviour is naturally represented by a bipartite graph and that graph representation learning can capture relational patterns missed by flat features.

## Dataset
ASOS UK fast-fashion dataset, September–November 2021.

After preprocessing:
- Training events: 939,537.
- Test events: 858,526.
- Users: 1,084,504.
- Product variants: 338,076.
- Return:keep ≈ 1.2:1.
- Training = September–October.
- Test = October–November.

Returned event label = 1; kept event label = 0.

Preprocessing:
- Remove duplicates.
- Handle missing values/outliers.
- Recode customer/product IDs.
- Convert birth year to age.
- Exclude ~30,000 customers older than 90.
- One-hot encode categorical variables.
- Standardize numerical variables.

## Graph representation

Graph `G=(U,I,E)`:
- `U` = customer nodes.
- `I` = product nodes.
- `E` = customer-product interaction edges.

Customer features:
- ID.
- Age.
- Gender.
- Shipping country.
- Membership.
- Historical sales volume.
- Historical return volume.
- Customer return rate.
- Historical return-reason proportions (12 codes).

Product features:
- Variant/product/supplier IDs.
- Product type.
- Brand.
- Average price.
- Average discounted price.
- Sales volume.
- Return volume.
- Product return rate.
- Historical return-reason proportions.

Prediction target is an edge-level keep/return classification.

## Returnformer pipeline

**Original node features + Node2Vec structural embeddings**
→ **attention fusion**
→ **Graph Transformer**
→ **Graph External Attention (GEA)**
→ **KAN decoder**
→ **return probability**

### 1. Node2Vec data augmentation
Large graphs are partitioned into smaller subgraphs for computational reasons. Partitioning can destroy global structural relationships.

Node2Vec is used to obtain global topological embeddings before partitioning.

Node2Vec parameters:
- `p = 0.8`
- `q = 0.8`

### 2. Attention fusion
Let original features be `Xo` and structural features be `Xs`.

Each is linearly projected:
- `X'o = Xo Wo`
- `X's = Xs Ws`

Attention scores:
- `ao = tanh(X'o qo)`
- `as = tanh(X's qs)`

Softmax converts them into weights, then:
`h = αs X's + αo X'o`

Purpose: dynamically determine how much original vs structural information to use.

### 3. Graph Transformer
The Graph Transformer performs self-attention among nodes in the current subgraph, allowing long-range interactions inside that subgraph.

The implementation removes edge-feature processing and incorporates graph structure through the attention neighbourhood.

For each head:
- `Q = WQ h`
- `K = WK h`
- `V = WV h`

Attention:
`w_ij = softmax((Qi · Kj) / sqrt(dk))`

The softmax input is clamped to [-5,+5] for numerical stability.

Multi-head outputs are concatenated and projected.

Then:
- LayerNorm + residual.
- 2-layer feed-forward network with GELU.
- LayerNorm + residual.

Settings:
- 2 Graph Transformer layers.
- 4 attention heads.
- embedding dimension `d=128`.
- dropout `0.45`.

### 4. Graph External Attention (GEA)
Partitioning prevents a normal local encoder from directly modelling relationships between different subgraphs.

GEA introduces external learnable key/value memory:
- `Uk`: external keys.
- `Uv`: external values.
- `m = 20` virtual nodes.
- `Hext = 1` attention head.

Current node embeddings attend to the external memory. Dual normalization is used to stabilize the attention matrix.

GEA is intended to share common return patterns across subgraphs.

### 5. KAN decoder
KAN replaces a conventional inner-product/shallow-MLP decoder.

MLP applies repeated linear transforms with fixed activations:
`F(z)=σ(Wz+b)`

KAN uses a matrix of trainable univariate functions:
`KAN(X) = (ΦL ○ ... ○ Φ1)(X)`

The paper describes these functions using B-splines and places learnable functions on edges to capture complex interactions with fewer parameters.

## Training setup
- Python 3.9.
- sklearn, pandas, numpy and other open-source libraries.
- Cross-entropy loss.
- Adam optimizer.
- Optuna hyperparameter search.
- Probability threshold = 0.5.
- 10% of training data randomly sampled for validation.

Search:
- Batch size: 64, 128, 256.
- Embedding dimension: 16, 32, 64, 128, 256.
- Learning rate: 1e-5 to 1e-3.
- Dropout: 0.2 or 0.5.

Final settings:
- Node2Vec `p=0.8`, `q=0.8`.
- GT layers = 2.
- GT heads = 4.
- GEA virtual nodes = 20.
- GEA heads = 1.
- `d=128`.
- LR = 2e-5.
- dropout = 0.45.
- batch size = 128.

## Baselines
ML:
- MLP.
- XGBoost.
- LightGBM.
- CatBoost.

GNN:
- GCN.
- GAT.
- GraphSAGE.

Metrics:
- Accuracy.
- Precision.
- Recall.
- F1.
- AUC.

## Paper results
Returnformer:
- Accuracy = 75.04%.
- Precision = 72.29%.
- Recall = 86.75%.
- F1 = 78.87%.
- AUC = 84.42% (0.844).

It outperformed the seven baselines on every reported metric except precision.

GraphSAGE:
- F1 = 77.41%, the highest F1 among comparison models.

High-return customers (return rate >= 50%):
- Accuracy = 79.23%.
- Precision = 80.80%.
- Recall = 95.71%.
- F1 = 87.63%.
- AUC = 78.21%.

PR analysis:
- Average Precision (AP) = 0.865.
- Returnformer achieves higher precision at the same recall level than the baselines.

## Ablation
The paper removes:
1. Data augmentation / Node2Vec.
2. Graph-level attention / GEA.
3. KAN decoder.

The full Returnformer performs better than the simplified variants on all reported metrics except precision.

Paper interpretation:
- Node2Vec restores structural information lost by graph partitioning.
- GEA captures relationships/common return patterns across subgraphs.
- KAN improves nonlinear decision boundaries.

## Sensitivity
Tested:
- GT layers: 1–4.
- GT attention heads: 1, 2, 4, 8.
- GEA attention heads: 1, 2, 4, 8.

Observed:
- Performance degrades when GT layers exceed 2, attributed to overfitting.
- More than 4 GT heads may create redundant attention computation.
- GEA results vary non-monotonically with head count.
- Overall architecture is reasonably robust to appropriate hyperparameter changes.

## Interpretation and limitations
The paper concludes graph representation learning is well suited to customer–product interactions.

Returnformer is particularly effective for high-return customers.

Precision is lower than recall at threshold 0.5. The authors argue missing true return risk can be more costly than over-flagging some low-risk customers.

Limitations:
- Mainly static transaction/user/product information.
- Does not include factors such as reviews, seasonality and promotions.
- User preferences and product popularity are dynamic.
- Real-time data integration remains a challenge.
- Future work: dynamic data learning and improved interpretability.

## Important distinction for this project
The paper predicts **post-purchase keep/return behaviour** in an ASOS fashion dataset. Its results do not automatically transfer to India COD RTO prediction.

The paper's AUC 0.844 is the paper's result, not the project's GraphSAGE result.
