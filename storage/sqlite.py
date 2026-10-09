# SQLite-хранилище для трендов
# Две таблицы: trends (сами значения) и wal_processed (id уже обработанных записей)
# Соединение открывается с check_same_thread=False — чтобы писать из WriterThread

import os                              # нужен, чтобы создать папку под БД
import sqlite3                         # стандартная библиотека для SQLite
import threading                       # замок для безопасной записи из потоков

from storage.base import Storage       # базовый класс
from core.record import Record         # наши записи


# Хранилище трендов в SQLite
class SqliteStorage(Storage):
    def __init__(self, path: str):     # конструктор принимает путь к data.db
        super().__init__(path)         # сохраняем путь
        self._conn = None              # соединение с БД
        self._cur = None               # курсор для запросов
        self._lock = threading.Lock()  # замок: пишем/читаем по очереди

    def open(self):                                            # открыть соединение и создать таблицы
        folder = os.path.dirname(self._path)                   # папка, где лежит БД
        if folder:                                             # если папка указана...
            os.makedirs(folder, exist_ok=True)                 # ...создаём её (если ещё нет)
        # check_same_thread=False — разрешаем использовать соединение из других потоков
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._cur = self._conn.cursor()                        # берём курсор
        self._create_tables()                                  # создаём таблицы, если их нет

    def _create_tables(self):                                  # создание таблиц и индексов
        # Таблица для трендов
        self._cur.execute("""
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT UNIQUE,
                source_id INTEGER NOT NULL,
                object_name TEXT NOT NULL,
                value REAL,
                ts TEXT NOT NULL
            )
        """)                                                   # UNIQUE на record_id — защита от дубликатов
        # Таблица для обработанных WAL-записей
        self._cur.execute("""
            CREATE TABLE IF NOT EXISTS wal_processed (
                record_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
        """)                                                   # сюда пишем id записей, уже улетевших в trends
        # Индексы — чтобы искать было быстро
        self._cur.execute("CREATE INDEX IF NOT EXISTS idx_trends_src_obj ON trends(source_id, object_name)")
        self._cur.execute("CREATE INDEX IF NOT EXISTS idx_trends_ts ON trends(ts)")
        self._conn.commit()                                    # фиксируем изменения

    def save(self, record: Record):                            # сохранить тренд
        with self._lock:                                       # заходим под замок — пишем только по одному
            try:
                self._cur.execute(                             # вставляем запись в trends
                    "INSERT OR IGNORE INTO trends(record_id, source_id, object_name, value, ts) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (record.record_id, record.source_id, record.object_name,
                     float(record.raw_value) if not isinstance(record.raw_value, bool)
                     else int(record.raw_value), record.ts),
                )
                self._cur.execute(                             # помечаем record_id как обработанный
                    "INSERT OR IGNORE INTO wal_processed(record_id, processed_at) VALUES (?, ?)",
                    (record.record_id, record.ts),
                )
                self._conn.commit()                            # фиксируем транзакцию
            except sqlite3.Error:                              # если что-то не так...
                self._conn.rollback()                          # ...откатываем изменения
                raise                                          # и пробрасываем ошибку выше

    def is_processed(self, record_id: str) -> bool:            # проверяем, обрабатывалась ли запись
        with self._lock:                                       # тоже под замком
            self._cur.execute("SELECT 1 FROM wal_processed WHERE record_id = ?", (record_id,))
            return self._cur.fetchone() is not None            # если есть строка — уже обработана

    def close(self):                                           # закрыть соединение
        if self._conn is not None:                             # если соединение открыто...
            self._conn.close()                                 # ...закрываем
            self._conn = None                                  # обнуляем
            self._cur = None                                   # и курсор тоже