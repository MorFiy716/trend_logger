# Генератор config.json
# Делает 4 источника, 1000 объектов на каждый и 20 трендов (по 5 на систему)

import json                            # для записи JSON
import os                              # для путей


# Какие системы и какие тренды у них
SYSTEMS = {
    1: {  # Котельная
        "system": "boiler",
        "trends": [
            ("temp_supply",     "float", 60,  95),
            ("temp_return",     "float", 40,  70),
            ("pressure_boiler", "float", 1.0, 3.5),
            ("flow_water",      "float", 0,   100),
            ("water_level",     "float", 0,   100),
        ],
    },
    2: {  # Насосная
        "system": "pump",
        "trends": [
            ("pump_speed",        "float", 0, 3000),
            ("pump_current",      "float", 0, 50),
            ("pump_vibration",    "float", 0, 10),
            ("pump_temp",         "float", 20, 90),
            ("pump_pressure_out", "float", 1.0, 4.0),
        ],
    },
    3: {  # Вентиляция
        "system": "vent",
        "trends": [
            ("air_temp_in",  "float", -10, 40),
            ("air_temp_out", "float", -10, 40),
            ("air_humidity", "float", 0, 100),
            ("fan_speed",    "float", 0, 2000),
            ("air_flow",     "float", 0, 5000),
        ],
    },
    4: {  # Электрика
        "system": "power",
        "trends": [
            ("voltage_l1",   "float", 200, 250),
            ("voltage_l2",   "float", 200, 250),
            ("voltage_l3",   "float", 200, 250),
            ("current_main", "float", 0, 100),
            ("power_total",  "float", 0, 100),
        ],
    },
}


# Сколько всего объектов у каждого источника
TOTAL_OBJECTS = 1000


# Сгенерировать один объект (тренд или обычный)
def make_object(name: str, typ: str, lo, hi, is_trend: bool) -> dict:
    return {                                       # словарь описывает один объект
        "name": name,                              # имя
        "type": typ,                               # тип
        "range_min": lo,                           # нижняя граница
        "range_max": hi,                           # верхняя граница
        "is_trend": is_trend,                      # тренд или нет
    }


# Сгенерировать 1000 объектов для источника
def make_objects(source_id: int) -> list:
    info = SYSTEMS[source_id]                      # берём описание системы
    objects = []                                   # сюда складываем объекты

    # Сначала 5 трендов
    for name, typ, lo, hi in info["trends"]:       # проходим по трендам
        objects.append(make_object(name, typ, lo, hi, True))   # добавляем как тренд

    # Потом добавляем простые объекты (bool и int), пока не наберём 1000
    # Bool-объекты — разные «флаги»
    bool_names = [
        "is_running", "is_alarm", "is_open", "is_closed",
        "is_ready", "is_blocked", "is_heating", "is_cooling",
        "is_day_mode", "is_night_mode",
    ]
    idx = 0                                        # счётчик, чтобы имена не повторялись
    while len(objects) < TOTAL_OBJECTS:            # пока объектов меньше 1000...
        if len(objects) % 3 == 0:                  # каждый третий — bool
            name = f"{info['system']}_flag_{idx}"  # имя с суффиксом
            objects.append(make_object(name, "bool", None, None, False))   # добавляем bool
        else:                                      # остальные — int
            name = f"{info['system']}_param_{idx}" # имя с суффиксом
            objects.append(make_object(name, "int", 0, 1000, False))       # добавляем int
        idx += 1                                   # увеличиваем счётчик

    return objects                                 # возвращаем список объектов


# Собрать весь конфиг
def build_config() -> dict:
    cfg = {                                        # сам конфиг
        "paths": {                                 # служебные пути
            "wal": "data/wal.jsonl",               # WAL
            "sqlite": "data/data.db",              # SQLite
            "errors": "data/errors.jsonl",         # лог ошибок
            "app_log": "data/app.log",             # общий лог
            "nontrends_prefix": "data/nontrends_", # префикс файлов JSON для не-трендов
        },
        "sources": [],                             # список источников заполним ниже
    }
    for sid in SYSTEMS:                            # проходим по всем 4 системам
        cfg["sources"].append({                    # добавляем источник
            "source_id": sid,                      # id
            "file_path": f"data/source_{sid}.jsonl",   # куда пишет эмулятор
            "objects": make_objects(sid),          # список из 1000 объектов
        })
    return cfg                                     # возвращаем готовый конфиг


# Точка входа
if __name__ == "__main__":
    base = os.path.dirname(__file__)               # папка, где лежит скрипт
    out = os.path.join(base, "config.json")        # путь к config.json
    cfg = build_config()                           # строим конфиг
    with open(out, "w", encoding="utf-8") as f:    # открываем на запись
        json.dump(cfg, f, ensure_ascii=False, indent=2)   # пишем красиво
    print(f"config.json создан: {out}")            # сообщаем
    print(f"Всего источников: {len(cfg['sources'])}")   # сколько источников
    for src in cfg["sources"]:                     # по каждому источнику...
        trends = sum(1 for o in src["objects"] if o["is_trend"])   # считаем тренды
        print(f"  source {src['source_id']}: объектов = {len(src['objects'])}, трендов = {trends}")