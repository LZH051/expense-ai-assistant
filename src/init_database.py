from db import connect_to_database, get_database_path
from paths import SCHEMA_FILE, ensure_directories


def initialize_database() -> None:
    """创建 SQLite 数据库文件和三张业务表。"""
    ensure_directories()
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection = connect_to_database()
    try:
        connection.executescript(schema)
        connection.commit()
    finally:
        connection.close()
    print(f"SQLite 数据库初始化成功：{get_database_path()}")


if __name__ == "__main__":
    initialize_database()
