# Импорт всего из пакета core одним разом

from core.config import AppConfig, SourceConfig, ObjectConfig   # конфиг и его части
from core.record import Record                                  # запись
from core.value import ScalarValue, IntValue, FloatValue, BoolValue, VALUE_TYPES, make_value   # типы значений
from core.validator import Validator, ValidationResult          # валидатор

__all__ = [                                                 # что экспортируется из пакета
    "AppConfig", "SourceConfig", "ObjectConfig",            # конфиг
    "Record",                                               # запись
    "ScalarValue", "IntValue", "FloatValue", "BoolValue",   # типы значений
    "VALUE_TYPES", "make_value",                            # реестр и фабрика
    "Validator", "ValidationResult",                        # валидация
]