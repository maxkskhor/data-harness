"""Regenerate evals/results/SUMMARY.md from the committed JSON results.

    python evals/summarize.py

(Thin wrapper over ``data_harness.eval.summary``.)
"""

from data_harness.eval.summary import main

if __name__ == "__main__":
    main()
