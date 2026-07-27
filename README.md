# 个人消费记账与 AI 分析助手

本项目使用 SQLite 存储数据，数据库文件位于
`database/expense_ai.db`，无需安装或启动数据库服务器。

## 功能

- 生成50～100条模拟消费记录并清洗异常、空值和重复数据
- 创建 `users`、`expenses`、`budgets` 三张 SQLite 表
- 使用唯一约束和 `INSERT OR IGNORE` 保证重复运行不重复入库
- 按类别、月份统计消费并进行预算对比
- 可选调用 OpenAI 兼容接口生成消费建议

## 安装

```powershell
cd E:\expense-ai-assistant-sqlite
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```


## 运行与验收

```powershell
python src\main.py
python src\load_database.py
python src\verify_project.py
```

第二次入库应显示新增0条，证明去重有效。数据库文件可用
DB Browser for SQLite 打开：

```text
E:\expense-ai-assistant-sqlite\database\expense_ai.db
```

## AI 分析

在 `.env` 中填写本地密钥并确认费用后运行：

```powershell
python src\main.py --with-ai --confirm-paid-run
```

`.env`、`.db` 和虚拟环境均已加入 `.gitignore`。
