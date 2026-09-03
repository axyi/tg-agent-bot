"""spec-v1.4: honored reasoning control, S01 check repair, errata.

One test per T-V14-* id of section 12.2. Offline discipline unchanged
(REQ-V14-TST-01): no test touches the network, DNS or a real Docker daemon;
every LLM interaction is faked.
"""

import re

from devtools import bench_scenarios


def _s01_answer_regex_pattern() -> str:
    s01 = next(s for s in bench_scenarios.SCENARIOS if s.id == "S01")
    check = next(c for c in s01.checks if c.kind == bench_scenarios.ANSWER_REGEX)
    return check.pattern


def test_t_v14_scn_01_s01_check_accepts_capability_paraphrase():
    """T-V14-SCN-01 (SCN-03, H1 branch only): the repaired S01 check passes
    on each of the three recorded v1.3 candidate answers
    (docs/assets/bench/optimized.json, S01 runs 1-3) and on the baseline's
    passing answers (docs/assets/bench/baseline.json, S01 runs 1-2), and
    still fails on an off-topic or refusing answer. Inlined as literals, per
    the requirement, never read from a benchmark file."""
    pattern = _s01_answer_regex_pattern()

    v13_candidate_answers = [
        "Привет! Я — большая языковая модель Qwen. Могу отвечать на вопросы, "
        "писать и редактировать тексты, переводить, помогать с кодом, "
        "анализировать информацию и рассуждать над сложными задачами. Также "
        "у меня есть инструменты: могу узнать погоду в любом городе и "
        "рассказать о среде, в которой работаю. Чем помочь?",
        "Привет! Я — большая языковая модель Qwen. Могу отвечать на вопросы, "
        "писать и редактировать тексты, переводить, помогать с кодом, "
        "анализировать информацию и рассуждать над сложными задачами. Также "
        "у меня есть инструменты: могу узнать погоду в любом городе и "
        "рассказать о среде, в которой работаю. Чем помочь?",
        "Привет! Я отвечаю на вопросы, помогаю с текстами, переводами и "
        "идеями. Могу показать погоду и прогноз для любого города, запустить "
        "команды в изолированном Linux-контейнере и рассказать о его "
        "окружении. Спроси что-нибудь конкретное!",
    ]
    for answer in v13_candidate_answers:
        assert re.search(pattern, answer, re.I | re.S), answer

    v13_baseline_answers = [
        "Привет! Вот что я умею:\n\n- Отвечать на вопросы и объяснять темы\n"
        "- Показывать погоду и прогноз для любого города\n- Рассказывать о "
        "среде, в которой я работаю (контейнер, диск, Python)\n- Запускать "
        "программы в изолированном контейнере\n- Получать данные из сети по "
        "разрешённым адресам\n\nСпрашивай — помогу.",
        "Привет! Я умею:\n\n- Отвечать на вопросы и помогать с текстами, "
        "идеями, переводами\n- Показывать погоду и прогноз для любого "
        "города\n- Рассказывать о среде, в которой работаю (система, диск, "
        "Python)\n- Выполнять простые команды в изолированном контейнере\n\n"
        "Спрашивай — помогу!",
    ]
    for answer in v13_baseline_answers:
        assert re.search(pattern, answer, re.I | re.S), answer

    off_topic = (
        "Сегодня хорошая погода, а как у тебя дела? Расскажи о своих планах "
        "на выходные."
    )
    refusing = "Извините, я не могу ответить на этот вопрос."
    assert re.search(pattern, off_topic, re.I | re.S) is None
    assert re.search(pattern, refusing, re.I | re.S) is None
