tg-agent-bot v1.11.1 — плейн-фоллбэк только на HTTP 400, ширины таблиц, /sessions пустой, паперворк v1.11.0 исправлен

Условия: плейн-фоллбэк send_pre/edit_pre теперь только на
TelegramError.status == 400; /documents рендерит id целиком до 99 999,
/model не обрезает имя модели; /sessions без сессий — обычный ответ;
DOC_LIMIT_REPLY называет обе формы /delete; один embedding-батч-
константа (llm.embeddings.BATCH_SIZE); ERR-01 строки 11-16 получили
тесты диспетчера; autouse-фикстура убила xdist-флейк секретного
реестра; README/plan.md/AGENTS.md и отчёт v1.11.0 исправлены (пять
точечных правок).

Результат: ревью в чистом контексте — 0 must-fix, 2 should-fix waived,
5 informational. Gate 6: 152/152 мутаций, wall 1043.9с (порог 1300с не
задет). Gate 7: recall@5=1.000. Gate 8 (T5, единственный прогон):
injection 5/5, hallucination 4/4, memory 3/3, judge mean 0.923 —
переиспользован на T6 (diff version-only). Версия 1.11.0→1.11.1,
uv.lock version-only, 14 pin-сайтов переписаны на месте, реальные
цифры (2411 тестов, 152 мутации). replay чист на всех 17 коммитах. T0
блокировался один раз (bot_state override), возобновлён оператором.
Локальный тег v1.11.1; пуш — на операторе.

Метрики: claude-sonnet-5 (Claude Code, оркестратор + делегированные
субагенты), промпты 256-267 (12). Живой инференс — gate 5/7/8 один
раз, заметно меньше $1 по паблик-прайсу; Claude Code — $0, подписка.

GitHub: https://github.com/axyi/tg-agent-bot
