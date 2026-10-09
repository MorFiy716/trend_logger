# Валидатор записи по конфигу
# Возвращает результат: ok или причину отказа

from dataclasses import dataclass                  # для короткого класса результата

from core.config import AppConfig, ObjectConfig        # конфиг и описание объекта
from core.record import Record                         # сама запись
from core.value import VALUE_TYPES                     # реестр типов значений


# Результат проверки одной записи
@dataclass
class ValidationResult:
    ok: bool                                       # прошла ли запись проверку
    reason: str = ""                               # код причины отказа (если не прошла)
    expected: str = ""                             # что ожидалось (для лога)
    obj_config: ObjectConfig | None = None         # конфиг объекта (если найден)


# Сам валидатор
class Validator:
    def __init__(self, config: AppConfig):         # конструктор принимает конфиг
        self._config = config                      # запоминаем конфиг

    def validate(self, record: Record) -> ValidationResult:   # главный метод — проверить запись
        source = self._config.get_source(record.source_id)    # ищем источник по id
        if source is None:                                    # если источника нет в конфиге...
            return ValidationResult(False, "unknown_source", f"source_id={record.source_id}")  # ...ошибка

        obj = source.get_object(record.object_name)           # ищем объект у этого источника
        if obj is None:                                       # если объекта нет...
            return ValidationResult(False, "unknown_object", f"object={record.object_name}")    # ...ошибка

        # Проверяем, что тип из конфига вообще нам известен
        if obj.type not in VALUE_TYPES:                       # если тип не в реестре...
            return ValidationResult(False, "unknown_type_in_config", obj.type)                  # ...ошибка

        value_cls = VALUE_TYPES[obj.type]                     # берём класс значения по типу
        value = value_cls(record.raw_value)                   # создаём значение нужного типа
        if not value.matches(record.raw_value):               # если сырое значение не подходит по типу...
            return ValidationResult(                          # ...возвращаем ошибку типа
                False,
                "type_mismatch",
                f"expected={obj.type}, received={type(record.raw_value).__name__}",
                obj,
            )

        casted = value.cast(record.raw_value)                 # приводим значение к нужному виду
        if not obj.in_range(casted):                          # если вышло за диапазон...
            return ValidationResult(                          # ...возвращаем ошибку диапазона
                False,
                "out_of_range",
                f"expected=[{obj.range_min}..{obj.range_max}], received={casted}",
                obj,
            )

        return ValidationResult(True, obj_config=obj)         # всё хорошо — запись валидна