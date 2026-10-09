# Точка входа приложения
# Что делает:
#   1) читает config.json
#   2) создаёт папку data/ (если её нет)
#   3) открывает хранилища: WAL, SQLite, JSON, errors
#   4) восстанавливает незавершённые записи из WAL
#   5) запускает 4 потока-источника + WriterThread
#   6) раз в 5 секунд печатает статистику
#   7) по Ctrl+C корректно завершается

import os                              # для путей и создания папок
import queue                           # общая очередь
import threading                       # потоки
import time                            # паузы

from core.config import AppConfig                      # конфиг
from core.record import Record                         # запись
from core.validator import Validator                   # валидатор
from storage.wal import WalStorage                     # WAL
from storage.sqlite import SqliteStorage               # SQLite
from storage.json_file import JsonStorage              # JSON
from storage.errors import ErrorStorage                # лог ошибок
from sources.file_json import FileJsonSource           # источник
from writer.writer_thread import WriterThread          # поток-писатель


# Сколько секунд между выводами статистики
STATS_INTERVAL = 5.0


# Поток одного источника: читает и кладёт записи в общую очередь
class SourceThread(threading.Thread):
    def __init__(self, source: FileJsonSource, out_queue: "queue.Queue", stop_event: threading.Event):
        super().__init__(name=f"Source-{source.source_id}", daemon=True)   # daemon: не блокирует выход процесса
        self._source = source                    # сам источник
        self._queue = out_queue                  # куда класть записи
        self._stop_event = stop_event                  # общий флаг «пора остановиться»

    def run(self):                               # главный цикл потока
        with self._source:                       # открываем источник (with закроет его в конце)
            while not self._stop_event.is_set():       # пока не попросили остановиться
                any_read = False                 # были ли записи в этот проход
                for record in self._source.read_new():   # берём все новые записи
                    if self._stop_event.is_set():   # проверяем остановку на каждой записи
                        return                   # если пора — выходим немедленно
                    self._queue.put(record)      # кладём в общую очередь
                    any_read = True              # отмечаем, что что-то прочитали
                if not any_read:                 # если ничего не прочитали...
                    time.sleep(0.05)             # ...немного подождём, чтобы не крутить CPU


# Восстановление из WAL при старте
def restore_from_wal(wal: WalStorage, sqlite: SqliteStorage,
                     json_storage: JsonStorage, validator: Validator, errors: ErrorStorage):
    records = wal.read_all()                     # читаем все записи из WAL
    print(f"[restore] в WAL найдено записей: {len(records)}")   # сообщаем
    restored = 0                                 # сколько восстановили
    for raw in records:                          # проходим по каждой записи
        rid = raw["record_id"]                   # достаём id
        if sqlite.is_processed(rid):             # если уже обработана...
            continue                             # ...пропускаем
        record = Record(                         # собираем Record из словаря
            source_id=raw["source_id"],
            object_name=raw["object_name"],
            raw_value=raw["value"],
            ts=raw["ts"],
        )
        result = validator.validate(record)      # проверяем по конфигу
        if not result.ok:                        # если стала невалидной...
            errors.save_error(record, result)    # ...пишем в лог ошибок
            wal.mark_processed(rid)              # и помечаем как обработанную (чтобы не висела)
            continue                             # идём дальше
        # Повторяем шаги записи
        try:
            if result.obj_config.is_trend:       # тренд...
                sqlite.save(record)              # ...в SQLite
            else:                                # не-тренд...
                json_storage.save(record)        # ...в JSON
            wal.mark_processed(rid)              # помечаем как обработанную
            restored += 1                        # считаем восстановленные
        except Exception as e:                   # если снова упало...
            print(f"[restore] не удалось восстановить {rid}: {e}")   # сообщаем
    print(f"[restore] восстановлено записей: {restored}")   # итог


