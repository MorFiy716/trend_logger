# WAL-журнал (Write-Ahead Log)
# Сначала запись принудительно идёт на диск, только потом — в SQLite/JSON
# Обработанные записи периодически удаляются из файла
# fsync делается НЕ на каждую запись, а раз в 100 мс — это ускоряет работу в 10–20 раз

import hashlib                         # для контрольной суммы (md5) каждой строки
import json                            # для чтения/записи JSON Lines
import os                              # нужен для fsync, создания папки и атомарной замены файла
import time                            # нужен для отсчёта 5 секунд между очистками и 100 мс между fsync

from storage.base import Storage       # наш базовый класс
from core.record import Record         # работаем с записями


# Сколько секунд между очистками WAL
CLEAN_INTERVAL_SEC = 5.0
# Сколько обработанных записей накопить, чтобы досрочно почистить WAL
CLEAN_THRESHOLD = 100
# Сколько секунд между fsync (групповая синхронизация на диск)
FSYNC_INTERVAL_SEC = 0.1


# WAL-хранилище
class WalStorage(Storage):
    def __init__(self, path: str):         # конструктор принимает путь к wal.jsonl
        super().__init__(path)             # сохраняем путь в базовом классе
        self._file = None                  # файл, в который пишем
        self._processed: set[str] = set()  # record_id записей, уже успешно доставленных
        self._last_clean = 0.0             # когда в последний раз чистили файл
        self._last_fsync = 0.0             # когда в последний раз делали fsync
        self._pending_fsync = False        # есть ли несинхронизированные записи

    def open(self):                        # открыть файл на дозапись
        folder = os.path.dirname(self._path)   # папка, где должен лежать WAL
        if folder:                             # если папка указана...
            os.makedirs(folder, exist_ok=True) # ...создаём её (если ещё нет)
        # buffering=1 — построчная буферизация: flush после каждой строки
        self._file = open(self._path, "a", encoding="utf-8", buffering=1)
        self._last_clean = time.time()     # запоминаем момент открытия
        self._last_fsync = time.time()     # и момент последнего fsync

    def close(self):                       # закрыть файл
        if self._file is not None:         # если файл открыт...
            if self._pending_fsync:        # если остались несинхронизированные записи...
                try:
                    os.fsync(self._file.fileno())   # ...синхронизируем перед закрытием
                except OSError:
                    pass                   # если не получилось — не страшно, ОС сама сбросит
            self._file.close()             # ...закрываем
            self._file = None              # и обнуляем ссылку
            self._pending_fsync = False    # сбрасываем флаг

    # Собрать строку записи вместе с CRC
    def _line_with_crc(self, record: Record) -> str:
        body = record.to_json_line()                                # JSON-строка записи
        crc = hashlib.md5(body.encode("utf-8")).hexdigest()         # считаем md5 от неё
        return json.dumps({"body": body, "crc": crc},               # оборачиваем body + crc в ещё один JSON
                          ensure_ascii=False)                       # русские буквы не экранируем

    # Записать запись в WAL (flush сразу, fsync — раз в 100 мс)
    def save(self, record: Record):
        line = self._line_with_crc(record)     # формируем строку с CRC
        self._file.write(line + "\n")          # пишем строку в файл
        self._file.flush()                     # сбрасываем буфер Python в ОС
        self._pending_fsync = True             # помечаем: есть что синхронизировать

        now = time.time()                                       # текущее время
        if now - self._last_fsync >= FSYNC_INTERVAL_SEC:        # если прошло 100 мс...
            os.fsync(self._file.fileno())                       # ...просим ОС записать физически на диск
            self._last_fsync = now                              # запоминаем момент
            self._pending_fsync = False                         # синхронизация выполнена

        self._maybe_clean()                    # возможно, пора почистить файл

    # Пометить запись как обработанную (успешно улетела в SQLite или JSON)
    def mark_processed(self, record_id: str):
        self._processed.add(record_id)         # кладём id в множество обработанных

    # Пора ли чистить файл
    def _maybe_clean(self):
        now = time.time()                                       # текущее время
        if (now - self._last_clean >= CLEAN_INTERVAL_SEC        # если прошло 5 секунд...
                or len(self._processed) >= CLEAN_THRESHOLD):    # ...или накопилось 100 обработанных
            self.clean()                                        # чистим файл

    # Очистка: оставляем только необработанные записи
    def clean(self):
        if self._file is None:                 # если файл почему-то не открыт...
            return                             # ...чистить нечего
        if not self._processed:                # если нечего чистить...
            self._last_clean = time.time()     # ...просто обновим время
            return                             # и выйдем

        # Перед перезаписью — синхронизируем, если есть несинхронизированные
        if self._pending_fsync:                # если были записи после последнего fsync...
            try:
                os.fsync(self._file.fileno())  # ...синхронизируем их
            except OSError:
                pass
            self._pending_fsync = False

        self._file.close()                     # закрываем текущий файл (чтобы читать его целиком)
        tmp_path = self._path + ".tmp"         # временный файл, куда пишем «оставшееся»

        kept = 0                               # счётчик оставленных записей (для отладки)
        with open(self._path, "r", encoding="utf-8") as src, \
             open(tmp_path, "w", encoding="utf-8") as dst:     # открываем исходный и временный файлы
            for raw_line in src:                                 # читаем построчно
                raw_line = raw_line.strip()                      # убираем \n и пробелы
                if not raw_line:                                 # пустые строки пропускаем
                    continue
                try:                                             # пытаемся разобрать строку
                    wrapper = json.loads(raw_line)               # внешний JSON с body и crc
                    body = wrapper["body"]                       # достаём body
                    crc_expected = wrapper["crc"]                # достаём ожидаемый crc
                except (json.JSONDecodeError, KeyError):         # если строка битая...
                    continue                                     # ...просто выбрасываем
                crc_real = hashlib.md5(body.encode("utf-8")).hexdigest()   # пересчитываем crc
                if crc_real != crc_expected:                     # если не совпало...
                    continue                                     # ...запись повреждена, выкидываем
                rec = json.loads(body)                           # разбираем саму запись
                if rec.get("record_id") in self._processed:      # если запись уже обработана...
                    continue                                     # ...не сохраняем
                dst.write(raw_line + "\n")                       # иначе — оставляем в новом файле
                kept += 1                                        # считаем оставшиеся

        os.replace(tmp_path, self._path)                         # атомарно подменяем старый файл новым
        self._file = open(self._path, "a", encoding="utf-8", buffering=1)   # снова открываем на дозапись
        self._processed.clear()                                  # обработанные больше не нужны
        self._last_clean = time.time()                           # запоминаем момент очистки

    # Прочитать все записи из WAL — нужно при восстановлении при старте
    def read_all(self) -> list[dict]:
        result = []                                              # сюда сложим валидные записи
        if not os.path.exists(self._path):                       # если файла ещё нет...
            return result                                        # ...возвращаем пустой список
        with open(self._path, "r", encoding="utf-8") as f:       # открываем WAL
            for raw_line in f:                                   # читаем построчно
                raw_line = raw_line.strip()                      # чистим
                if not raw_line:                                 # пустые — пропускаем
                    continue
                try:                                             # пытаемся разобрать
                    wrapper = json.loads(raw_line)               # внешний JSON
                    body = wrapper["body"]                       # body
                    crc_expected = wrapper["crc"]                # crc
                except (json.JSONDecodeError, KeyError):         # битая строка
                    continue                                     # пропускаем
                crc_real = hashlib.md5(body.encode("utf-8")).hexdigest()   # пересчитываем crc
                if crc_real != crc_expected:                     # если не совпало...
                    continue                                     # ...запись повреждена
                result.append(json.loads(body))                  # добавляем разобранную запись
        return result                                            # возвращаем всё, что нашли