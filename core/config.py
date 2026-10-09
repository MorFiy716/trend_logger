# Конфиг приложения — читается один раз при старте из config.json

import json                                       # для чтения JSON-файла
from dataclasses import dataclass, field          # чтобы классы были короткими
from pathlib import Path                          # удобная работа с путями


# Описание одного объекта в конфиге
@dataclass
class ObjectConfig:
    name: str                                     # имя объекта
    type: str                                     # тип значения: "int" | "float" | "bool"
    range_min: float | int | None = None          # нижняя граница диапазона (может не быть)
    range_max: float | int | None = None          # верхняя граница диапазона (может не быть)
    is_trend: bool = False                        # является ли объект трендом

    def in_range(self, value) -> bool:            # проверяем, попадает ли значение в диапазон
        if isinstance(value, bool):               # для bool диапазон не применяем
            return True                           # булево всегда «в диапазоне»
        if self.range_min is not None and value < self.range_min:   # если есть нижняя граница и значение меньше...
            return False                          # ...не проходит
        if self.range_max is not None and value > self.range_max:   # если есть верхняя граница и значение больше...
            return False                          # ...не проходит
        return True                               # иначе всё ок


# Описание одного источника
@dataclass
class SourceConfig:
    source_id: int                                # id источника
    file_path: str                                # путь к файлу, куда пишет источник
    objects: dict[str, ObjectConfig] = field(default_factory=dict)   # объекты по имени

    def get_object(self, name: str) -> ObjectConfig | None:   # найти объект по имени
        return self.objects.get(name)             # вернёт объект или None


# Общий конфиг приложения
@dataclass
class AppConfig:
    sources: dict[int, SourceConfig] = field(default_factory=dict)   # источники по id
    paths: dict[str, str] = field(default_factory=dict)              # служебные пути (wal, sqlite, errors...)

    def get_source(self, source_id: int) -> SourceConfig | None:     # найти источник по id
        return self.sources.get(source_id)        # вернёт источник или None

    @classmethod
    def load(cls, path: str | Path) -> "AppConfig":    # загрузка конфига из файла
        with open(path, "r", encoding="utf-8") as f:   # открываем файл на чтение
            data = json.load(f)                        # читаем JSON в словарь

        cfg = cls()                                    # создаём пустой конфиг
        cfg.paths = dict(data.get("paths", {}))        # забираем служебные пути

        for src in data["sources"]:                    # проходим по всем источникам в JSON
            source = SourceConfig(                     # создаём SourceConfig
                source_id=int(src["source_id"]),       # id источника
                file_path=src["file_path"],            # путь к его файлу
            )
            for obj in src["objects"]:                 # проходим по объектам источника
                oc = ObjectConfig(                     # создаём ObjectConfig
                    name=obj["name"],                  # имя
                    type=obj["type"],                  # тип
                    range_min=obj.get("range_min"),    # нижняя граница (может отсутствовать)
                    range_max=obj.get("range_max"),    # верхняя граница (может отсутствовать)
                    is_trend=bool(obj.get("is_trend", False)),   # тренд или нет
                )
                source.objects[oc.name] = oc           # кладём объект в словарь по имени
            cfg.sources[source.source_id] = source     # кладём источник в общий словарь

        return cfg                                     # возвращаем готовый конфиг
