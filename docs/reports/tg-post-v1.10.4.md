tg-agent-bot v1.10.4 — пять мутаций v1103-* приземлены, все frozen-list пины переписаны, gate 8 зелёный на этом прогоне

Условия: добить остаток остановленного v1.10.3 — пять мутаций v1103-*
(авторские ещё в T6, но не закоммиченные) приземлить в mutation_check.py
(mutation-all 144), переписать frozen-list пины тестов на
presence/contiguity/order вместо хрупких «последний элемент», прогнать
gate 8 один раз за весь прогон на openai/gpt-4.1, судья
anthropic/claude-sonnet-5.

Результат: ревью в чистом контексте — 5/5 PASS. Gate 6 дважды (T4, T5)
144/144 убито. Единственный gate 8: injection 5/5, hallucination 4/4,
memory 3/3, judge mean 0.907, latency 3.58s — все пороги пройдены. T5:
версия 1.9.5→1.10.4, uv.lock online, README/AGENTS.md — реальные цифры
(2311 тестов, 144 мутации). Gate 8 у T5 переиспользован из T4 (diff
версии-only). `replay` чист на всех 13 коммитах. Локальный тег v1.10.4;
пуш — на операторе.

Метрики: claude-sonnet-5 (Claude Code), 6 промптов (228-233). Живой
инференс заметно меньше $1; Claude Code — $0, подписка.

GitHub: https://github.com/axyi/tg-agent-bot
