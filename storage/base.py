# Базовый абстрактный класс для всех хранилищ
# Любое хранилище умеет: открыться, сохранить значение, закрыться

from abc import ABC, abstractmethod    # ABC — базовый класс для абстракций, abstractmethod — метка «метод обязателен»
from core.record import Record       # работаем с нашими записями


# Общий родитель для WAL, SQLite, JSON и лога ошибок
class Storage(ABC):
    def __init__(self, path: str):     # конструктор принимает путь к файлу/БД
        self._path = path              # запоминаем путь в защищённом поле

    @property
    def path(self):                    # свойство, чтобы читать путь снаружи
        return self._path              # возвращаем путь

    @abstractmethod
    def open(self):                    # «открыть хранилище» — реализуют наследники
        ...                            # в базовом классе реализации нет

    @abstractmethod
    def save(self, record: Record):    # «сохранить запись» — тоже обязателен у наследников
        ...                            # у каждого хранилища своя логика

    @abstractmethod
    def close(self):                   # «закрыть хранилище» — обязательно
        ...                            # чтобы корректно закрыть файлы/соединения

    def __enter__(self):               # поддержка конструкции with Storage(...) as s:
        self.open()                    # при входе — открываемся
        return self                    # возвращаем себя

    def __exit__(self, exc_type, exc, tb):   # выход из with
        self.close()                   # при выходе — закрываемся
        return False                   # не подавляем исключения