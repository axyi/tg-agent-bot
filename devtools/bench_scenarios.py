"""The twelve frozen benchmark scenarios of spec-v1.3 Appendix C.

REQ-V13-BEN-08/09: the catalog is data only — ids, Russian user turns and the
checks that decide whether a run succeeded. REQ-V13-BEN-12 freezes this file
from commit C2 onward: `bench.py` records the sha256 of its *bytes* in
`meta.scenarios_sha256`, so any edit makes every existing benchmark file
incomparable (`report` exit 2) and unvalidatable (`check` exit 1).

The *evaluation* of a check lives in `devtools/bench.py`, deliberately not here:
a miscalibrated check is a harness defect, and fixing how a check is judged must
not have to change this file's hash.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

# Check kinds. A kind whose `turn` is `None` is about the whole run (tools,
# exit codes, summaries); the rest address one answer.
ANSWER_REGEX = "answer_regex"
ANSWER_NOT_REGEX = "answer_not_regex"
ANSWER_MAX_CHARS = "answer_max_chars"
TOOL_USED = "tool_used"
NO_TOOLS = "no_tools"
JSON_KEYS = "json_keys"
EXIT_CODE_SEEN = "exit_code_seen"
SUMMARY_EXISTS = "summary_exists"

KINDS = (
    ANSWER_REGEX, ANSWER_NOT_REGEX, ANSWER_MAX_CHARS, TOOL_USED,
    NO_TOOLS, JSON_KEYS, EXIT_CODE_SEEN, SUMMARY_EXISTS,
)
# The kinds that address one answer; the rest are about the whole run. A check
# of these kinds without a `turn` could never find an answer and so could never
# pass — a miscalibration REQ-V13-BEN-12 makes expensive, so it is refused at
# load time rather than discovered in a benchmark.
ANSWER_KINDS = (ANSWER_REGEX, ANSWER_NOT_REGEX, ANSWER_MAX_CHARS, JSON_KEYS)

# `turn=-1` — the last non-command user turn.
LAST_TURN = -1


@dataclass(frozen=True)
class Check:
    """One acceptance condition. The fields a kind does not use stay at their
    defaults; `json_pairs` is a tuple rather than a dict so that a `Check` keeps
    the hashability a frozen dataclass promises."""

    kind: str
    turn: int | None = None
    pattern: str = ""
    max_chars: int = 0
    tool: str = ""
    json_pairs: tuple[tuple[str, object], ...] = ()
    nonzero: bool = True

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown check kind: {self.kind}")

    @property
    def expected_json(self) -> dict:
        return dict(self.json_pairs)


def answer_regex(pattern: str, turn: int = LAST_TURN) -> Check:
    return Check(kind=ANSWER_REGEX, pattern=pattern, turn=turn)


def answer_not_regex(pattern: str, turn: int = LAST_TURN) -> Check:
    return Check(kind=ANSWER_NOT_REGEX, pattern=pattern, turn=turn)


def answer_max_chars(max_chars: int, turn: int = LAST_TURN) -> Check:
    return Check(kind=ANSWER_MAX_CHARS, max_chars=max_chars, turn=turn)


def tool_used(name: str) -> Check:
    return Check(kind=TOOL_USED, tool=name)


def json_keys(expected: Mapping[str, object], turn: int = LAST_TURN) -> Check:
    return Check(kind=JSON_KEYS, json_pairs=tuple(expected.items()), turn=turn)


def exit_code_seen(nonzero: bool = True) -> Check:
    return Check(kind=EXIT_CODE_SEEN, nonzero=nonzero)


# The two kinds that take no argument are values, not factories, so that the
# Appendix C table reads the same in code as in the spec.
no_tools = Check(kind=NO_TOOLS)
summary_exists = Check(kind=SUMMARY_EXISTS)


def is_command(turn: str) -> bool:
    """A turn starting with `/` is a bot command, never a numbered user turn."""
    return turn.startswith("/")


def non_command_turns(turns: list[str]) -> list[str]:
    return [turn for turn in turns if not is_command(turn)]


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    turns: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    network: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.title:
            raise ValueError("a scenario needs an id and a title")
        if not self.turns or not all(
            isinstance(turn, str) and turn.strip() for turn in self.turns
        ):
            raise ValueError(f"{self.id}: turns must be non-empty strings")
        if not self.checks:
            raise ValueError(f"{self.id}: a scenario without checks can never fail")
        # REQ-V13-BEN-08: `turn` addresses a one-based *non-command* user turn.
        # Validating it here means a scenario that outlives its own turn list
        # cannot be loaded at all, let alone benchmarked.
        countable = len(non_command_turns(self.turns))
        if countable == 0:
            raise ValueError(f"{self.id}: a scenario needs at least one user turn")
        for check in self.checks:
            if not isinstance(check, Check):
                raise ValueError(f"{self.id}: checks must be Check instances")
            if check.turn is None:
                if check.kind in ANSWER_KINDS:
                    raise ValueError(
                        f"{self.id}: check {check.kind} addresses an answer and "
                        "needs a turn"
                    )
                continue
            if check.turn != LAST_TURN and not 1 <= check.turn <= countable:
                raise ValueError(
                    f"{self.id}: check {check.kind} addresses turn {check.turn}, "
                    f"but the scenario has {countable} non-command turn(s)"
                )

    def turn_index(self, turn: int) -> int:
        """The 0-based index into the run's answers for a one-based `turn`."""
        return len(non_command_turns(self.turns)) - 1 if turn == LAST_TURN else turn - 1


