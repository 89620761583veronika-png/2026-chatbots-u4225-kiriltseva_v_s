"""ДелоБот: личные задачи участников команды, CSV и обратная связь."""
import io
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand, ReplyKeyboardMarkup, Update
from telegram.error import Forbidden, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from storage import Storage

BASE = Path(__file__).resolve().parent
HELP = '''ДелоБот помогает держать задачи под контролем.

/add high Подготовить презентацию — добавить задачу
/tasks — открытые задачи по приоритету
/search презентация — найти задачу
/done 1 — завершить задачу №1
/remind 2 30 — напомнить о задаче №2 через 30 минут
/sample — пример CSV; отправьте свой файл для импорта
/feedback 5 Удобно, хочу сроки — оставить отзыв
/myid — ваш Telegram ID
/stats и /reviews — статистика и отзывы для администратора
/help — эта справка

Обычный текст также добавляет задачу с приоритетом normal.
Работаю в личных сообщениях. Ваши задачи видны только вам.
Отзывы с Telegram ID доступны владельцу проекта; не присылайте секреты.'''
KEYBOARD = ReplyKeyboardMarkup([['📋 Мои задачи', '❓ Помощь'], ['📎 Пример CSV']], resize_keyboard=True)
log = logging.getLogger(__name__)


def store(context):
    return context.application.bot_data['storage']


async def reply(update, text):
    # Ограничение Telegram — 4096 символов; длинные списки делим на сообщения.
    for start in range(0, len(text), 3500):
        await update.effective_message.reply_text(text[start:start + 3500], reply_markup=KEYBOARD)


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        await reply(update, 'Откройте личный чат с ботом для работы с задачами.')
        return
    name = update.effective_message.text.split()[0].split('@')[0][1:]
    args = context.args
    user = update.effective_user.id
    db = store(context)
    try:
        if name in ('start', 'help'):
            await reply(update, HELP)
        elif name == 'myid':
            await reply(update, f'Ваш ID: {user}')
        elif name == 'add':
            if len(args) < 2:
                raise ValueError('Пример: /add high Подготовить презентацию')
            task_id = db.add(user, ' '.join(args[1:]), args[0])
            await reply(update, f'Задача №{task_id} добавлена.')
        elif name in ('tasks', 'search'):
            if name == 'search' and not args:
                raise ValueError('Пример: /search презентация')
            rows = db.tasks(user, ' '.join(args) if name == 'search' else '')
            text = '\n'.join(f"№{r['id']} · {r['priority']} · {r['title']}" for r in rows)
            await reply(update, text or 'Задач пока нет. Добавьте: /add normal Позвонить клиенту')
        elif name == 'done':
            if len(args) != 1:
                raise ValueError('Пример: /done 1')
            found = db.finish(user, int(args[0]))
            await reply(update, 'Задача выполнена ✅' if found else 'Открытая задача с таким номером не найдена.')
        elif name == 'remind':
            if len(args) != 2:
                raise ValueError('Пример: /remind 1 30')
            found = db.remind(user, int(args[0]), update.effective_chat.id, int(args[1]))
            await reply(update, 'Напоминание сохранено. Проверяю каждые 30 секунд.' if found else 'Открытая задача не найдена.')
        elif name == 'sample':
            with (BASE / 'data/tasks.csv').open('rb') as source:
                await update.effective_message.reply_document(source, filename='tasks.csv')
        elif name == 'feedback':
            if len(args) < 2:
                raise ValueError('Пример: /feedback 5 Что понравилось и что улучшить')
            db.feedback(user, int(args[0]), ' '.join(args[1:]))
            await reply(update, 'Спасибо! Отзыв сохранён для улучшения проекта.')
        elif name in ('stats', 'reviews'):
            if user != context.application.bot_data['admin_id']:
                await reply(update, 'Команда доступна владельцу проекта.')
                return
            if name == 'reviews':
                await update.effective_message.reply_document(io.BytesIO(db.reviews_csv()), filename='feedback.csv')
            else:
                tasks, reviews = db.statistics()
                avg = f"{reviews['rating']:.2f}" if reviews['rating'] is not None else 'нет оценок'
                await reply(update, f"Задач: {tasks['n']}; выполнено: {tasks['done']}; пользователей с задачами: {tasks['users']}\nОтзывов: {reviews['n']}; авторов отзывов: {reviews['users']}; средняя оценка: {avg}")
    except ValueError as exc:
        message = str(exc)
        if message.startswith('invalid literal'):
            message = 'Номер задачи, минуты и оценка должны быть целыми числами. /help'
        await reply(update, message)


