# JSON-хранилище для не-трендов
# Пишет в JSON Lines, ротация каждые 1000 строк

import json                            # для записи строк
import os                              # для создания папки

from storage.base import Storage              # базовый класс
from core.record import Record       # наши записи


# Сколько строк в одном файле
LINES_PER_FILE = 1000


# Хранилище не-трендов в JSON Lines
class JsonStorage(Storage):
    def __init__(self, path_prefix: str):       # конструктор принимает префикс пути
        super().__init__(path_prefix)           # сохраняем префикс, например "data/nontrends_"
        self._file = None                       # текущий открытый файл
        self._file_index = 0                    # номер текущего файла (0001, 0002, ...)
        self._line_count = 0                    # сколько строк уже записали в текущий файл

    def open(self):                             # открыть папку и первый файл
        folder = os.path.dirname(self._path)    # папка, где лежат файлы
        if folder:                              # если папка указана...
            os.makedirs(folder, exist_ok=True)  # ...создаём её
        self._open_next_file()                  # открываем первый файл

    def _current_filename(self) -> str:                        # имя текущего файла
        return f"{self._path}{self._file_index:04d}.jsonl"    # например nontrends_0001.jsonl

    def _open_next_file(self):                                 # открыть следующий файл
        if self._file is not None:                             # если предыдущий был открыт...
            self._file.close()                                 # ...закрываем
        self._file_index += 1                                  # увеличиваем номер
        self._line_count = 0                                   # сбрасываем счётчик строк
        self._file = open(self._current_filename(), "a", encoding="utf-8", buffering=1)   # открываем новый

    def save(self, record: Record):                            # сохранить не-тренд
        line = json.dumps({                                    # собираем словарь
            "record_id": record.record_id,                     # id записи
            "source_id": record.source_id,                     # источник
            "object_name": record.object_name,                 # объект
            "value": record.raw_value,                         # значение
            "ts": record.ts,                                   # время
        }, ensure_ascii=False)                                 # русские буквы не экранируем
        self._file.write(line + "\n")                          # пишем строку
        self._line_count += 1                                  # увеличиваем счётчик
        if self._line_count >= LINES_PER_FILE:                 # если набралось 1000 строк...
            self._open_next_file()                             # ...переходим в следующий файл

    def close(self):                                           # закрыть текущий файл
        if self._file is not None:                             # если открыт...
            self._file.close()                                 # ...закрываем
            self._file = None                                  # обнуляем