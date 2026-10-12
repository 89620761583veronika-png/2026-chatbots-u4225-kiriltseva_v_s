import tempfile
import time
import unittest
from pathlib import Path
from storage import Storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.tmp.name) / 'test.db')

    def tearDown(self):
        self.tmp.cleanup()

    def test_ownership_and_persistence(self):
        task = self.db.add(1, 'Позвонить клиенту')
        self.assertFalse(self.db.finish(2, task))
        self.assertFalse(self.db.remind(2, task, 2, 10))
        self.assertEqual(self.db.tasks(2), [])
        reopened = Storage(self.db.path)
        self.assertEqual(reopened.tasks(1)[0]['title'], 'Позвонить клиенту')
        self.assertTrue(reopened.finish(1, task))
        self.assertEqual(reopened.tasks(1), [])

    def test_priority_and_search(self):
        self.db.add(1, 'Архив', 'low')
        self.db.add(1, 'Презентация', 'high')
        self.assertEqual(self.db.tasks(1)[0]['priority'], 'high')
        self.assertEqual(len(self.db.tasks(1, 'ПРЕЗ')), 1)

    def test_atomic_csv_import(self):
        invalid = 'title,priority\nПервая,normal\nВторая,wrong\n'.encode()
        with self.assertRaises(ValueError):
            self.db.import_tasks(1, invalid)
        self.assertEqual(self.db.tasks(1), [])
        self.assertEqual(self.db.import_tasks(1, b'\xef\xbb\xbftitle,priority\nDemo,high\n'), 1)

    def test_invalid_csv(self):
        for content in (b'name,priority\na,high', b'title,priority', b'\xff',
                        b'title,priority\na,high,extra', b'title,priority\na'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.db.import_tasks(1, content)

    def test_validation(self):
        for title, priority in [('', 'normal'), ('x' * 501, 'normal'), ('a', 'wrong')]:
            with self.assertRaises(ValueError):
                self.db.add(1, title, priority)
        for rating in (0, 6):
            with self.assertRaises(ValueError):
                self.db.feedback(1, rating, 'Комментарий')

    def test_reminder_survives_restart(self):
        task = self.db.add(1, 'Встреча')
        self.db.remind(1, task, 1, 1)
        with self.db.connect() as conn:
            conn.execute('UPDATE tasks SET remind_at=? WHERE id=?', (time.time() - 1, task))
        reopened = Storage(self.db.path)
        self.assertEqual(len(reopened.due()), 1)
        reopened.mark_reminded(task)
        self.assertEqual(reopened.due(), [])

    def test_feedback_and_statistics(self):
        self.db.feedback(1, 5, '=FORMULA')
        self.db.feedback(1, 3, 'Второй отзыв')
        self.db.feedback(2, 4, 'Хорошо')
        tasks, reviews = self.db.statistics()
        self.assertEqual(reviews['users'], 2)
        self.assertEqual(reviews['rating'], 4)
        self.assertIn("'=FORMULA", self.db.reviews_csv().decode('utf-8-sig'))


if __name__ == '__main__':
    unittest.main()
