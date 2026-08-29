# 安心账本｜个人消费与预算管理网站

安心账本是一个基于 FastAPI 的多用户个人记账网站，支持消费记录管理、分类预算、预算超支提醒和个人账户管理。每位用户的数据相互隔离，可在电脑或手机浏览器中使用。

## 在线体验

- 网站首页：<https://expense-ai-assistant.vercel.app/>

## 主要功能

### 多用户账户

- 用户名、邮箱和密码注册
- 登录、退出及登录状态管理
- 密码使用随机盐和 `scrypt` 哈希保存，不存储明文
- 修改用户名、邮箱和密码
- 永久删除账户以及该账户的消费和预算数据
- 每位用户只能查看和修改自己的数据

### 消费管理

- 新增、查看、修改和删除消费记录
- 记录消费日期、类别、金额、商户或地点及说明
- 消费类别采用固定选项，避免输入格式不一致
- 按类别、开始日期和结束日期筛选记录
- 金额使用 `Decimal` 校验和计算，避免浮点数精度问题

目前支持的消费类别：餐饮、交通、购物、居住、娱乐、医疗、教育、旅行和其他。

### AI 消费分析

- 网站内生成当月 AI 消费分析（/insights），基于聚合统计而非原始流水
- 分析结果按月保存，浏览不重复调用付费接口；同月重新生成覆盖更新
- 未配置 AI 环境变量时页面会明确提示
- 调用带超时、瞬时故障指数退避重试，token 用量记录到 `output/ai_usage.jsonl`

### 预算与统计

- 按月份和类别设置或更新预算
- 支持“全部类别”月度总预算
- 删除不再需要的预算
- 仪表盘显示累计支出、本月支出、本月预算和消费笔数
- 显示分类消费排行和最近消费
- 总预算（"全部类别"）超支提醒与分类预算逐类别超支提醒分开计算
- 预算页显示当月各分类执行进度条，仪表盘有近12个月趋势折线与分类占比环形图（本地自托管 Chart.js，无 CDN）
- 消费列表分页（每页20条）并显示"共 N 条 · 合计"，支持本月/近30天快捷筛选
- 手机（H5）与电脑浏览器均已适配，移动端表格自动转卡片式布局

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy
- 页面：Jinja2、HTML、CSS
- 本地数据库：SQLite
- 公网数据库：Neon PostgreSQL
- 部署平台：Vercel

## 项目结构

```text
api/                 Vercel FastAPI 入口
src/                 网页、数据库、ETL、统计和命令行代码
static/              网页样式
templates/           Jinja2 页面模板
data/                原始和清洗后的模拟消费数据
database/            SQLite 建表脚本和本地数据库目录
output/              ETL 报告和统计输出
tests/               网页功能测试
docs/                部署等补充说明
```

`.env`、`.db`、虚拟环境、缓存和密钥不得提交到 GitHub。

## 本地安装

Windows PowerShell：

```powershell
cd E:\expense-ai-assistant-sqlite
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

不需要激活虚拟环境，可以直接使用 `.venv` 中的 Python，避免 PowerShell 执行策略阻止 `Activate.ps1`。

## 环境变量

本地开发可复制 `.env.example` 后按需填写：

```env
# 原命令行 SQLite 数据库
SQLITE_DB_PATH=database/expense_ai.db

# 可选 AI 分析
AI_API_KEY=
AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
AI_MODEL=doubao-seed-2-0-lite-260428

# Web 数据库和登录会话
DATABASE_URL=
SESSION_SECRET=
```

说明：

- 本地不填写 `DATABASE_URL` 时，Web 版默认使用 `database/web_expense.db`。
- Vercel 部署必须配置云端 PostgreSQL `DATABASE_URL` 和随机的 `SESSION_SECRET`。
- 不要在 README、代码或 GitHub 中填写真实密钥。

## 本地运行网站

```powershell
.\.venv\Scripts\python.exe -m uvicorn web_app:app --app-dir src --reload
```

浏览器打开：<http://127.0.0.1:8000>

本地 Web 数据库默认保存在：

```text
E:\expense-ai-assistant-sqlite\database\web_expense.db
```

它与命令行 ETL 使用的 `database/expense_ai.db` 相互独立。

## 命令行 ETL 版本

执行模拟数据生成、清洗、SQLite 入库和统计：

```powershell
.\.venv\Scripts\python.exe src\main.py
.\.venv\Scripts\python.exe src\verify_project.py
```

交互式手动录入消费：

```powershell
.\.venv\Scripts\python.exe src\main.py --interactive
```

可选 AI 消费分析只在明确确认可能产生费用后执行：

```powershell
.\.venv\Scripts\python.exe src\main.py --with-ai --confirm-paid-run
```

## JSON API（/api/v1）

登录会话即可调用，错误统一封装为 `{"error": {"code", "message"}}`，金额一律为字符串：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/statistics` | 分类汇总、近12个月逐月合计（缺月补零）、预算对账状态 |
| GET | `/api/v1/expenses` | 分页查询（`page`/`page_size`≤100/`category`/`start_date`/`end_date`） |
| POST | `/api/v1/expenses` | JSON 创建消费，Pydantic 校验 |
| GET | `/api/v1/categories` | 类别清单 |

`/health` 会真实探测数据库，异常时返回 503。交互式文档见 `/docs`。

## 测试

安装开发依赖后，一条命令运行全部测试（pytest 会自动收集 `tests/` 下所有用例）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

测试的临时数据库与登录态由 `tests/conftest.py` 统一提供，每个用例独享干净数据库。
推送到 GitHub 后，`.github/workflows/tests.yml` 会自动运行同样的测试。

## Vercel 部署

1. 将代码上传到 GitHub，但不要上传 `.env`、`.db`、`.venv`、`__pycache__` 或日志。
2. 在 Vercel 导入 GitHub 仓库，根目录保持 `./`。
3. 在 Vercel 设置 `DATABASE_URL` 和 `SESSION_SECRET`。
4. 部署后访问 `/health`、`/register` 和 `/login` 检查运行状态。

更详细的部署说明见 [`docs/web_deployment.md`](docs/web_deployment.md)。

## 数据与安全说明

- 公网用户数据保存在 Neon PostgreSQL，不保存在 Vercel 临时文件系统中。
- Cookie 使用签名会话，并设置基础安全响应头和 CSRF 防护。
- 所有消费、预算、资料修改和删除操作都会校验当前登录用户。
- 登录失败限流（同一邮箱 15 分钟 5 次），登录校验做了等时处理防邮箱枚举。
- 响应头含 CSP、线上 HSTS；登录态页面 Cache-Control: no-store。
- 线上环境缺少 `SESSION_SECRET` 或 `DATABASE_URL` 会拒绝启动，不再静默降级。
- “永久保存”仍取决于云数据库服务状态、保留政策和备份策略，重要数据应定期备份。
- 请勿在公开仓库中提交真实账户数据、数据库连接串或 API 密钥。

## 项目用途

本项目用于学习 Python ETL、SQLite/PostgreSQL、FastAPI、多用户数据隔离、身份验证、预算分析和云端部署。