# Главная функция
def main():
    base = os.path.dirname(os.path.abspath(__file__))         # папка проекта (абсолютный путь)
    cfg_path = os.path.join(base, "config.json")              # путь к конфигу
    cfg = AppConfig.load(cfg_path)                            # читаем конфиг

    # Создаём папку data/ заранее — чтобы точно была
    data_dir = os.path.join(base, "data")                     # путь к папке data
    os.makedirs(data_dir, exist_ok=True)                      # создаём её (если ещё нет)
    print(f"[main] папка data: {data_dir}")                   # сообщаем

    # Собираем пути из конфига
    paths = cfg.paths                                         # словарь с путями
    wal_path = os.path.join(base, paths["wal"])               # путь к WAL
    sqlite_path = os.path.join(base, paths["sqlite"])         # путь к SQLite
    errors_path = os.path.join(base, paths["errors"])         # путь к ошибкам
    nontrends_prefix = os.path.join(base, paths["nontrends_prefix"])   # префикс JSON-файлов

    # Создаём хранилища
    wal = WalStorage(wal_path)                                # WAL
    sqlite = SqliteStorage(sqlite_path)                       # SQLite
    json_storage = JsonStorage(nontrends_prefix)              # JSON
    errors = ErrorStorage(errors_path)                        # лог ошибок
    validator = Validator(cfg)                                # валидатор по конфигу

    # Открываем всё
    wal.open()                                                # открываем WAL
    sqlite.open()                                             # открываем SQLite
    json_storage.open()                                       # открываем JSON
    errors.open()                                             # открываем лог ошибок

    source_threads = []                                       # сюда соберём потоки-источники
    writer = None                                             # поток-писатель
    stop_event = threading.Event()                            # флаг «пора остановиться»

    try:
        # Восстановление из WAL
        restore_from_wal(wal, sqlite, json_storage, validator, errors)   # добиваем незавершённые
        wal.clean()                                           # подчищаем WAL после восстановления

        # Очередь
        q: "queue.Queue" = queue.Queue(maxsize=1000)          # ограничим очередь: до 5000 записей

        # WriterThread
        writer = WriterThread(q, validator, wal, sqlite, json_storage, errors)   # создаём писателя
        writer.start()                                        # запускаем

        # Потоки-источники (по одному на каждый source_id из конфига)
        for sid, src_cfg in cfg.sources.items():              # проходим по источникам
            src_path = os.path.join(base, src_cfg.file_path)  # путь к файлу источника
            source = FileJsonSource(sid, src_path)            # создаём источник
            th = SourceThread(source, q, stop_event)          # оборачиваем в поток
            th.start()                                        # запускаем
            source_threads.append(th)                         # запоминаем

        print("[main] приложение запущено, Ctrl+C для остановки")   # сообщаем

        # Основной цикл — печатаем статистику раз в 5 секунд
        while True:                                           # бесконечно
            time.sleep(STATS_INTERVAL)                        # ждём 5 секунд
            print(writer.stats_line())                        # печатаем статистику писателя

    except KeyboardInterrupt:                                 # поймали Ctrl+C
        print("\n[main] остановка по Ctrl+C")                 # сообщаем
    finally:
        # Корректная остановка
        stop_event.set()                                      # просим потоки-источники остановиться
        for th in source_threads:                             # ждём каждый поток-источник
            th.join(timeout=2.0)                              # максимум 2 секунды на поток

        if writer is not None:                                # если писатель был создан...
            writer.stop()                                     # ...просим его закончить
            writer.join(timeout=30.0)                          # ...ждём писателя
            if writer.is_alive():  # если всё ещё жив...
                print("[main] ВНИМАНИЕ: WriterThread не завершился за 120 с")
                print("[main] возможна потеря данных в очереди, но WAL защитит остальное")
                # WriterThread станет zombie daemon-потоком и умрёт вместе с процессом
                # WAL НЕ закрываем — пусть ОС разберётся, данные уже на диске
                return
        # Теперь безопасно закрываем всё
        wal.clean()                                           # финальная очистка WAL
        wal.close()                                           # закрываем всё
        sqlite.close()
        json_storage.close()
        errors.close()
        print("[main] завершено")                             # сообщаем


if __name__ == "__main__":
    main()