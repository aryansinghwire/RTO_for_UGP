# Phase 0 Data Profile Report

```
==============================================================================
PHASE 0 DATA PROFILE  -  Returnformer / RTO Risk Engine
data_dir: /Users/aryan/RTO_for_UGP/data/synth_india_500k
==============================================================================

==============================================================================
1. FILE LOADING
==============================================================================
  [OK]       event_train      -> event_table_training.p  (237,078 rows x 3 cols, 6.4 MB)
  [OK]       event_test       -> event_table_testing.p  (262,922 rows x 3 cols, 8.5 MB)
  [OK]       customer_train   -> customer_nodes_training.p  (277,777 rows x 31 cols, 71.4 MB)
  [OK]       customer_test    -> customer_nodes_testing.p  (277,777 rows x 31 cols, 71.4 MB)
  [OK]       product_train    -> product_nodes_training.p  (40,000 rows x 42 cols, 14.9 MB)
  [OK]       product_test     -> product_nodes_testing.p  (40,000 rows x 42 cols, 14.9 MB)

==============================================================================
2. SCHEMA DETECTION
==============================================================================
  label                 : isReturned                     [OK]
  customer_key          : hash(customerId)               [OK]
  product_key           : hash(variantID)                [OK]
  event_customer_key    : hash(customerId)               [OK]
  event_product_key     : hash(variantID)                [OK]

==============================================================================
3. TABLE PROFILE - event_train
==============================================================================
  shape: 237,078 rows x 3 cols
  memory: 33.2 MB in RAM
  expected column count (PRD): 3  |  actual: 3

  dtypes:
    str         : 2 cols
    int64       : 1 cols

  missing values:
    none

  numeric summary (non-family columns, up to 12):
                mean    std  min  50%  max
    isReturned  0.28  0.449  0.0  0.0  1.0

  low-cardinality columns (<=10 uniques):
    isReturned                       (2 uniq): 0:170,727, 1:66,351

==============================================================================
3. TABLE PROFILE - customer_train
==============================================================================
  shape: 277,777 rows x 31 cols
  memory: 98.9 MB in RAM
  expected column count (PRD): 30  |  actual: 31

  dtypes:
    float64     : 16 cols
    int64       : 13 cols
    str         : 2 cols

  wide column families (>=3 cols sharing a stem):
    customerId_level_return_code_*          : 13 columns
    Country_*                               : 9 columns

  missing values:
    customerId_level_return_code_A          : 228,095 (82.11%)
    customerId_level_return_code_B          : 228,095 (82.11%)
    customerId_level_return_code_C          : 228,095 (82.11%)
    customerId_level_return_code_D          : 228,095 (82.11%)
    customerId_level_return_code_E          : 228,095 (82.11%)
    customerId_level_return_code_F          : 228,095 (82.11%)
    customerId_level_return_code_G          : 228,095 (82.11%)
    customerId_level_return_code_H          : 228,095 (82.11%)
    customerId_level_return_code_I          : 228,095 (82.11%)
    customerId_level_return_code_J          : 228,095 (82.11%)
    customerId_level_return_code_K          : 228,095 (82.11%)
    customerId_level_return_code_L          : 228,095 (82.11%)
    customerId_level_return_code_M          : 228,095 (82.11%)
    salesPerCustomer                        : 162,237 (58.41%)
    returnsPerCustomer                      : 162,237 (58.41%)
    customerReturnRate                      : 162,237 (58.41%)

  numeric summary (non-family columns, up to 12):
                                        mean     std     min     50%     max
    yearOfBirth                     1984.479  11.536  1965.0  1984.0  2004.0
    isMale                             0.550   0.497     0.0     1.0     1.0
    premier                            0.296   0.456     0.0     0.0     1.0
    salesPerCustomer                   2.052   1.164     1.0     2.0    10.0
    returnsPerCustomer                 0.574   0.785     0.0     0.0     7.0
    customerReturnRate                 0.299   0.393     0.0     0.0     1.0
    customerId_level_return_code_A     0.275   0.416     0.0     0.0     1.0
    customerId_level_return_code_B     0.085   0.260     0.0     0.0     1.0
    customerId_level_return_code_C     0.056   0.211     0.0     0.0     1.0
    customerId_level_return_code_D     0.042   0.187     0.0     0.0     1.0
    customerId_level_return_code_E     0.078   0.247     0.0     0.0     1.0
    customerId_level_return_code_F     0.032   0.162     0.0     0.0     1.0

  low-cardinality columns (<=10 uniques):
    isMale                           (2 uniq): 1:152,815, 0:124,962
    shippingCountry                  (3 uniq): Country_A:147,074, Country_B:75,218, Country_C:55,485
    premier                          (2 uniq): 0:195,616, 1:82,161
    salesPerCustomer                 (10 uniq): nan:162,237, 1.0:47,280, 2.0:34,733, 3.0:19,965, 4.0:9,055, 5.0:3,241
    returnsPerCustomer               (8 uniq): nan:162,237, 0.0:65,858, 1.0:36,878, 2.0:9,740, 3.0:2,401, 4.0:549
    customerId_level_return_code_D   (10 uniq): nan:228,095, 0.0:46,882, 1.0:1,573, 0.5:803, 0.3333333333333333:281, 0.25:101
    customerId_level_return_code_E   (9 uniq): nan:228,095, 0.0:44,630, 1.0:2,887, 0.5:1,484, 0.3333333333333333:473, 0.25:131
    customerId_level_return_code_F   (10 uniq): nan:228,095, 0.0:47,581, 1.0:1,160, 0.5:639, 0.3333333333333333:218, 0.25:60

==============================================================================
3. TABLE PROFILE - product_train
==============================================================================
  shape: 40,000 rows x 42 cols
  memory: 20.4 MB in RAM
  expected column count (PRD): 44  |  actual: 42

  dtypes:
    int64       : 21 cols
    float64     : 18 cols
    str         : 3 cols

  wide column families (>=3 cols sharing a stem):
    variantID_level_return_code_*           : 13 columns
    productType_*                           : 11 columns
    Brand_*                                 : 10 columns

  missing values:
    variantID_level_return_code_A           : 19,155 (47.89%)
    variantID_level_return_code_B           : 19,155 (47.89%)
    variantID_level_return_code_C           : 19,155 (47.89%)
    variantID_level_return_code_D           : 19,155 (47.89%)
    variantID_level_return_code_E           : 19,155 (47.89%)
    variantID_level_return_code_F           : 19,155 (47.89%)
    variantID_level_return_code_G           : 19,155 (47.89%)
    variantID_level_return_code_H           : 19,155 (47.89%)
    variantID_level_return_code_I           : 19,155 (47.89%)
    variantID_level_return_code_J           : 19,155 (47.89%)
    variantID_level_return_code_K           : 19,155 (47.89%)
    variantID_level_return_code_L           : 19,155 (47.89%)
    variantID_level_return_code_M           : 19,155 (47.89%)
    salesPerProduct                         : 9,702 (24.25%)
    returnsPerProduct                       : 9,702 (24.25%)
    productReturnRate                       : 9,702 (24.25%)

  numeric summary (non-family columns, up to 12):
                                      mean      std    min      50%       max
    avgGbpPrice                    854.464  510.393  199.0  735.000  7479.000
    avgDiscountValue                 0.183    0.098    0.0    0.172     0.564
    salesPerProduct                  7.825    8.419    1.0    5.000    93.000
    returnsPerProduct                2.190    3.001    0.0    1.000    53.000
    productReturnRate                0.277    0.279    0.0    0.231     1.000
    variantID_level_return_code_A    0.271    0.335    0.0    0.143     1.000
    variantID_level_return_code_B    0.083    0.208    0.0    0.000     1.000
    variantID_level_return_code_C    0.060    0.181    0.0    0.000     1.000
    variantID_level_return_code_D    0.042    0.149    0.0    0.000     1.000
    variantID_level_return_code_E    0.078    0.201    0.0    0.000     1.000
    variantID_level_return_code_F    0.032    0.133    0.0    0.000     1.000
    variantID_level_return_code_G    0.030    0.128    0.0    0.000     1.000

  low-cardinality columns (<=10 uniques):
    Brand_A                          (2 uniq): 0:35,992, 1:4,008
    Brand_B                          (2 uniq): 0:35,975, 1:4,025
    Brand_C                          (2 uniq): 0:35,980, 1:4,020
    Brand_D                          (2 uniq): 0:35,993, 1:4,007
    Brand_E                          (2 uniq): 0:35,960, 1:4,040
    Brand_F                          (2 uniq): 0:36,039, 1:3,961
    Brand_G                          (2 uniq): 0:36,002, 1:3,998
    Brand_I                          (2 uniq): 0:36,002, 1:3,998

==============================================================================
4. LABEL BALANCE (isReturned)
==============================================================================
  event_train: returned(1)=66,351  kept(0)=170,727  pos:neg = 0.39:1  (positive share 28.0%)
  event_test: returned(1)=87,638  kept(0)=175,284  pos:neg = 0.50:1  (positive share 33.3%)

  paper reference pos:neg ratio ~= 1.2:1 (for sanity comparison only)

==============================================================================
5. GRAPH JOIN-KEY INTEGRITY  (critical)
==============================================================================
  event_train   -> customer_train   [customer]: 0 unresolved edges (0.00%)
  event_test    -> customer_test    [customer]: 0 unresolved edges (0.00%)
  event_train   -> product_train    [product]: 0 unresolved edges (0.00%)
  event_test    -> product_test     [product]: 0 unresolved edges (0.00%)

  (Every edge endpoint should resolve to a node row. Non-zero orphan
   rates mean edges that reference a customer/product with no feature row.)

==============================================================================
6. TRAIN/TEST ENTITY OVERLAP  (cold-start signal)
==============================================================================
  customers: 277,777 in train, 277,777 in test, 0 test-only (0.0% cold-start)
  products: 40,000 in train, 40,000 in test, 0 test-only (0.0% cold-start)

  (Test entities absent from train have no graph history -> these are the
   orders the baseline fallback model must score. This % sizes that need.)

==============================================================================
7. RETURN-REASON PROFILE SANITY
==============================================================================
  customer_train: family 'customerId_level_return_code_*' (13 numeric cols) row-sum mean=0.179, share of rows summing ~1.0 = 17.9%
  product_train: family 'variantID_level_return_code_*' (13 numeric cols) row-sum mean=0.521, share of rows summing ~1.0 = 52.1%

  (Reason-code columns are proportions of a customer's/product's past
   returns; rows should sum to ~1 where any returns exist.)

==============================================================================
8. SANITY vs PAPER-REPORTED SCALE
==============================================================================
  event_train rows: 237,078  (paper: 939,537)
  event_test  rows: 262,922  (paper: 858,526)
  unique customers (train+test): 277,777  (paper: 1,084,504)
  unique variants  (train+test): 40,000  (paper: 338,076)

  (Small deviations are fine - the paper's counts are post-cleaning.
   Large gaps mean a different export or an extra preprocessing step.)

==============================================================================
DONE
==============================================================================
  Review the join-integrity and cold-start sections first - they gate
  Phase 1. If both look clean, you're clear to build the baseline.
```
