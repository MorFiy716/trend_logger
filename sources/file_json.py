# Источник, читающий JSON Lines из файла
# Все 4 источника у нас — такие: source_1.jsonl, source_2.jsonl, source_3.jsonl, source_4.jsonl

import json                            # для разбора JSON-строк
import os                              # для проверки существования файла

from sources.base import DataSource           # наш базовый класс
from core.record import Record       # наши записи


# Источник, читающий из файла в формате JSON Lines
class FileJsonSource(DataSource):
    def __init__(self, source_id: int, path: str):    # конструктор
        super().__init__(source_id, path)             # сохраняем id и путь
        self._file = None                             # открытый файл
        self._position = 0                            # на какой позиции в файле мы остановились в прошлый раз

    def open(self):                                   # открыть файл на чтение
        if not os.path.exists(self._path):            # если файла ещё нет...
            # Создаём пустой файл, чтобы дальнейшее чтение не падало
            open(self._path, "a", encoding="utf-8").close()
        self._file = open(self._path, "r", encoding="utf-8")   # открываем на чтение
        self._file.seek(self._position)               # встаём на сохранённую позицию
        self._opened = True                           # помечаем, что открылись

    def read_new(self):                               # отдать все новые записи с прошлого вызова
        if not self._opened:                          # если источник не открыт...
            return                                    # ...просто выходим (ничего не отдаём)
        self._file.seek(self._position)               # встаём на позицию, где остановились
        for line in self._file:                       # идём по строкам файла
            line = line.strip()                       # убираем \n и пробелы
            if not line:                              # пустые строки пропускаем
                continue
            try:                                      # пытаемся разобрать строку
                record = Record.from_json_line(line)  # из JSON-строки делаем Record
            except (json.JSONDecodeError, KeyError):  # если строка битая...
                continue                              # ...пропускаем её
            yield record                              # отдаём запись наружу
        self._position = self._file.tell()            # запоминаем, где остановились

    def close(self):                                  # закрыть файл
        if self._file is not None:                    # если открыт...
            self._file.close()                        # ...закрываем
            self._file = None                         # обнуляем
            self._opened = False                      # помечаем, что закрылись