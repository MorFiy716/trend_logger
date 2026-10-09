# Лог ошибок
# Одинаковые ошибки не пишутся заново — увеличивается счётчик count

import json                            # для записи JSON Lines
import os                              # для создания папки
import threading                       # чтобы безопасно писать из разных потоков
from datetime import datetime          # для текущего времени

from storage.base import Storage              # базовый класс
from core.record import Record       # наши записи
from core.validator import ValidationResult   # результат проверки


# Хранилище ошибок с группировкой
class ErrorStorage(Storage):
    def __init__(self, path: str):         # конструктор принимает путь к errors.jsonl
        super().__init__(path)             # сохраняем путь
        self._file = None                  # открытый файл
        # Словарь уже встреченных ошибок: ключ -> индекс в self._records
        self._groups: dict[tuple, int] = {}
        # Список самих записей об ошибках (чтобы потом перезаписывать файл)
        self._records: list[dict] = []
        self._lock = threading.Lock()      # замок — пишем из разных потоков аккуратно

    def open(self):                                    # открыть файл
        folder = os.path.dirname(self._path)           # папка
        if folder:                                     # если указана...
            os.makedirs(folder, exist_ok=True)         # ...создаём
        self._file = open(self._path, "a", encoding="utf-8", buffering=1)   # открываем на дозапись

    def close(self):                                   # закрыть файл
        if self._file is not None:                     # если открыт...
            self._file.close()                         # ...закрываем
            self._file = None                          # обнуляем

    # Ключ группировки — по нему понимаем, что ошибка «та же самая»
    @staticmethod
    def _group_key(record: Record, result: ValidationResult) -> tuple:
        return (record.source_id, record.object_name, result.reason, result.expected)

    # Записать ошибку
    def save_error(self, record: Record, result: ValidationResult):
        with self._lock:                                       # заходим под замок
            key = self._group_key(record, result)              # ключ группировки
            now = datetime.now().isoformat(timespec="seconds") # текущее время
            if key in self._groups:                            # если такая ошибка уже была...
                idx = self._groups[key]                        # ...берём её индекс
                self._records[idx]["count"] += 1               # увеличиваем счётчик
                self._records[idx]["last_seen"] = now          # обновляем время последнего появления
            else:                                              # если впервые...
                self._groups[key] = len(self._records)         # запоминаем индекс новой записи
                self._records.append({                         # добавляем новую запись
                    "first_seen": now,                         # когда впервые увидели
                    "last_seen": now,                          # когда последний раз
                    "count": 1,                                # сколько раз встретилась
                    "source_id": record.source_id,             # источник
                    "object_name": record.object_name,         # объект
                    "reason": result.reason,                   # причина
                    "expected": result.expected,               # что ожидалось
                    "received": record.raw_value,              # что пришло
                })
            self._rewrite_file()                               # перезаписываем файл целиком

    # Перезапись файла целиком — чтобы count всегда был актуальным
    def _rewrite_file(self):
        self._file.close()                                     # закрываем текущий файл
        tmp = self._path + ".tmp"                              # временный файл
        with open(tmp, "w", encoding="utf-8") as f:            # пишем во временный
            for rec in self._records:                          # проходим по всем записям
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")   # пишем JSON-строку
        os.replace(tmp, self._path)                            # атомарно подменяем
        self._file = open(self._path, "a", encoding="utf-8", buffering=1)   # снова открываем

    # Storage.save() у ErrorStorage не используется — но абстракцию надо соблюсти
    def save(self, record: Record):
        raise NotImplementedError("Для ошибок используйте save_error(record, result)")