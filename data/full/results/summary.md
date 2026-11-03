# Results

**Status: READY** - all results-gate checks passed.

Accepted codings: 1800 of 1800 planned units. Coding accuracy, AI audit (independent model reviewers): 100% of 100 randomly sampled answers. Human hand-check: 100% of 29 answers.

## 1. Does intent move the brand list more than wording does?

Distance 0 = identical brand visibility, 1 = no overlap. p = share of 2,000 random relabelings with a gap at least as large (small p: intent effect unlikely to be wording noise).

| model | category | same intent, other wording | different intent | ratio | p |
|---|---|---|---|---|---|
| claude | crm | 0.32 | 0.53 | 1.69 | 0.000 |
| claude | headphones | 0.21 | 0.59 | 2.86 | 0.000 |
| claude | running_shoes | 0.17 | 0.49 | 2.98 | 0.000 |
| gemini | crm | 0.43 | 0.66 | 1.56 | 0.000 |
| gemini | headphones | 0.23 | 0.70 | 2.99 | 0.000 |
| gemini | running_shoes | 0.26 | 0.63 | 2.42 | 0.000 |
| gpt | crm | 0.34 | 0.52 | 1.54 | 0.000 |
| gpt | headphones | 0.28 | 0.66 | 2.32 | 0.000 |
| gpt | running_shoes | 0.41 | 0.67 | 1.66 | 0.000 |

## 2. Stability when the same prompt is repeated

| model | mean overlap | identical brand lists |
|---|---|---|
| claude | 0.80 | 11.8% |
| gemini | 0.71 | 7.5% |
| gpt | 0.76 | 20.6% |

## 3. Concentration: share of mentions going to the top 3 brands

| model | category | neutral | budget | premium | sustainable | novice |
|---|---|---|---|---|---|---|
| claude | running_shoes | 39% | 46% | 34% | 35% | 53% |
| claude | headphones | 59% | 54% | 54% | 50% | 67% |
| claude | crm | 34% | 36% | 41% | 41% | 54% |
| gemini | running_shoes | 51% | 51% | 49% | 47% | 72% |
| gemini | headphones | 65% | 72% | 53% | 56% | 76% |
| gemini | crm | 55% | 50% | 49% | 36% | 72% |
| gpt | running_shoes | 58% | 56% | 59% | 60% | 69% |
| gpt | headphones | 68% | 85% | 67% | 85% | 86% |
| gpt | crm | 73% | 62% | 64% | 70% | 80% |

## 4. Agreement between models (overlap of top-5 brands, averaged)

| pair | overlap |
|---|---|
| claude vs gemini | 0.65 |
| claude vs gpt | 0.74 |
| gemini vs gpt | 0.74 |

## Data quality

| model | accepted answers | refusals | short (flagged) | failed permanently | coding failed gate | no brand recommended |
|---|---|---|---|---|---|---|
| claude | 600 | 0 | 0 | 0 | 0 | 0 |
| gemini | 600 | 0 | 0 | 0 | 0 | 0 |
| gpt | 600 | 0 | 0 | 0 | 0 | 9 |
