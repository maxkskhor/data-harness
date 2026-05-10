# dataact — Deferred Work (v2 roadmap)

Everything here was explicitly out-of-scope for v0.1.0 or surfaced as a desired improvement after the initial release.
Items are grouped by theme and ordered roughly by expected value vs. effort.

---

## 1. Python version support

**Current:** `requires-python = ">=3.12"` (pyproject.toml)

**Goal:** support Python 3.10+.

What needs changing:
- Audit every use of `match`/`case` (structural pattern matching, 3.10+) and `|` union type syntax in annotations (3.10+ at runtime; 3.9 with `from __future__ import annotations`).
- Replace any 3.12-specific stdlib additions (`tomllib`, `itertools.batched`, etc.) with backports or equivalents.
- Update `pyproject.toml` to `requires-python = ">=3.10"` and add a `py310` tox/CI matrix entry.
- Verify the test suite passes on 3.10 and 3.11 (uv workspace matrix or `tox`).

Notes: the main cost is annotation syntax; the logic itself is not deeply 3.12-dependent.

---

## 2. Additional provider adapters

**Current:** only `AnthropicAdapter`.

**Goal:** add `OpenAIAdapter` as the next provider. Most developers will reach for OpenAI first, so the framework should show the common path as well as demonstrate that the `ProviderAdapter` ABC is actually provider-neutral.

Design notes:
- `OpenAIAdapter.chat()` maps OpenAI's response format to `NormalizedResponse`.
- Cache-control annotation is Anthropic-specific — `OpenAIAdapter` is a no-op there.
- Tests for the new adapter follow the same pattern as `tests/test_providers.py`.

---

## 3. SDK ergonomics / simple `Agent` builder

**Current:** examples wire the harness internals directly: cache, connector registry, wrapped connector specs, interpreter tool, variables tool, planner tools, subagent factory, reminder hook, and `Harness` construction.

**Goal:** add a small high-level API for the common path so `dataact` is usable as a library without hiding the harness design. The explicit low-level API should remain available for users who want to customise the internals. The future `learn-dataact` repo will carry the smaller teaching version.

Detailed draft: `PLAN_SDK.md`.

---

## 4. CI / GitHub Actions

**Current:** no CI configuration.

**Goal:** a minimal `.github/workflows/ci.yml` that:
- Runs `uv run pytest tests/ -m "not live"` on push/PR.
- Tests against Python 3.10, 3.11, 3.12 (once item 1 is done).
- Optionally runs smoke tests nightly using a repository secret for `ANTHROPIC_API_KEY`.

---

## 5. Published package (PyPI)

**Current:** local install only (`uv sync`).

**Goal:** publish `dataact` to PyPI so users can `pip install dataact` or `uv add dataact`.

Prerequisites: items 1 (broad Python support), 3 (SDK ergonomics), and 4 (CI) should land first.
Steps: add a release workflow, pin a stable version tag, run `uv build && uv publish`.
