# Типы скалярных значений
# Иерархия: ScalarValue -> IntValue, FloatValue, BoolValue

from abc import ABC, abstractmethod   # ABC — базовый класс для абстракций, abstractmethod — метка «метод обязателен у наследников»


# Абстрактный базовый класс для всех скалярных значений
class ScalarValue(ABC):
    type_name = "scalar"              # имя типа по умолчанию

    def __init__(self, value):        # конструктор принимает значение
        self._value = value           # сохраняем значение в защищённое поле

    @property
    def value(self):                  # свойство, чтобы читать значение снаружи
        return self._value            # возвращаем сохранённое значение

    @abstractmethod
    def matches(self, raw) -> bool:   # «подходит ли сырое значение под этот тип»
        ...                           # реализации тут нет — её обязаны дать наследники

    @abstractmethod
    def cast(self, raw):              # «привести сырое значение к внутреннему виду»
        ...                           # то же — без реализации в базовом классе

    def __repr__(self):               # отладочное представление объекта
        return f"{self.__class__.__name__}({self._value!r})"   # например IntValue(5)


# Целое значение
class IntValue(ScalarValue):
    type_name = "int"                 # имя типа

    def matches(self, raw) -> bool:   # проверяем, что пришло именно целое
        if isinstance(raw, bool):     # bool в Python — подкласс int,
            return False              # поэтому True/False отсекаем вручную
        return isinstance(raw, int)   # остальное целое — подходит

    def cast(self, raw):              # приводим к int
        return int(raw)               # на всякий случай (если пришло 5.0 → 5)


# Вещественное значение
class FloatValue(ScalarValue):
    type_name = "float"               # имя типа

    def matches(self, raw) -> bool:   # проверяем, что пришло число
        if isinstance(raw, bool):     # bool снова отсекаем
            return False              # иначе True пройдёт как 1.0
        return isinstance(raw, (int, float))  # int тоже считаем float-совместимым

    def cast(self, raw):              # приводим к float
        return float(raw)             # 5 → 5.0


# Булево значение
class BoolValue(ScalarValue):
    type_name = "bool"                # имя типа

    def matches(self, raw) -> bool:   # проверяем, что пришло True/False
        return isinstance(raw, bool)  # строго булев тип

    def cast(self, raw):              # приводим к bool
        return bool(raw)              # на всякий случай


# Реестр типов — по имени из конфига получаем нужный класс
VALUE_TYPES = {
    IntValue.type_name: IntValue,     # "int"   → IntValue
    FloatValue.type_name: FloatValue, # "float" → FloatValue
    BoolValue.type_name: BoolValue,   # "bool"  → BoolValue
}


# Фабрика значений: из имени типа и сырого значения собираем объект
def make_value(type_name: str, raw) -> ScalarValue:
    cls = VALUE_TYPES.get(type_name)              # ищем класс по имени
    if cls is None:                               # если имени нет в реестре...
        raise ValueError(f"Неизвестный тип значения: {type_name}")  # ...ругаемся
    return cls(raw)                               # иначе создаём значение нужного типа