async def text(update, context):
    if update.effective_chat.type != 'private':
        return
    value = update.effective_message.text
    shortcuts = {'📋 Мои задачи': 'tasks', '❓ Помощь': 'help', '📎 Пример CSV': 'sample'}
    if value in shortcuts:
        # Выполняем команду через новый объект Update, не меняя исходный входной объект.
        data = update.to_dict()
        data['message']['text'] = '/' + shortcuts[value]
        forwarded = Update.de_json(data, context.bot)
        context.args = []
        await command(forwarded, context)
        return
    try:
        task_id = store(context).add(update.effective_user.id, value)
        await reply(update, f'Задача №{task_id} добавлена (normal).')
    except ValueError as exc:
        await reply(update, str(exc))


async def document(update, context):
    if update.effective_chat.type != 'private':
        return
    doc = update.effective_message.document
    if not (doc.file_name or '').lower().endswith('.csv') or (doc.file_size or 0) > 100_000:
        await reply(update, 'Отправьте CSV до 100 КБ. Формат можно получить через /sample.')
        return
    content = await (await doc.get_file()).download_as_bytearray()
    if len(content) > 100_000:
        await reply(update, 'CSV превышает 100 КБ.')
        return
    try:
        count = store(context).import_tasks(update.effective_user.id, bytes(content))
        await reply(update, f'Импортировано задач: {count}. Посмотреть: /tasks. Повторная загрузка создаст новые задачи.')
    except ValueError as exc:
        await reply(update, str(exc))


async def reminders(context):
    for task in store(context).due():
        try:
            await context.bot.send_message(task['chat_id'], f"⏰ Задача №{task['id']}: {task['title']}")
            store(context).mark_reminded(task['id'])
        except Forbidden:
            store(context).mark_reminded(task['id'])
        except TelegramError:
            log.warning('Напоминание не доставлено; повторю на следующем цикле.')


async def errors(update, context):
    # Не записываем токены, содержимое сообщений и полный сетевой URL в логи.
    log.error('Ошибка обработки: %s', type(context.error).__name__)
    if isinstance(update, Update) and update.effective_message:
        try:
            await reply(update, 'Не удалось выполнить действие. Попробуйте ещё раз через минуту.')
        except TelegramError:
            pass


async def post_init(app):
    await app.bot.set_my_commands([BotCommand(name, desc) for name, desc in [
        ('start', 'Начать'), ('help', 'Справка'), ('add', 'Добавить задачу'),
        ('tasks', 'Мои задачи'), ('search', 'Поиск'), ('done', 'Завершить'),
        ('remind', 'Напомнить'), ('sample', 'Пример CSV'), ('feedback', 'Отзыв'), ('myid', 'Мой ID')]])


def build_app(token, db, admin_id=None):
    app = Application.builder().token(token).post_init(post_init).build()
    app.bot_data.update(storage=db, admin_id=admin_id)
    for name in ('start', 'help', 'myid', 'add', 'tasks', 'search', 'done', 'remind', 'sample', 'feedback', 'stats', 'reviews'):
        app.add_handler(CommandHandler(name, command))
    app.add_handler(MessageHandler(filters.Document.ALL, document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
    app.add_error_handler(errors)
    app.job_queue.run_repeating(reminders, interval=30, first=1)
    return app


def main():
    load_dotenv(BASE / '.env')
    token = os.getenv('BOT_TOKEN', '').strip()
    if not token:
        raise SystemExit('Добавьте BOT_TOKEN в .env (см. .env.example).')
    admin = os.getenv('ADMIN_USER_ID', '').strip()
    try:
        admin_id = int(admin) if admin else None
    except ValueError:
        raise SystemExit('ADMIN_USER_ID должен быть целым числом.')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    db = Storage(os.getenv('DATABASE_PATH', str(BASE / 'runtime/bot.db')))
    build_app(token, db, admin_id).run_polling(allowed_updates=['message'])


if __name__ == '__main__':
    main()
