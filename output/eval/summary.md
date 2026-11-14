# California look-back: accuracy and cost (Nov 3, 2026 propositions)

Each card: Analyst writes -> Critic (gpt-6-luna) reviews -> up to 2 rewrites. A separate Grader then scores the final card against the official voter guide (Legislative Analyst = answer key).

## Writer: gpt-6-astra

| Prop | Verified | Turing (Yes/No) | Rewrites | Claims | Supported | Unsupported | Contradicted | Yes/No/Fiscal correct | Argument coverage | Input tok | Cached | Output tok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 4/4 | 0 | 11 | 11 | 0 | 0 | 3/3 | 1.0 | 19,242 | 7,963 | 3,303 |
| 3 | yes | 4/4 | 1 | 11 | 11 | 0 | 0 | 3/3 | 1.0 | 28,669 | 11,048 | 6,658 |
| 5 | yes | 4/4 | 0 | 11 | 11 | 0 | 0 | 3/3 | 0.8 | 16,056 | 4,971 | 3,108 |
| 39 | yes | 4/4 | 0 | 12 | 12 | 0 | 0 | 3/3 | 0.9 | 15,923 | 4,971 | 3,126 |
| 41 | no | 4/4 | 2 | 12 | 12 | 0 | 0 | 3/3 | 0.8 | 45,169 | 18,935 | 12,278 |
| 45 | yes | 4/4 | 0 | 12 | 12 | 0 | 0 | 3/3 | 0.8 | 17,089 | 4,971 | 3,705 |

**Averages:** {"props": 6, "verified": 5, "fidelity": 1.0, "contradicted": 0, "effects_correct": "18/18", "coverage": 0.883, "rewrites": 0.5, "turing_min_avg": 4, "input_per_prop": 23691, "cached_per_prop": 8810, "output_per_prop": 5363, "seconds_per_prop": 70.6}

## Writer: gpt-6-luna

| Prop | Verified | Turing (Yes/No) | Rewrites | Claims | Supported | Unsupported | Contradicted | Yes/No/Fiscal correct | Argument coverage | Input tok | Cached | Output tok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 4/4 | 2 | 9 | 8 | 0 | 1 | 3/3 | 0.8 | 59,208 | 30,314 | 12,524 |
| 3 | no | 4/3 | 2 | 13 | 13 | 0 | 0 | 3/3 | 0.667 | 47,091 | 18,938 | 14,472 |
| 39 | no | 4/4 | 2 | 13 | 13 | 0 | 0 | 3/3 | 0.8 | 49,459 | 19,427 | 14,776 |

**Averages:** {"props": 3, "verified": 1, "fidelity": 0.963, "contradicted": 1, "effects_correct": "9/9", "coverage": 0.756, "rewrites": 2, "turing_min_avg": 3.667, "input_per_prop": 51919, "cached_per_prop": 22893, "output_per_prop": 13924, "seconds_per_prop": 128.8}

## Writer comparison (same props only)

| Writer | Props | Fidelity | Contradicted | Effects correct | Coverage | Rewrites | Min Turing | Input/prop | Cached/prop | Output/prop |
|---|---|---|---|---|---|---|---|---|---|---|
| gpt-6-astra | ['1', '3', '39'] | 1.0 | 0 | 9/9 | 0.967 | 0.333 | 4 | 21,278 | 7,994 | 4,362 |
| gpt-6-luna | ['1', '3', '39'] | 0.963 | 1 | 9/9 | 0.756 | 2 | 3.667 | 51,919 | 22,893 | 13,924 |

## Prompt change: each side's top 3 official points (same 6 props, same models)

| Metric | Before | After |
|---|---|---|
| Steelmen verified (of 6) | 5 | 5 |
| Claims supported | 0.987 | 1.0 |
| Claims contradicted | 1 | 0 |
| Yes/No/cost correct | 18/18 | 18/18 |
| Official argument points covered | 0.756 | 0.883 |
| Rewrites per prop | 0.667 | 0.5 |
| Lowest Turing score (avg) | 3.833 | 4 |
| Input tokens / prop | 25428 | 23691 |
| Cached tokens / prop | 9322 | 8810 |
| Output tokens / prop | 5411 | 5363 |
