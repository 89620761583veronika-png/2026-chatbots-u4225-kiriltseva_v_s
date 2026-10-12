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

Telegram API в автоматических тестах заменён. Не проверены настоящая доставка
сообщений, видео, многодневная стабильность, GitHub Actions и пользовательский пилот.

12.10.2026: Telegram getMe подтвердил `itmoftmi_kvs_bot`; приложение и планировщик
успешно запущены локально. Это не подтверждает прохождение всех команд в клиенте Telegram.
