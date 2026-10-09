# Базовый абстрактный класс для всех источников данных
# Источник умеет: открыться, отдавать новые записи, закрыться

from abc import ABC, abstractmethod    # ABC — базовый класс, abstractmethod — метка обязательного метода
from typing import Iterator            # Iterator — тип «что-то, по чему можно идти циклом»

from core.record import Record       # работаем с нашими записями


# Общий родитель для всех источников
class DataSource(ABC):
    def __init__(self, source_id: int, path: str):   # конструктор принимает id источника и путь к его файлу/ресурсу
        self._source_id = source_id                  # запоминаем id (1..4)
        self._path = path                            # запоминаем путь
        self._opened = False                         # флаг «открыт ли источник»

    @property
    def source_id(self) -> int:                      # свойство для чтения id снаружи
        return self._source_id                       # возвращаем id

    @property
    def path(self) -> str:                           # свойство для чтения пути
        return self._path                            # возвращаем путь

    @abstractmethod
    def open(self):                                  # «открыть источник» — обязателен у наследников
        ...                                          # в базовом классе реализации нет

    @abstractmethod
    def read_new(self) -> Iterator[Record]:          # «отдать все новые записи с прошлого раза» — обязателен
        ...                                          # реализация — у наследников

    @abstractmethod
    def close(self):                                 # «закрыть источник» — обязателен
        ...                                          # чтобы корректно освободить ресурсы

    def __enter__(self):                             # поддержка with DataSource(...) as s:
        self.open()                                  # при входе — открываемся
        return self                                  # возвращаем себя

    def __exit__(self, exc_type, exc, tb):           # выход из with
        self.close()                                 # при выходе — закрываемся
        return False                                 # не подавляем исключения