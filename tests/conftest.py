"""pytest 共享配置。

关键点：环境变量必须在导入 web_app 之前设置——engine 在
web_database 导入期就已按 DATABASE_URL 创建，事后改环境变量无效。
conftest.py 会先于所有测试模块被 pytest 加载，所以放在这里。
"""

import os
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

_TMP_DIR = tempfile.mkdtemp(prefix="expense-pytest-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DIR}/web.db")
os.environ.setdefault("SESSION_SECRET", "pytest-session-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import web_app  # noqa: E402
from web_database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """每个测试都拿到干净的数据库，避免用例间互相污染。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(web_app.app) as test_client:
        yield test_client


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "页面中未找到 csrf_token 隐藏域"
    return match.group(1)


def register(client: TestClient, email: str = "pytest@example.com") -> None:
    page = client.get("/register")
    response = client.post(
        "/register",
        data={
            "username": "Pytest User",
            "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf_token": csrf_from(page.text),
        },
    )
    assert response.status_code == 200, response.status_code


@pytest.fixture
def user_client(client):
    """已注册并处于登录态的客户端。"""
    register(client)
    return client
