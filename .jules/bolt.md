## 2024-05-23 - [Pandas Iteration Bottleneck]
**Learning:** Iterating over DataFrame rows with `df.iloc[i]` or `iterrows()` to construct dictionaries is extremely slow (O(N) with high constant factor due to Series creation).
**Action:** Always vectorize column extraction to lists/arrays first (e.g. `df['col'].tolist()`) and `zip` them for iteration. This yielded a ~130x speedup in `src/data.py`.
