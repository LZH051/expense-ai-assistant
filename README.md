# 安心账本｜个人消费与预算管理

项目一现包含两个可独立运行的版本：

- 原SQLite命令行版：模拟数据、ETL、统计和可选AI分析。
- 多用户Web版：注册登录、数据隔离、消费增删改查、预算和仪表盘。

## Web版功能

- 任何人可以使用邮箱注册个人账户
- 密码通过随机盐和 `scrypt` 哈希保存，不存储明文密码
- 每个用户只能访问自己的消费和预算
- 新增、查看、筛选、编辑和删除消费记录
- 创建、更新和删除月度分类预算
- 修改账户资料和密码
- 用户可以永久删除账户及其全部数据
- CSRF保护、签名会话Cookie和基础安全响应头
- 响应式HTML界面，支持电脑和手机
- 本地SQLite开发，线上PostgreSQL持久化

## 安装

```powershell
cd E:\expense-ai-assistant-sqlite
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## 本地运行Web版

```powershell
python src\web_app.py
```

浏览器打开：

```text
http://127.0.0.1:8000
```

本地Web数据库默认保存在：

```text
database/web_expense.db
```

它与原命令行版的 `database/expense_ai.db` 分开，互不影响。

## 公开部署

项目已包含 `api/index.py` 和 `vercel.json`。公开部署时必须：

1. 使用云端PostgreSQL数据库，设置 `DATABASE_URL`。
2. 生成随机会话密钥，设置 `SESSION_SECRET`。
3. 将代码上传GitHub并在Vercel导入仓库。

完整步骤见 [docs/web_deployment.md](docs/web_deployment.md)。

不要把真实的 `.env`、数据库密码、会话密钥或AI密钥上传GitHub。

## 原命令行版

完整ETL流程：

```powershell
python src\main.py
python src\verify_project.py
```

命令行手动记账：

```powershell
python src\main.py --interactive
```

可选AI分析：

```powershell
python src\main.py --with-ai --confirm-paid-run
```

原SQLite数据库可使用DB Browser for SQLite打开：

```text
E:\expense-ai-assistant-sqlite\database\expense_ai.db
```