SCENARIOS: list[Scenario] = [
    Scenario(
        id="S01",
        title="greet",
        turns=["Привет! Что ты умеешь? Ответь кратко."],
        checks=[
            no_tools,
            # REQ-V14-SCN-03 (H1): a tool NAME (exec/команд/скилл/skill/fetch/
            # python) or a capability PHRASE (инструмент/контейнер/навык), so
            # a fluent paraphrase that names no tool still passes.
            answer_regex(
                "exec|команд|скилл|skill|fetch|python"
                "|инструмент|контейнер|навык"
            ),
            answer_max_chars(900),
        ],
    ),
    Scenario(
        id="S02",
        title="arith",
        turns=["Посчитай 17*23+5, используя python через exec, и дай только число."],
        checks=[tool_used("exec"), answer_regex(r"\b396\b")],
    ),
    Scenario(
        id="S03",
        title="file-roundtrip",
        turns=[
            "Создай файл notes.txt с тремя строками: alpha, beta, gamma. "
            "Затем выведи, сколько строк в файле, и назови это число."
        ],
        checks=[tool_used("exec"), answer_regex(r"\b3\b|три")],
    ),
    Scenario(
        id="S04",
        title="error-explain",
        turns=[
            "Выполни python-скрипт, который импортирует модуль foo_bar_baz_qux, "
            "и объясни в одной фразе, почему он упал."
        ],
        checks=[
            tool_used("exec"),
            exit_code_seen(nonzero=True),
            answer_regex(
                "ModuleNotFoundError|foo_bar_baz_qux|не найден|not found|не установлен"
            ),
        ],
    ),
    Scenario(
        id="S05",
        title="big-output",
        turns=[
            "Выполни через exec этот python-код без изменений: import random; "
            "random.seed(7); [print(random.randint(1, 1000)) for _ in range(5000)] "
            "— и назови первое напечатанное число."
        ],
        checks=[tool_used("exec"), answer_regex(r"\b332\b")],
    ),
    Scenario(
        id="S06",
        title="noisy-log",
        turns=[
            "Запусти python-скрипт: 200 раз печатает строку 'INFO heartbeat ok', "
            "затем вычисляет 1/0. Объясни причину падения одной фразой."
        ],
        checks=[tool_used("exec"), answer_regex("ZeroDivisionError|делен|на ноль|zero")],
    ),
    Scenario(
        id="S07",
        title="skill",
        turns=["Используй скилл host-info и расскажи, что он сообщает о системе."],
        checks=[tool_used("load_skill"), answer_regex(".{40,}")],
    ),
    Scenario(
        id="S08",
        title="fetch-weather",
        turns=[
            "Какая сейчас погода в Берлине? Используй fetch на "
            "https://wttr.in/Berlin?format=3 и ответь одной строкой."
        ],
        checks=[tool_used("fetch"), answer_regex("Berlin|Берлин|°")],
        network=True,
    ),
    Scenario(
        id="S09",
        title="multi-turn",
        turns=[
            "Создай файл data.csv со строками: name,score / ann,10 / bob,20 / "
            "cid,30 / dan,40 / eve,50",
            "Посчитай через python среднее значение score из data.csv.",
            "А какое там максимальное значение score? Ответь одним числом.",
        ],
        checks=[answer_regex(r"\b30\b", turn=2), answer_regex(r"\b50\b", turn=3)],
    ),
    Scenario(
        id="S10",
        title="knowledge",
        turns=["Объясни в двух предложениях, что такое KV-cache в LLM."],
        checks=[no_tools, answer_regex("KV|кэш|кеш|cache"), answer_max_chars(900)],
    ),
    Scenario(
        id="S11",
        title="json",
        turns=["Верни строго JSON-объект с ключами a и b, где a=1, b=2. Без пояснений."],
        checks=[no_tools, json_keys({"a": 1, "b": 2})],
    ),
    Scenario(
        id="S12",
        title="summary",
        turns=[
            "Запомни: проект называется Orion, дедлайн 15 октября.",
            "Что я просил запомнить? Одной строкой.",
            "/new",
        ],
        checks=[answer_regex("Orion", turn=2), summary_exists],
    ),
]


def _validate_catalog(scenarios: list[Scenario]) -> None:
    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.id in seen:
            raise ValueError(f"duplicate scenario id: {scenario.id}")
        seen.add(scenario.id)


_validate_catalog(SCENARIOS)
