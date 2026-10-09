# Проверка целостности данных
# Сравнивает: сколько записей было в файлах источников
#            сколько попало в SQLite + JSON + errors + осталось в WAL
# Запускать ПОСЛЕ остановки main.py

import json                            # для чтения JSON Lines
import os                              # для путей
import sqlite3                         # для чтения SQLite


# Папка проекта и папка с данными
BASE = os.path.dirname(os.path.abspath(__file__))    # где лежит verify.py
DATA = os.path.join(BASE, "data")                    # подпапка data


# Посчитать количество непустых строк в файле JSON Lines
def count_lines(path: str) -> int:
    if not os.path.exists(path):                     # если файла нет...
        return 0                                     # ...считаем 0
    count = 0                                        # счётчик
    with open(path, "r", encoding="utf-8") as f:     # открываем файл
        for line in f:                               # читаем построчно
            if line.strip():                         # если строка не пустая...
                count += 1                           # ...увеличиваем счётчик
    return count                                     # возвращаем результат


# Посчитать уникальные записи в источнике (по record_id = source|object|ts)
def count_unique_in_source(path: str) -> int:
    if not os.path.exists(path):                     # если файла нет...
        return 0                                     # ...0
    seen = set()                                     # множество уникальных ключей
    with open(path, "r", encoding="utf-8") as f:     # открываем
        for line in f:                               # читаем
            line = line.strip()                      # чистим
            if not line:                             # пустые пропускаем
                continue
            try:                                     # пытаемся разобрать
                rec = json.loads(line)               # JSON в словарь
            except json.JSONDecodeError:             # битую строку
                continue                             # пропускаем
            key = f"{rec['source_id']}|{rec['object_name']}|{rec['ts']}"   # тот же ключ, что в Record
            seen.add(key)                            # добавляем в множество
    return len(seen)                                 # сколько уникальных


# Посчитать количество уникальных record_id в SQLite (таблица trends)
def count_sqlite_trends(path: str) -> int:
    if not os.path.exists(path):                     # если БД нет...
        return 0                                     # ...0
    conn = sqlite3.connect(path)                     # подключаемся
    try:
        cur = conn.cursor()                          # курсор
        cur.execute("SELECT COUNT(*) FROM trends")   # считаем строки
        return cur.fetchone()[0]                     # первый столбец первой строки
    except sqlite3.Error:                            # если таблицы ещё нет...
        return 0                                     # ...0
    finally:
        conn.close()                                 # закрываем соединение


# Посчитать количество строк в SQLite (таблица wal_processed)
def count_sqlite_processed(path: str) -> int:
    if not os.path.exists(path):                     # если БД нет...
        return 0                                     # ...0
    conn = sqlite3.connect(path)                     # подключаемся
    try:
        cur = conn.cursor()                          # курсор
        cur.execute("SELECT COUNT(*) FROM wal_processed")   # считаем строки
        return cur.fetchone()[0]                     # результат
    except sqlite3.Error:                            # если таблицы нет...
        return 0                                     # ...0
    finally:
        conn.close()                                 # закрываем


# Посчитать, сколько записей сейчас лежит в WAL (необработанные)
def count_wal_records(path: str) -> int:
    return count_lines(path)                         # строк в WAL = необработанных записей


# Посчитать общее количество записей во всех файлах nontrends_*.jsonl
def count_all_nontrends() -> int:
    total = 0                                        # общий счётчик
    if not os.path.isdir(DATA):                      # если папки data нет...
        return 0                                     # ...0
    for name in os.listdir(DATA):                    # пробегаем по файлам в data/
        if name.startswith("nontrends_") and name.endswith(".jsonl"):   # если это наш файл
            total += count_lines(os.path.join(DATA, name))              # прибавляем его строки
    return total                                     # возвращаем итог


# Посчитать общее количество ошибок в errors.jsonl (учитывая счётчики count)
def count_errors(path: str) -> int:
    if not os.path.exists(path):                     # если файла нет...
        return 0                                     # ...0
    total = 0                                        # общий счётчик «срабатываний»
    with open(path, "r", encoding="utf-8") as f:     # открываем
        for line in f:                               # читаем
            line = line.strip()                      # чистим
            if not line:                             # пустые
                continue
            try:                                     # пытаемся разобрать
                rec = json.loads(line)               # JSON
            except json.JSONDecodeError:             # битая
                continue
            total += int(rec.get("count", 1))        # прибавляем счётчик (по умолчанию 1)
    return total                                     # возвращаем


