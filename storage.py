"""SQLite: задачи каждого пользователя изолированы, SQL использует параметры."""
import csv
import io
import sqlite3
import time
from pathlib import Path

PRIORITIES = {'high': 0, 'normal': 1, 'low': 2}


def validate_task(title, priority):
    title = title.strip()
    if not 1 <= len(title) <= 500:
        raise ValueError('Текст задачи должен содержать от 1 до 500 символов.')
    if priority not in PRIORITIES:
        raise ValueError('Приоритет: high, normal или low.')
    return title


def parse_csv(content):
    try:
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        if reader.fieldnames != ['title', 'priority']:
            raise ValueError('CSV должен иметь заголовок title,priority.')
        rows = []
        for row in reader:
            if None in row or row.get('title') is None or row.get('priority') is None:
                raise ValueError('Некорректное количество столбцов CSV.')
            rows.append((validate_task(row['title'], row['priority'].strip()), row['priority'].strip()))
            if len(rows) > 100:
                raise ValueError('За один раз можно импортировать до 100 задач.')
        if not rows:
            raise ValueError('В CSV нет задач.')
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError('Нужен CSV в кодировке UTF-8.') from exc


class Storage:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                    title TEXT NOT NULL, priority TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    remind_at REAL, chat_id INTEGER, reminded INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS tasks_owner ON tasks(user_id, done);
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                    comment TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def add(self, user_id, title, priority='normal'):
        title = validate_task(title, priority)
        with self.connect() as db:
            return db.execute('INSERT INTO tasks(user_id,title,priority) VALUES(?,?,?)',
                              (user_id, title, priority)).lastrowid

    def import_tasks(self, user_id, content):
        rows = parse_csv(content)  # Проверяем весь файл до записи: импорт атомарный.
        with self.connect() as db:
            db.executemany('INSERT INTO tasks(user_id,title,priority) VALUES(?,?,?)',
                           [(user_id, title, priority) for title, priority in rows])
        return len(rows)

    def tasks(self, user_id, query=''):
        with self.connect() as db:
            rows = db.execute('''SELECT * FROM tasks WHERE user_id=? AND done=0
                ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, id''',
                              (user_id,)).fetchall()
        return [row for row in rows if query.casefold() in row['title'].casefold()]

    def finish(self, user_id, task_id):
        with self.connect() as db:
            return db.execute('UPDATE tasks SET done=1 WHERE id=? AND user_id=? AND done=0',
                              (task_id, user_id)).rowcount == 1

    def remind(self, user_id, task_id, chat_id, minutes):
        if not 1 <= minutes <= 43200:
            raise ValueError('Укажите от 1 до 43200 минут.')
        with self.connect() as db:
            return db.execute('''UPDATE tasks SET remind_at=?, chat_id=?, reminded=0
                WHERE id=? AND user_id=? AND done=0''',
                              (time.time() + minutes * 60, chat_id, task_id, user_id)).rowcount == 1

    def due(self):
        with self.connect() as db:
            return db.execute('SELECT * FROM tasks WHERE done=0 AND reminded=0 AND remind_at<=?',
                              (time.time(),)).fetchall()

    def mark_reminded(self, task_id):
        with self.connect() as db:
            db.execute('UPDATE tasks SET reminded=1 WHERE id=?', (task_id,))

    def feedback(self, user_id, rating, comment):
        if not 1 <= rating <= 5 or not 1 <= len(comment.strip()) <= 1000:
            raise ValueError('Нужны оценка 1–5 и комментарий от 1 до 1000 символов.')
        with self.connect() as db:
            db.execute('INSERT INTO feedback(user_id,rating,comment) VALUES(?,?,?)',
                       (user_id, rating, comment.strip()))

    def statistics(self):
        with self.connect() as db:
            tasks = db.execute('SELECT COUNT(*) n,COUNT(DISTINCT user_id) users,COALESCE(SUM(done),0) done FROM tasks').fetchone()
            reviews = db.execute('SELECT COUNT(*) n,COUNT(DISTINCT user_id) users,AVG(rating) rating FROM feedback').fetchone()
        return dict(tasks), dict(reviews)

    def reviews_csv(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['id', 'user_id', 'rating', 'comment', 'created_at'])
        with self.connect() as db:
            for row in db.execute('SELECT * FROM feedback ORDER BY id'):
                values = list(row)
                # Защита при открытии пользовательского текста в Excel.
                if values[3].startswith(('=', '+', '-', '@', '\t', '\r')):
                    values[3] = "'" + values[3]
                writer.writerow(values)
        return output.getvalue().encode('utf-8-sig')
