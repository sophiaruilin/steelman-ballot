# California look-back: accuracy and cost (Nov 3, 2026 propositions)

Each card: Analyst (gpt-6-astra) writes -> Critic (gpt-6-luna) reviews -> up to 2 rewrites. A separate Grader (gpt-6-astra) scores the final card against the official voter guide, with the Legislative Analyst as the answer key. Current cards are graded twice and averaged to smooth grader noise.

## Current cards (v3)

| Prop | Verified | Turing (Yes/No) | Rewrites | Claims supported | Contradicted | Yes/No/cost correct | #1 point = headline | Top-3 covered | All covered | Reading grade | Input tok | Cached | Output tok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 4/4 | 0 | 100% | 0.0 | 3.0/3 | 100% | 100% | 80% | 8.4 | 14,939 | 2,980 | 3,314 |
| 3 | no | 4/3 | 2 | 100% | 0.0 | 3.0/3 | 100% | 83% | 78% | 7.2 | 46,622 | 20,408 | 11,436 |
| 5 | yes | 4/4 | 1 | 100% | 0.0 | 3.0/3 | 100% | 83% | 76% | 9.0 | 33,327 | 12,956 | 6,498 |
| 39 | yes | 4/4 | 1 | 100% | 0.0 | 3.0/3 | 100% | 100% | 100% | 10.4 | 32,881 | 12,828 | 8,285 |
| 41 | yes | 4/4 | 2 | 97% | 0.0 | 3.0/3 | 100% | 83% | 86% | 8.9 | 48,323 | 20,863 | 11,956 |
| 45 | yes | 4/4 | 0 | 100% | 0.0 | 3.0/3 | 100% | 100% | 89% | 10.0 | 18,334 | 5,853 | 3,538 |

## Targets

| Metric | Target | Current |
|---|---|---|
| Claims supported by sources | >= 99%, 0 contradicted | 100%, 0 contradicted |
| Yes / No / cost correct | 100% | 18/18 |
| Each side's #1 point is its headline | 100% | 100% |
| Each side's top-3 points covered (on the merits) | >= 95% | 92% |
| All points on the merits covered | 85-90% | 85% |
| Steelmen verified by the Critic | >= 85-90% | 5/6 |
| Reading level of what voters see first | about grade 8-9 | 8.983 |

## How the card design evolved (same 6 props, same models)

| Metric | v1: pros/cons steelmen | v2: + each side's top 3 official points | v3: What changes + one headline per side, on the merits only |
|---|---|---|---|
| Steelmen verified (of 6) | 5 | 5 | 5 |
| Claims supported | 1.0 | 1.0 | 0.995 |
| Claims contradicted | 0 | 0 | 0 |
| Yes/No/cost correct | 18/18 | 18/18 | 18/18 |
| #1 point is the headline | - | - | 1.0 |
| Top-3 points covered | 0.861 | 0.889 | 0.916 |
| All points covered | 0.804 | 0.855 | 0.848 |
| Rewrites per prop | 0.667 | 0.5 | 1 |
| Lowest Turing score (avg) | 3.833 | 4 | 3.833 |
| Reading grade | - | - | 8.983 |
| Input tokens / prop | 25428 | 23691 | 32404 |
| Cached tokens / prop | 9322 | 8810 | 12648 |
| Output tokens / prop | 5411 | 5363 | 7504 |
| Seconds / prop | 73.3 | 70.6 | 87.9 |

Note: v1 and v2 counted all official points; v3 counts only points about the change, setting aside arguments about motives or funders by design.

## Writer model comparison (v1 cards, props 1, 3, 39)

| Writer | Verified | Claims supported | Rewrites | Input/prop | Output/prop |
|---|---|---|---|---|---|
| gpt-6-astra | 2/3 | 100% | 1 | 30,613 | 6,616 |
| gpt-6-luna | 1/3 | 96% | 2 | 51,919 | 13,924 |
