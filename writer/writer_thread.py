# Поток-писатель: берёт записи из очереди и раскладывает их по хранилищам
# Порядок: WAL -> (SQLite или JSON) -> пометить обработанным
# Невалидные записи уходят в лог ошибок и в WAL не пишутся

import queue                            # стандартная очередь — между потоками
import threading                        # потоки
from datetime import datetime           # для лога времени

from core.record import Record        # наши записи
from core.validator import Validator  # валидатор
from storage.wal import WalStorage    # WAL
from storage.sqlite import SqliteStorage       # SQLite для трендов
from storage.json_file import JsonStorage      # JSON для не-трендов
from storage.errors import ErrorStorage        # лог ошибок


# Конец очереди — специальный маркер, чтобы остановить поток-писатель
STOP_MARKER = object()


# Поток-писатель
class WriterThread(threading.Thread):
    def __init__(self,
                 in_queue: "queue.Queue",
                 validator: Validator,
                 wal: WalStorage,
                 sqlite: SqliteStorage,
                 json_storage: JsonStorage,
                 errors: ErrorStorage):
        super().__init__(name="WriterThread", daemon=False)  # обычный поток — main дождётся его через join
        self._queue = in_queue                       # очередь, откуда берём записи
        self._validator = validator                  # валидатор
        self._wal = wal                              # WAL
        self._sqlite = sqlite                        # SQLite для трендов
        self._json = json_storage                    # JSON для не-трендов
        self._errors = errors                        # лог ошибок

        # Счётчики для консольной статистики
        self.cnt_accepted = 0                        # сколько записей всего приняли
        self.cnt_trends = 0                          # сколько ушло в SQLite
        self.cnt_json = 0                            # сколько ушло в JSON
        self.cnt_errors = 0                          # сколько ушло в лог ошибок

    def stop(self):                                  # корректная остановка потока
        self._queue.put(STOP_MARKER)                 # кидаем маркер в очередь — поток сам завершится

    def run(self):                                   # главный цикл потока
        while True:                                  # крутимся, пока не придёт маркер
            item = self._queue.get()                 # берём из очереди (ждём, если пусто)
            if item is STOP_MARKER:                  # если это маркер остановки...
                break                                # ...выходим из цикла
            self._process(item)                      # иначе обрабатываем запись

    # Обработка одной записи
    def _process(self, record: Record):
        self.cnt_accepted += 1                       # считаем принятые

        result = self._validator.validate(record)    # проверяем по конфигу
        if not result.ok:                            # если запись невалидна...
            self._errors.save_error(record, result)  # ...пишем в лог ошибок
            self.cnt_errors += 1                     # увеличиваем счётчик ошибок
            return                                   # в WAL и основные хранилища не пишем

        # 1) Сначала запись принудительно уходит в WAL
        self._wal.save(record)                       # сохраняем в wal.jsonl (с fsync)

        # 2) Затем — в SQLite (если тренд) или в JSON (если не-тренд)
        try:
            if result.obj_config.is_trend:           # если объект помечен как тренд...
                self._sqlite.save(record)            # ...пишем в SQLite
                self.cnt_trends += 1                 # считаем тренды
            else:                                    # иначе...
                self._json.save(record)              # ...пишем в JSON
                self.cnt_json += 1                   # считаем не-тренды
        except Exception:                            # если запись в SQLite/JSON упала...
            # В WAL запись остаётся — при следующем запуске восстановим и попробуем снова
            raise                                    # пробрасываем ошибку выше (её поймает main)

        # 3) Успех — помечаем WAL-запись как обработанную
        self._wal.mark_processed(record.record_id)   # при очередной очистке WAL она будет удалена

    # Строка статистики — для вывода в консоль
    def stats_line(self) -> str:
        return (f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Принято: {self.cnt_accepted} | "
                f"Тренды: {self.cnt_trends} | "
                f"JSON: {self.cnt_json} | "
                f"Ошибок: {self.cnt_errors}")