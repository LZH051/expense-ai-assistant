# SQLite 改造说明

- MySQL 服务器连接改为 Python 标准库 `sqlite3`。
- 数据库由服务器实例改为本地 `database/expense_ai.db` 文件。
- `INSERT IGNORE` 改为 `INSERT OR IGNORE`，参数占位符 `%s` 改为 `?`。
- `DATE_FORMAT()` 改为 SQLite 的 `strftime()`。
- 表和索引改用 SQLite 兼容语法，并启用 `PRAGMA foreign_keys = ON`。
- AI 功能在所有直接入口中要求 `--confirm-paid-run`，防止误调用。
