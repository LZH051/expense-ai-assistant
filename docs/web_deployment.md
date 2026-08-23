# Web版公开部署说明

## 一、部署结构

```text
浏览器HTML/CSS/JavaScript
        ↓ HTTPS
Vercel Python / FastAPI
        ↓ DATABASE_URL
云端PostgreSQL
```

Vercel运行环境不能把本地SQLite文件作为永久数据库，因此线上必须使用
PostgreSQL。SQLite只用于本地开发和演示。

## 二、本地验证

```powershell
cd E:\expense-ai-assistant-sqlite
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python src\web_app.py
```

打开 `http://127.0.0.1:8000`，完成注册、登录、添加消费和预算测试。

## 三、准备GitHub

上传源代码，但不要上传：

```text
.env
.venv
*.db
__pycache__
```

`.gitignore` 已排除这些内容。上传前仍应再次确认没有真实密钥。

## 四、准备PostgreSQL

可以从Vercel Marketplace选择PostgreSQL提供商，也可以使用其他托管
PostgreSQL服务。创建数据库后取得连接地址，并在Vercel项目的
Environment Variables中新增：

```text
DATABASE_URL=postgresql://用户名:密码@主机/数据库名?sslmode=require
```

不要把这个连接地址写入代码、README或GitHub。

## 五、生成会话密钥

在本地PowerShell运行：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

复制输出，在Vercel环境变量中新增：

```text
SESSION_SECRET=刚才生成的随机字符串
```

这个值只放在Vercel环境变量中，不上传GitHub。

## 六、部署Vercel

1. 登录Vercel并选择 **Add New → Project**。
2. 导入该项目的GitHub仓库。
3. 保持项目根目录为仓库根目录。
4. 添加 `DATABASE_URL` 和 `SESSION_SECRET` 环境变量。
5. 点击 **Deploy**。
6. 部署完成后访问Vercel生成的 `.vercel.app` 地址。

应用首次启动时会在PostgreSQL中创建 `web_users`、`web_expenses` 和
`web_budgets` 表。

## 七、自定义域名

在Vercel项目的 **Settings → Domains** 中添加已购买域名，并按页面提示
配置DNS。没有自定义域名时，Vercel提供的 `.vercel.app` 地址也可以公开使用。

## 八、上线前检查

- 注册两个不同账户，确认看不到对方数据
- 检查新增、修改和删除消费
- 检查预算新增、更新和删除
- 检查修改密码后旧密码不能登录
- 检查删除账户会同时删除该账户的消费和预算
- 确认GitHub中不存在 `.env` 和数据库文件
- 确认Vercel Production环境已配置数据库和会话密钥

当前版本适合作为真实多用户MVP。若面向大量陌生用户长期运营，还应继续增加
邮箱验证、忘记密码邮件、数据库迁移工具、集中式限流、备份和监控。
