# Results

**Status: NOT READY** - do not cite these numbers yet:
- extraction accuracy not hand-checked yet

Accepted codings: 1800 of 1800 planned units. Extraction not yet hand-checked (fill handcheck.csv).

## 1. Does intent move the brand list more than wording does?

Distance 0 = identical brand visibility, 1 = no overlap. p = share of 2,000 random relabelings with a gap at least as large (small p: intent effect unlikely to be wording noise).

| model | category | same intent, other wording | different intent | ratio | p |
|---|---|---|---|---|---|
| claude | crm | 0.35 | 0.56 | 1.60 | 0.000 |
| claude | headphones | 0.22 | 0.64 | 2.84 | 0.000 |
| claude | running_shoes | 0.17 | 0.50 | 3.00 | 0.000 |
| gemini | crm | 0.44 | 0.67 | 1.52 | 0.000 |
| gemini | headphones | 0.25 | 0.72 | 2.82 | 0.000 |
| gemini | running_shoes | 0.29 | 0.64 | 2.20 | 0.000 |
| gpt | crm | 0.33 | 0.50 | 1.49 | 0.000 |
| gpt | headphones | 0.34 | 0.69 | 2.02 | 0.000 |
| gpt | running_shoes | 0.42 | 0.67 | 1.62 | 0.000 |

## 2. Stability when the same prompt is repeated

| model | mean overlap | identical brand lists |
|---|---|---|
| claude | 0.76 | 7.3% |
| gemini | 0.70 | 7.2% |
| gpt | 0.72 | 19.3% |

## 3. Concentration: share of mentions going to the top 3 brands

| model | category | neutral | budget | premium | sustainable | novice |
|---|---|---|---|---|---|---|
| claude | running_shoes | 39% | 46% | 35% | 37% | 53% |
| claude | headphones | 59% | 48% | 55% | 57% | 63% |
| claude | crm | 34% | 37% | 41% | 44% | 54% |
| gemini | running_shoes | 52% | 49% | 49% | 44% | 70% |
| gemini | headphones | 65% | 72% | 53% | 59% | 76% |
| gemini | crm | 55% | 49% | 49% | 36% | 72% |
| gpt | running_shoes | 58% | 57% | 59% | 60% | 69% |
| gpt | headphones | 65% | 71% | 70% | 89% | 90% |
| gpt | crm | 85% | 76% | 67% | 68% | 82% |

## 4. Agreement between models (overlap of top-5 brands, averaged)

| pair | overlap |
|---|---|
| claude vs gemini | 0.62 |
| claude vs gpt | 0.71 |
| gemini vs gpt | 0.59 |

## Data quality

| model | accepted answers | refusals | short (flagged) | failed permanently | coding failed gate | no brand recommended |
|---|---|---|---|---|---|---|
| claude | 600 | 0 | 0 | 0 | 0 | 0 |
| gemini | 600 | 0 | 0 | 0 | 0 | 0 |
| gpt | 600 | 0 | 0 | 0 | 0 | 9 |
