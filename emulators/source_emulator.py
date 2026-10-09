# Эмулятор одного источника данных
# Запускается как отдельная программа: python source_emulator.py 1
# Пишет в data/source_1.jsonl от 100 до 600 сообщений в секунду

import json                            # для сериализации записей
import os                              # для создания папки
import random                          # для случайных значений
import sys                             # для аргументов командной строки
import time                            # для пауз между сообщениями
from datetime import datetime          # для метки времени


# Сколько сообщений в секунду шлёт источник (мин и макс)
MIN_PER_SEC = 100
MAX_PER_SEC = 600


# Прочитать конфиг источника — какие объекты он «умеет» слать
def load_source_objects(config_path: str, source_id: int):
    with open(config_path, "r", encoding="utf-8") as f:   # открываем конфиг
        data = json.load(f)                                # читаем JSON
    for src in data["sources"]:                            # ищем нужный источник
        if int(src["source_id"]) == source_id:             # если id совпал...
            return src["objects"]                          # ...возвращаем список объектов
    return []                                              # если не нашли — пустой список


# Сгенерировать случайное значение для объекта
def random_value(obj: dict):
    t = obj["type"]                                        # тип значения из конфига
    if t == "bool":                                        # для bool...
        return random.choice([True, False])                # ...кидаем монетку
    lo = obj.get("range_min")                              # нижняя граница (может не быть)
    hi = obj.get("range_max")                              # верхняя граница (может не быть)
    if lo is not None and hi is not None:                  # если обе есть...
        if t == "int":                                     # ...и тип int
            return random.randint(int(lo), int(hi))        # ...случайное целое в диапазоне
        return round(random.uniform(float(lo), float(hi)), 2)  # иначе — float с 2 знаками
    if t == "int":                                         # если диапазона нет и int
        return random.randint(0, 100)                      # случайное целое 0..100
    return round(random.uniform(0.0, 100.0), 2)            # иначе float 0..100


# Сгенерировать «плохое» значение — чтобы иногда валидатор ловил ошибки
def maybe_broken_value(obj: dict, good_value):
    if random.random() > 0.02:                             # в 98% случаев всё хорошо
        return good_value                                  # отдаём нормальное значение
    # А в 2% — специально ломаем: тип или диапазон
    t = obj["type"]                                        # тип из конфига
    if t == "bool":                                        # для bool
        return random.choice(["yes", "no", 0, 1])          # шлём что-то не булево
    if random.random() < 0.5:                              # для чисел — иногда портим тип
        return "неправильно"                               # строка вместо числа
    return (good_value or 0) + random.randint(1000, 5000)  # иногда выходим за диапазон


# Основной цикл эмулятора
def run(source_id: int, config_path: str, data_dir: str):
    objects = load_source_objects(config_path, source_id)   # что умеет слать этот источник
    if not objects:                                        # если объектов нет...
        print(f"[src {source_id}] нет объектов в конфиге — выходим")   # сообщаем
        return                                             # и выходим

    out_path = os.path.join(data_dir, f"source_{source_id}.jsonl")   # путь к файлу источника
    os.makedirs(data_dir, exist_ok=True)                   # создаём папку, если нет
    print(f"[src {source_id}] пишу в {out_path}")          # сообщаем, куда пишем

    with open(out_path, "a", encoding="utf-8", buffering=1) as f:   # открываем на дозапись
        while True:                                        # бесконечный цикл
            # Раз в секунду выбираем новое число сообщений
            count = random.randint(MIN_PER_SEC, MAX_PER_SEC)   # от 100 до 600
            period = 1.0 / count                           # сколько ждать между сообщениями
            for _ in range(count):                         # шлём нужное количество
                obj = random.choice(objects)               # случайный объект
                value = random_value(obj)                  # случайное значение
                value = maybe_broken_value(obj, value)     # иногда ломаем
                record = {                                 # собираем запись
                    "source_id": source_id,                # id источника
                    "object_name": obj["name"],            # имя объекта
                    "value": value,                        # значение
                    "ts": datetime.now().isoformat(timespec="milliseconds"),   # метка времени
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")   # пишем строку
                time.sleep(period)                         # пауза, чтобы уложиться в 100–600/с


# Точка входа — читаем id источника из аргументов
if __name__ == "__main__":
    if len(sys.argv) < 2:                                  # если id не передали...
        print("Использование: python source_emulator.py <source_id>")   # подсказка
        sys.exit(1)                                        # выход
    sid = int(sys.argv[1])                                 # id источника из аргумента
    config = os.path.join(os.path.dirname(__file__), "..", "config.json")   # путь к конфигу
    data = os.path.join(os.path.dirname(__file__), "..", "data")            # путь к папке data
    run(sid, config, data)                                 # запускаем