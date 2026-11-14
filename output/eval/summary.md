# California look-back: accuracy and cost (Nov 3, 2026 propositions)

Each card: Analyst writes -> Critic (gpt-6-luna) reviews -> up to 2 rewrites. A separate Grader then scores the final card against the official voter guide (Legislative Analyst = answer key).

## Writer: gpt-6-astra

| Prop | Verified | Turing (Yes/No) | Rewrites | Claims | Supported | Unsupported | Contradicted | Yes/No/Fiscal correct | Argument coverage | Input tok | Cached | Output tok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 4/4 | 1 | 11 | 11 | 0 | 0 | 3/3 | 0.8 | 30,834 | 12,857 | 5,619 |
| 3 | yes | 4/4 | 0 | 11 | 11 | 0 | 0 | 3/3 | 0.556 | 14,380 | 4,571 | 3,712 |
| 5 | yes | 4/4 | 0 | 11 | 11 | 0 | 0 | 3/3 | 0.778 | 15,566 | 4,571 | 2,787 |
| 39 | no | 3/4 | 2 | 13 | 12 | 0 | 1 | 3/3 | 0.9 | 46,626 | 18,822 | 10,518 |
| 41 | yes | 4/4 | 1 | 12 | 12 | 0 | 0 | 3/3 | 0.7 | 28,614 | 10,538 | 6,735 |
| 45 | yes | 4/4 | 0 | 12 | 12 | 0 | 0 | 3/3 | 0.8 | 16,545 | 4,571 | 3,093 |

**Averages:** {"props": 6, "verified": 5, "fidelity": 0.987, "contradicted": 1, "effects_correct": "18/18", "coverage": 0.756, "rewrites": 0.667, "turing_min_avg": 3.833, "input_per_prop": 25428, "cached_per_prop": 9322, "output_per_prop": 5411, "seconds_per_prop": 73.3}

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
| gpt-6-astra | ['1', '3', '39'] | 0.974 | 1 | 9/9 | 0.752 | 1 | 3.667 | 30,613 | 12,083 | 6,616 |
| gpt-6-luna | ['1', '3', '39'] | 0.963 | 1 | 9/9 | 0.756 | 2 | 3.667 | 51,919 | 22,893 | 13,924 |
