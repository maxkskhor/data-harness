"""Zero-config entry points: ``ask()``, ``Chat``, and ``SmartFrame``.

These are the headline conveniences. ``ask(df, "...")`` is the lowest-friction
way to query data: it resolves a provider from the environment, loads the data
into a session cache as handles, runs the agent, and returns a `RunResult`
(which renders richly in notebooks).

``Chat`` keeps a session alive for follow-up questions; ``SmartFrame`` is a
pandasai-style wrapper over a single frame. Neither mutates global state.
"""

from __future__ import annotations

import importlib.util
import os
from typing import TYPE_CHECKING, Any

from data_harness.agent import Agent
from data_harness.io import to_handles
from data_harness.result import RunResult

if TYPE_CHECKING:
    from data_harness.providers.base import ProviderAdapter

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"

_DEFAULT_SYSTEM = (
    "You are a senior data analyst. You answer questions about the user's data "
    "by writing Python in the python_interpreter tool.\n\n"
    "Guidelines:\n"
    "- The user's data is preloaded as cache handles (named variables). Use them "
    "directly; call list_variables if you need to see what is available.\n"
    "- Inspect data with print(...) before computing.\n"
    "- To make a chart, use matplotlib (import matplotlib.pyplot as plt) and build "
    "the figure; it is captured automatically. Do not call plt.show().\n"
    "- You MUST call answer(value) inside the interpreter with your final result "
    "(a number, a DataFrame, etc.) before you finish — this is how the caller "
    "receives the structured result. Do this even if you also explain in prose.\n"
    "- If a sql_query tool is available, you may use SQL over the data handles.\n"
    "- Finish with a short, clear written summary."
)

_OPENAI_PREFIXES = ("gpt", "o1", "o3", "o4", "chatgpt")


def _is_openai_model(model: str) -> bool:
    return model.lower().startswith(_OPENAI_PREFIXES)


def resolve_adapter(model: str | None = None) -> ProviderAdapter:
    """Resolve a `ProviderAdapter` from an explicit model or the environment.

    With no ``model``, prefers ``ANTHROPIC_API_KEY``, then ``OPENAI_API_KEY``,
    then ``OPENROUTER_API_KEY``, then ``DEEPSEEK_API_KEY``. With a ``model``,
    routes by name: a ``provider/model`` id (containing ``/``) goes to OpenRouter,
    ``deepseek*`` to DeepSeek's direct API, ``gpt*``/``o*`` to OpenAI, otherwise
    Anthropic.

    Raises:
        RuntimeError: If no provider can be resolved (no key, no model).
    """
    if model is not None:
        if "/" in model:
            return _make_openrouter(model)
        if model.startswith("deepseek"):
            return _make_deepseek(model)
        if _is_openai_model(model):
            return _make_openai(model)
        from data_harness.providers.anthropic import AnthropicAdapter

        return AnthropicAdapter(model=model)

    if os.environ.get("ANTHROPIC_API_KEY"):
        from data_harness.providers.anthropic import AnthropicAdapter

        return AnthropicAdapter(model=DEFAULT_ANTHROPIC_MODEL)
    if os.environ.get("OPENAI_API_KEY"):
        return _make_openai(DEFAULT_OPENAI_MODEL)
    if os.environ.get("OPENROUTER_API_KEY"):
        return _make_openrouter(DEFAULT_OPENROUTER_MODEL)
    if os.environ.get("DEEPSEEK_API_KEY"):
        return _make_deepseek(DEFAULT_DEEPSEEK_MODEL)

    raise RuntimeError(
        "No provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "OPENROUTER_API_KEY, or DEEPSEEK_API_KEY, or pass an explicit "
        "adapter=... / model=... to ask()/Chat()."
    )


def _make_openai(model: str) -> ProviderAdapter:
    try:
        from data_harness.providers.openai import OpenAIAdapter
    except ImportError as exc:  # pragma: no cover - exercised via install matrix
        raise RuntimeError(
            "OpenAI support requires the 'openai' extra: pip install "
            "'data-harness[openai]'."
        ) from exc
    return OpenAIAdapter(model=model)


def _make_openrouter(model: str) -> ProviderAdapter:
    try:
        from data_harness.providers.openai import OpenRouterAdapter
    except ImportError as exc:  # pragma: no cover - exercised via install matrix
        raise RuntimeError(
            "OpenRouter support requires the 'openai' extra: pip install "
            "'data-harness[openai]'."
        ) from exc
    return OpenRouterAdapter(model=model)


