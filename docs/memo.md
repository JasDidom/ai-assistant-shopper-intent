# Do AI assistants listen to what the shopper wants?

**A two-page memo on brand recommendations from Claude, GPT and Gemini**
Jass Di Domenico · jass.didomenico@gmail.com · November 2026

## Question

When a shopper tells an AI assistant what they care about (a low price, premium quality, sustainability, being a first-time buyer), does the assistant change which brands it recommends? Or does most of the variation come from how the question happens to be worded? This matters for generative-engine "share of model": if the wording drives the brand list, measured visibility is mostly noise.

## Design

- **Categories (3):** running shoes, noise-cancelling headphones, CRM software for a small business.
- **Intents (5):** neutral, budget, premium, sustainable, novice.
- **Wordings:** 4 per intent, the same across categories, giving 60 prompts.
- **Models (3):** `claude-opus-5-5`, `gpt-6.1-sol` and `gemini-3.8-flash`, called through the API with default settings, no system prompt, no web search and no memory.
- **Repeats:** 10 per prompt, giving **1,800 answers**.
- **Predictions:** written down before data collection, not formally registered (README, 2026-11-01), and a 36-answer pilot gated the paid run.

Brands and stances (recommended, mentioned, warned against) were extracted with a fixed JSON schema. Every brand had to come with a verbatim quote that code checked against the answer.

## Results

**1. Intent moves the brand list 1.5–3× more than wording does, for every model and category.** Distances are weighted Jaccard distances between brand-visibility vectors. The p-value comes from a permutation test with 2,000 relabelings.

| | Same intent, other wording | Different intent | Ratio |
|---|---|---|---|
| Running shoes | 0.17–0.41 | 0.49–0.67 | 1.7–3.0 |
| Headphones | 0.21–0.28 | 0.59–0.70 | 2.3–3.0 |
| CRM | 0.32–0.43 | 0.52–0.66 | 1.5–1.7 |

The ranges are across the three models, and p < 0.001 in all 9 model-and-category cells. The effect is weakest for CRM, where wording alone already moves the list a lot.

**What changes is the tail, not the core.** The core brands survive almost any intent: Sony and Bose; HubSpot and Zoho; Brooks and ASICS. Intent mainly swaps the brands below them:

- *Sustainable* headphones bring in Fairphone (100% of answers), House of Marley and Urbanista.
- *Sustainable* shoes put Veja (94%) and Allbirds on top.
- *Budget* headphones put Anker/Soundcore first (100%), followed by EarFun and 1MORE.
- *Premium* CRM brings in Salesforce, which rises from 38% of neutral answers to 92%.
- *Novice* mostly returns the neutral list.

**2. Repeats are fairly stable but rarely identical.** Asking the same prompt twice gives brand lists that overlap by 0.71–0.80 on average. Exactly identical lists come up in 7% of repeat pairs for Gemini, 12% for Claude and 21% for GPT.

**3. GPT concentrates its recommendations most.** The top 3 brands take 56–86% of GPT's recommendations, against 34–67% for Claude. "Novice" prompts are the most concentrated for all three models, at 53–86%.

**4. The models agree on 0.65–0.74 of their top-5 brands.** GPT agrees most with each of the others (0.74); Claude and Gemini agree least (0.65).

## Predictions vs. outcome

| Prediction (written before the data) | Outcome |
|---|---|
| Intent > wording for all three models | **Supported.** 9/9 cells, p < 0.001 |
| Identical repeat lists under 5% | **Not supported.** 7–21% |
| Mean repeat overlap above 0.5 | **Supported.** 0.71–0.80 |
| Top 3 brands take at least 50% in neutral and novice | **Partly supported.** True for novice in all cells; not for Claude's neutral shoes (39%) or CRM (34%) |
| Models agree least on CRM | **Not yet tested** by category |

## Data quality and one deviation

All 1,800 answers were collected from the requested model versions. There were no refusals and no answers lost permanently, and all 1,800 coded answers passed the quote check.

The first coding audit found 85/100 answers correct. GPT often lists options in a table and then names a favourite, and the coder marked the other table rows as "mentioned". The rule was clarified, all 1,800 answers were re-coded, and a **fresh** random sample was drawn. Four independent AI reviewers then judged 100/100 correct, and a human hand-check of 29 of those answers found 29/29 correct.

## Limitations

- API models without web search or memory are not the consumer apps.
- The study covers three categories and English prompts only.
- The three models sit at different price tiers.
- Model versions change over time, so the results are a snapshot of November 2026.
- Coding is automated. Its accuracy is measured, not assumed.

## What I'd do next

- Test whether intent effects survive web-search grounding.
- Add non-English prompts, starting with Italian and German.
- Measure intent at the level of brand *rank*, not just set membership, which is closer to recommender-systems work on predicted intent.

Code, prompts, raw answers and the analysis are in the repository.
