# Evaluation results

Human-readable leaderboards (newest first). Regenerate with `python -m data_harness.eval.summary`.

What the suites mean: **hard / large-data** validate the *design* (joins, multi-step, stateful, 100k-row handle work) and tend to saturate; **messy** and **WikiTableQuestions** are where models actually diverge.

## wikitablequestions · 2026-06-25
_125 runs · overall accuracy 81%_

| model | accuracy | avg turns | tokens | cost ($) |
|---|---|---|---|---|
| deepseek/deepseek-v4-flash | 96% | 4.5 | 228,476 | 0.0222 |
| qwen/qwen3.5-flash-02-23 | 88% | 6.5 | 464,862 | 0.0373 |
| openai/gpt-5-nano | 88% | 3.0 | 211,920 | 0.0400 |
| z-ai/glm-4.7-flash | 76% | 5.8 | 279,328 | 0.0247 |
| google/gemini-2.5-flash-lite | 56% | 3.2 | 166,521 | 0.0224 |

<sub>source: `wtq_20260625t215206.json`</sub>

## messy · 2026-06-25
_20 runs · overall accuracy 90%_

| model | accuracy | avg turns | tokens | cost ($) |
|---|---|---|---|---|
| deepseek/deepseek-v4-flash | 100% | 6.2 | 60,797 | 0.0060 |
| qwen/qwen3.5-flash-02-23 | 100% | 6.5 | 86,386 | 0.0068 |
| openai/gpt-5-nano | 100% | 2.8 | 28,951 | 0.0064 |
| google/gemini-2.5-flash-lite | 75% | 3.0 | 14,769 | 0.0020 |
| z-ai/glm-4.7-flash | 75% | 6.5 | 61,758 | 0.0051 |

<sub>source: `messy_20260625t195251.json`</sub>

## large · 2026-06-25
_25 runs · overall accuracy 100%_

| model | accuracy | avg turns | tokens | cost ($) |
|---|---|---|---|---|
| deepseek/deepseek-v4-flash | 100% | 2.6 | 16,383 | 0.0016 |
| qwen/qwen3.5-flash-02-23 | 100% | 3.6 | 26,883 | 0.0024 |
| openai/gpt-5-nano | 100% | 2.0 | 13,921 | 0.0026 |
| google/gemini-2.5-flash-lite | 100% | 3.6 | 17,492 | 0.0026 |
| z-ai/glm-4.7-flash | 100% | 3.8 | 22,804 | 0.0021 |

<sub>source: `large_20260625t085451.json`</sub>

## hard · 2026-06-25
_44 runs · overall accuracy 100%_

| model | accuracy | avg turns | tokens | cost ($) |
|---|---|---|---|---|
| deepseek/deepseek-v4-flash | 100% | 3.4 | 73,053 | 0.0071 |
| deepseek/deepseek-v4-pro | 100% | 2.5 | 52,463 | 0.0251 |
| qwen/qwen3.5-flash-02-23 | 100% | 3.9 | 92,131 | 0.0075 |
| anthropic/claude-haiku-4.5 | 100% | 3.1 | 81,868 | 0.1020 |

<sub>source: `hard_20260625t081400.json`</sub>
