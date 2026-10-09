from sources.base import DataSource           # базовый класс источника
from sources.file_json import FileJsonSource  # источник из JSON Lines файла

__all__ = ["DataSource", "FileJsonSource"]