# Собрать статистику по всем источникам
def collect_sources_stats() -> dict:
    stats = {}                                       # {source_id: count}
    for i in range(1, 5):                            # у нас 4 источника
        path = os.path.join(DATA, f"source_{i}.jsonl")   # путь к файлу источника
        stats[i] = count_unique_in_source(path)      # считаем уникальные записи
    return stats                                     # возвращаем словарь


# Главная функция — печатает отчёт
def main():
    print("=" * 60)                                  # декоративная линия для читаемости вывода
    print("ПРОВЕРКА ЦЕЛОСТНОСТИ ДАННЫХ")             # заголовок
    print("=" * 60)                                  # линия

    # 1. Что было в источниках
    sources = collect_sources_stats()                # считаем по каждому источнику
    total_in = sum(sources.values())                 # суммарно по всем
    print("\n[1] ИСТОЧНИКИ (уникальных записей)")    # заголовок
    for sid, cnt in sources.items():                 # по каждому источнику
        print(f"    source_{sid}.jsonl: {cnt}")      # печатаем
    print(f"    ИТОГО вошло: {total_in}")            # суммарно

    # 2. Что в SQLite
    sqlite_path = os.path.join(DATA, "data.db")      # путь к БД
    trends = count_sqlite_trends(sqlite_path)        # количество трендов
    processed = count_sqlite_processed(sqlite_path)  # количество обработанных записей
    print("\n[2] SQLite (data.db)")                  # заголовок
    print(f"    trends:        {trends}")            # тренды
    print(f"    wal_processed: {processed}")         # обработанные WAL-записи

    # 3. JSON не-тренды
    nontrends = count_all_nontrends()                # считаем по всем файлам nontrends_*.jsonl
    print("\n[3] JSON не-тренды")                    # заголовок
    print(f"    всего в nontrends_*.jsonl: {nontrends}")   # сколько

    # 4. Ошибки
    errors_path = os.path.join(DATA, "errors.jsonl") # путь к ошибкам
    err_count = count_errors(errors_path)            # сколько срабатываний (с учётом count)
    err_lines = count_lines(errors_path)             # сколько уникальных групп ошибок
    print("\n[4] Ошибки (errors.jsonl)")             # заголовок
    print(f"    уникальных групп: {err_count}")      # срабатываний
    print(f"    записей в файле:  {err_lines}")      # уникальных групп

    # 5. WAL — что осталось необработанным
    wal_path = os.path.join(DATA, "wal.jsonl")       # путь к WAL
    wal_left = count_wal_records(wal_path)           # сколько в WAL
    print("\n[5] WAL (необработанные записи)")       # заголовок
    print(f"    в wal.jsonl: {wal_left}")            # сколько

    # 6. Итоговая сверка
    # Формула: всё, что вошло = тренды + не-тренды + ошибки + остаток в WAL
    total_out = trends + nontrends + err_count + wal_left   # сколько «вышло» суммарно
    print("\n[6] ИТОГ")                              # заголовок
    print(f"    Вошло:  {total_in}")                 # сколько было в источниках
    print(f"    Вышло:  {total_out}")                # сколько распределилось
    diff = total_in - total_out                      # разница
    if diff == 0:                                    # если совпало...
        print("    РЕЗУЛЬТАТ: всё сошлось, потерь нет")   # ...хорошо
    elif diff > 0:                                   # если вошло больше...
        print(f"    РЕЗУЛЬТАТ: не хватает {diff} записей (возможна потеря или ещё не обработано)")   # ...тревога
    else:                                            # если вышло больше...
        print(f"    РЕЗУЛЬТАТ: лишних {abs(diff)} записей (возможны дубликаты)")   # ...тоже странно

    # 7. Пояснение про WAL
    if wal_left > 0:                                 # если в WAL что-то осталось
        print("\n[примечание] В WAL остались необработанные записи.")   # поясняем
        print("               Запустите main.py — они будут дозаписаны автоматически.")   # что делать


# Точка входа
if __name__ == "__main__":
    main()