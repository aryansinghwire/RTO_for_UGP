import pandas as pd
D = "/Users/aryan/RTO_for_UGP/data"
ev = pd.read_pickle(f"{D}/event_table_training.p")
pr = pd.read_pickle(f"{D}/product_nodes_training.p")

# 1. Do node tables only contain entities WITH returns?
print("min returnsPerProduct:", pr["returnsPerProduct"].min())

# 2. Are orphan variants genuinely absent (not a hash mismatch)?
orphan_ids = set(ev["hash(variantID)"]) - set(pr["hash(variantID)"])
print("distinct orphan variantIDs:", len(orphan_ids))

# 3. Are orphaned edges disproportionately KEPT (label=0)?
ev["orphan"] = ~ev["hash(variantID)"].isin(set(pr["hash(variantID)"]))
print(ev.groupby("orphan")["isReturned"].mean())   # return rate by orphan status

# 4. List the real reason-code columns (to resolve the duplicate D)
print([c for c in pr.columns if "return_code" in c])