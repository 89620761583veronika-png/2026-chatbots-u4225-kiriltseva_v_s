import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from telegram import Update
from bot import build_app, command, document, text
from storage import Storage


class BotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.tmp.name) / 'test.db')
        self.app = build_app('123456:TEST_TOKEN_OFFLINE', self.db, 9)
        self.ctx = SimpleNamespace(application=self.app, bot=self.app.bot, args=[])

    def tearDown(self):
        self.tmp.cleanup()

    def update(self, value, user=1):
        message = SimpleNamespace(text=value, reply_text=AsyncMock(), reply_document=AsyncMock())
        return SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=user),
                               effective_chat=SimpleNamespace(id=user, type='private'))

    async def test_commands(self):
        update = self.update('/add high Встреча')
        self.ctx.args = ['high', 'Встреча']
        await command(update, self.ctx)
        self.assertEqual(len(self.db.tasks(1)), 1)
        update = self.update('/done 1', user=2)
        self.ctx.args = ['1']
        await command(update, self.ctx)
        self.assertIn('не найдена', update.effective_message.reply_text.call_args.args[0])
        update = self.update('/stats', user=1)
        await command(update, self.ctx)
        self.assertIn('владельцу', update.effective_message.reply_text.call_args.args[0])

    async def test_bad_input_and_plain_text(self):
        update = self.update('/remind a b')
        self.ctx.args = ['a', 'b']
        await command(update, self.ctx)
        self.assertIn('целыми', update.effective_message.reply_text.call_args.args[0])
        await text(self.update('Отправить письмо'), self.ctx)
        self.assertEqual(len(self.db.tasks(1)), 1)

    async def test_csv_upload(self):
        update = self.update('')
        file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=b'title,priority\nDemo,high\n'))
        update.effective_message.document = SimpleNamespace(file_name='tasks.csv', file_size=30, get_file=AsyncMock(return_value=file))
        await document(update, self.ctx)
        self.assertEqual(len(self.db.tasks(1)), 1)

    async def test_keyboard_shortcut(self):
        update = Update.de_json({'update_id': 1, 'message': {'message_id': 1, 'date': 0,
            'chat': {'id': 1, 'type': 'private'}, 'from': {'id': 1, 'is_bot': False, 'first_name': 'Test'},
            'text': '📋 Мои задачи'}}, self.app.bot)
        with unittest.mock.patch('bot.reply', new_callable=AsyncMock) as reply:
            await text(update, self.ctx)
            self.assertIn('Задач пока нет', reply.call_args.args[1])
