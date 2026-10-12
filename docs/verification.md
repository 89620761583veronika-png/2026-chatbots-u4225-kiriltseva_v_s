# Проверка проекта · 12.10.2026

Среда: macOS, Python 3.12.14, python-telegram-bot 22.8, python-dotenv 1.2.1.

Команда: `.venv/bin/python -m unittest discover -s tests -v`.

```text
test_bad_input_and_plain_text ... ok
test_commands ... ok
test_csv_upload ... ok
test_keyboard_shortcut ... ok
test_atomic_csv_import ... ok
test_feedback_and_statistics ... ok
test_invalid_csv ... ok
test_ownership_and_persistence ... ok
test_priority_and_search ... ok
test_reminder_survives_restart ... ok
test_validation ... ok
Ran 11 tests
OK
```

`.venv/bin/python -m pip check`: No broken requirements found.

Запуск без токена корректно прекращается с сообщением «Добавьте BOT_TOKEN в .env
(см. .env.example)». Это проверка конфигурации, не живой запуск.

Docker Engine недоступен на момент проверки: клиент установлен, демон не запущен.
Сборка контейнера и серверный деплой ещё не проверены.
`docker compose config --quiet` проходит после явного задания имени `delobot`:
кириллическое имя рабочей папки не подходит для автоматического имени Compose.

Автоматические тесты используют подмену Telegram API; настоящие проверки перечислены ниже.

## Настоящая проверка в Telegram · 12.10.2026

В 19:29–19:34 по Москве подтверждены /start, /add high, /add low, обычный текст,
/tasks, /search, /remind 1 1 и доставка напоминания, /done, /sample, CSV-импорт,
ошибочный CSV, некорректные числовые аргументы, /feedback, /stats и /reviews.
В 19:33 выполнена штатная остановка и повторный запуск процесса, задачи сохранились.
Импорт добавил 3 задачи; ошибочный файл не добавил ни одной: в SQLite осталось 6.
Одну задачу завершили, открытых — 5. Один отзыв явно помечен техническим тестом;
это не пользовательский отзыв пилота. ADMIN_USER_ID настроен локально владельцу.

Повторно прошли все 11 тестов: [фактический журнал](test-results.txt).
GitHub Actions: [успешный запуск](https://github.com/89620761583veronika-png/2026-chatbots-u4225-kiriltseva_v_s/actions/runs/38277212084).
Скриншоты находятся в screenshots/ и встроены в отчёты. У снимков Telegram обрезана
левая область с посторонними переписками; содержание диалога с ботом не изменено.
Видео, сборка Docker, VPS, многодневное наблюдение и реальные отзывы ещё отсутствуют.
