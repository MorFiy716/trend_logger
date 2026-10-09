# Удобный импорт всего из пакета storage одним разом

from storage.base import Storage                        # базовый класс
from storage.wal import WalStorage                      # WAL
from storage.sqlite import SqliteStorage                # SQLite для трендов
from storage.json_file import JsonStorage               # JSON для не-трендов
from storage.errors import ErrorStorage                 # лог ошибок

__all__ = [                                      # что экспортируется из пакета
    "Storage",
    "WalStorage",
    "SqliteStorage",
    "JsonStorage",
    "ErrorStorage",
]