# Запись — одно входящее сообщение от источника

import json                                       # нужен для чтения/записи JSON
from dataclasses import dataclass, field          # dataclass — чтобы не писать __init__ вручную
from datetime import datetime                     # для получения текущего времени


# Класс одной записи
@dataclass
class Record:
    source_id: int                                # id источника (1..4)
    object_name: str                              # имя объекта (например, temp_supply)
    raw_value: object                             # сырое значение как пришло (int/float/bool)
    ts: str                                       # метка времени в виде строки ISO

    record_id: str = field(init=False)            # уникальный id записи, задаётся автоматически

    def __post_init__(self):                      # вызывается сразу после конструктора
        # Ключ уникальности: источник + объект + время
        self.record_id = f"{self.source_id}|{self.object_name}|{self.ts}"   # собираем строку-ключ

    @classmethod
    def from_json_line(cls, line: str) -> "Record":     # разбор строки из файла источника
        data = json.loads(line)                          # превращаем строку в словарь
        return cls(                                      # создаём Record из полей словаря
            source_id=int(data["source_id"]),            # id источника приводим к int
            object_name=str(data["object_name"]),        # имя объекта — строка
            raw_value=data["value"],                     # значение как есть
            ts=str(data["ts"]),                          # время строкой
        )

    def to_json_line(self) -> str:                # сериализация для WAL
        return json.dumps({                       # собираем словарь и превращаем в JSON-строку
            "record_id": self.record_id,          # обязательно сохраняем id (для идемпотентности)
            "source_id": self.source_id,          # источник
            "object_name": self.object_name,      # объект
            "value": self.raw_value,              # значение
            "ts": self.ts,                        # время
        }, ensure_ascii=False)                    # не экранируем русские буквы

    @staticmethod
    def now_iso() -> str:                         # удобный помощник — текущее время строкой
        return datetime.now().isoformat(timespec="milliseconds")   # например 2026-10-03T12:00:00.123