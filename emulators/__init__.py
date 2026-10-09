# Пакет emulators — содержит эмуляторы источников данных

from emulators.source_emulator import run, load_source_objects, random_value   # экспортируем полезное наружу

__all__ = ["run", "load_source_objects", "random_value"]              # что доступно через emulators.*