def _make_deepseek(model: str) -> ProviderAdapter:
    try:
        from data_harness.providers.openai import DeepSeekAdapter
    except ImportError as exc:  # pragma: no cover - exercised via install matrix
        raise RuntimeError(
            "DeepSeek support requires the 'openai' extra: pip install "
            "'data-harness[openai]'."
        ) from exc
    return DeepSeekAdapter(model=model)


def _build_agent(
    handles: dict[str, Any],
    *,
    adapter: ProviderAdapter | None,
    model: str | None,
    system: str | None,
    max_turns: int,
    run_dir: str | None,
    semantics: dict[str, dict] | None,
    sql: bool | None,
) -> Agent:
    agent = Agent(
        adapter=adapter if adapter is not None else resolve_adapter(model),
        system=system if system is not None else _DEFAULT_SYSTEM,
        max_turns=max_turns,
        run_dir=run_dir,
    )
    sem = semantics or {}
    for name, value in handles.items():
        agent.cache.put(name, value, semantics=sem.get(name))
    if sql is None:
        sql = importlib.util.find_spec("duckdb") is not None
    if sql:
        agent.enable_sql()
    return agent


def _handles_preamble(agent: Agent) -> str:
    listing = agent.cache.list_handles()
    if not listing:
        return ""
    lines = "\n".join(f"- {name}: {snap}" for name, snap in listing.items())
    return f"\n\nAvailable data handles:\n{lines}"


def ask(
    data: Any,
    question: str,
    *,
    model: str | None = None,
    adapter: ProviderAdapter | None = None,
    system: str | None = None,
    semantics: dict[str, dict] | None = None,
    sql: bool | None = None,
    max_turns: int = 12,
    run_dir: str | None = None,
) -> RunResult:
    """Ask a one-shot natural-language question about ``data``.

    Args:
        data: A DataFrame, a ``{name: value}`` mapping, a file path, or a list
            of file paths. Loaded into the session cache as handles.
        question: The natural-language question.
        model: Optional model id; routes to the matching provider. Ignored if
            ``adapter`` is given.
        adapter: Explicit provider adapter, overriding ``model``.
        system: Override the default analyst system prompt.
        semantics: Optional ``{handle: {...}}`` domain context folded into
            snapshots.
        sql: Enable the ``sql_query`` tool. ``None`` auto-enables it when DuckDB
            is installed.
        max_turns: Hard cap on provider turns.
        run_dir: Directory for JSONL logs and chart artefacts.

    Returns:
        A `RunResult`. Use ``.text`` for prose, ``.value`` for the structured
        answer, and ``.charts`` for rendered charts.
    """
    handles = to_handles(data)
    agent = _build_agent(
        handles,
        adapter=adapter,
        model=model,
        system=system,
        max_turns=max_turns,
        run_dir=run_dir,
        semantics=semantics,
        sql=sql,
    )
    return agent.run_result(question + _handles_preamble(agent))


class Chat:
    """A stateful conversation over a dataset.

    Unlike `ask`, a `Chat` keeps one message history and cache alive so
    follow-up questions can build on earlier turns.

    Example::

        chat = Chat(sales_df)
        chat.ask("What was total revenue?")
        chat.ask("Which month was highest?")  # remembers context
    """

    def __init__(
        self,
        data: Any,
        *,
        model: str | None = None,
        adapter: ProviderAdapter | None = None,
        system: str | None = None,
        semantics: dict[str, dict] | None = None,
        sql: bool | None = None,
        max_turns: int = 12,
        run_dir: str | None = None,
    ) -> None:
        handles = to_handles(data)
        self._agent = _build_agent(
            handles,
            adapter=adapter,
            model=model,
            system=system,
            max_turns=max_turns,
            run_dir=run_dir,
            semantics=semantics,
            sql=sql,
        )
        self._session = self._agent.session()
        self._first = True

    def ask(self, question: str) -> RunResult:
        """Ask a follow-up question and return its `RunResult`."""
        if self._first:
            question = question + _handles_preamble(self._agent)
            self._first = False
        return self._session.ask_result(question)

    @property
    def session(self):
        """The underlying `AgentSession` (cache, history, run file)."""
        return self._session


class SmartFrame:
    """pandasai-style wrapper over a single DataFrame.

    Example::

        SmartFrame(df).chat("plot revenue by month")
    """

    def __init__(self, df: Any, **kwargs: Any) -> None:
        self._chat = Chat(df, **kwargs)

    def chat(self, question: str) -> RunResult:
        """Ask a question about the wrapped frame; returns a `RunResult`."""
        return self._chat.ask(question)
