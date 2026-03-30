"""
测试空值/空白内容拦截功能。

覆盖范围：
- ModerationRequest Pydantic 模型层验证（第一道防线）
- ModerationService 服务层守卫（第二道防线）
- HTTP API 层端到端验证
"""
import pytest
import pytest_asyncio
from pydantic import ValidationError
from httpx import AsyncClient, ASGITransport

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ModerationRequest
from moderation_service import ModerationService
from main import app


# ---------------------------------------------------------------------------
# 第一道防线：Pydantic 模型层
# ---------------------------------------------------------------------------

class TestModerationRequestValidation:
    """ModerationRequest 模型对空值/空白内容的拦截测试"""

    # --- 应被拦截的输入 ---

    def test_none_content_is_rejected(self):
        """content 为 None 时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(content=None, creator_id="user1")

    def test_empty_string_is_rejected(self):
        """content 为空字符串时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(content="", creator_id="user1")

    def test_single_space_is_rejected(self):
        """content 为单个空格时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(content=" ", creator_id="user1")

    def test_multiple_spaces_are_rejected(self):
        """content 为多个空格时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(content="     ", creator_id="user1")

    def test_tab_only_is_rejected(self):
        """content 仅含制表符时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(content="\t", creator_id="user1")

    def test_newline_only_is_rejected(self):
        """content 仅含换行符时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(content="\n", creator_id="user1")

    def test_mixed_whitespace_is_rejected(self):
        """content 为混合空白字符时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(content=" \t\n\r ", creator_id="user1")

    def test_missing_content_field_is_rejected(self):
        """content 字段缺失时应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ModerationRequest(creator_id="user1")

    # --- 应通过的合法输入 ---

    def test_normal_content_is_accepted(self):
        """正常文本内容应通过验证"""
        req = ModerationRequest(content="Hello world", creator_id="user1")
        assert req.content == "Hello world"

    def test_content_with_leading_trailing_spaces_is_stripped(self):
        """首尾有空格的内容应被 strip 后通过验证"""
        req = ModerationRequest(content="  hello  ", creator_id="user1")
        assert req.content == "hello"

    def test_single_character_is_accepted(self):
        """单个非空字符应通过验证"""
        req = ModerationRequest(content="a", creator_id="user1")
        assert req.content == "a"

    def test_content_with_internal_spaces_is_accepted(self):
        """内容中含空格（非纯空白）应通过验证"""
        req = ModerationRequest(content="hello world", creator_id="user1")
        assert req.content == "hello world"

    def test_chinese_content_is_accepted(self):
        """中文内容应通过验证"""
        req = ModerationRequest(content="这是一条正常内容", creator_id="user1")
        assert req.content == "这是一条正常内容"

    def test_numeric_content_is_accepted(self):
        """纯数字内容应通过验证"""
        req = ModerationRequest(content="12345", creator_id="user1")
        assert req.content == "12345"


# ---------------------------------------------------------------------------
# 第二道防线：ModerationService 服务层
# ---------------------------------------------------------------------------

class TestModerationServiceGuard:
    """ModerationService 对空内容的服务层守卫测试"""

    def _make_service(self) -> ModerationService:
        return ModerationService(openai_key="mock-key", anthropic_key="mock-key")

    def _make_request(self, content: str) -> ModerationRequest:
        """绕过 Pydantic 验证直接构造对象，模拟验证被绕过的场景"""
        req = object.__new__(ModerationRequest)
        object.__setattr__(req, "content", content)
        object.__setattr__(req, "creator_id", "user1")
        object.__setattr__(req, "video_id", None)
        return req

    @pytest.mark.asyncio
    async def test_service_rejects_empty_string(self):
        """服务层应拒绝空字符串，不调用 AI API"""
        service = self._make_service()
        req = self._make_request("")
        with pytest.raises(ValueError, match="empty or whitespace-only"):
            await service.moderate_content(req)

    @pytest.mark.asyncio
    async def test_service_rejects_whitespace_only(self):
        """服务层应拒绝纯空白字符串"""
        service = self._make_service()
        req = self._make_request("   \t\n  ")
        with pytest.raises(ValueError, match="empty or whitespace-only"):
            await service.moderate_content(req)

    @pytest.mark.asyncio
    async def test_service_rejects_none(self):
        """服务层应拒绝 None 值"""
        service = self._make_service()
        req = self._make_request(None)
        with pytest.raises((ValueError, AttributeError)):
            await service.moderate_content(req)

    @pytest.mark.asyncio
    async def test_service_processes_valid_content(self):
        """服务层应正常处理有效内容"""
        service = self._make_service()
        req = ModerationRequest(content="A normal video description", creator_id="user1")
        result = await service.moderate_content(req)
        assert result.is_safe is True
        assert 0.0 <= result.confidence <= 1.0
        assert result.provider == "openai+anthropic"


# ---------------------------------------------------------------------------
# 端到端：HTTP API 层
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAPIEndpointNullGuard:
    """通过 HTTP 接口测试空值拦截行为"""

    async def _client(self):
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def test_api_rejects_null_content(self):
        """API 应拒绝 content 为 null 的请求，返回 422"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": None, "creator_id": "u1"})
        assert resp.status_code == 422

    async def test_api_rejects_empty_string(self):
        """API 应拒绝 content 为空字符串的请求，返回 422"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "", "creator_id": "u1"})
        assert resp.status_code == 422

    async def test_api_rejects_whitespace_only(self):
        """API 应拒绝 content 为纯空白的请求，返回 422"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "   ", "creator_id": "u1"})
        assert resp.status_code == 422

    async def test_api_rejects_tab_only(self):
        """API 应拒绝 content 仅含制表符的请求，返回 422"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "\t\t\t", "creator_id": "u1"})
        assert resp.status_code == 422

    async def test_api_rejects_newline_only(self):
        """API 应拒绝 content 仅含换行符的请求，返回 422"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "\n\n", "creator_id": "u1"})
        assert resp.status_code == 422

    async def test_api_rejects_missing_content_field(self):
        """API 应拒绝缺少 content 字段的请求，返回 422"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"creator_id": "u1"})
        assert resp.status_code == 422

    async def test_api_rejects_missing_creator_id(self):
        """API 应拒绝缺少 creator_id 字段的请求，返回 422"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "some content"})
        assert resp.status_code == 422

    async def test_api_accepts_valid_content(self):
        """API 应正常处理有效内容，返回 200"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "A normal video about cooking", "creator_id": "u1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "moderation" in data
        assert "is_safe" in data["moderation"]

    async def test_api_422_contains_error_detail(self):
        """422 响应体中应包含错误详情"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "  ", "creator_id": "u1"})
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body

    async def test_api_strips_surrounding_whitespace(self):
        """首尾有空格的有效内容应被 strip 后正常处理"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/moderate", json={"content": "  valid content  ", "creator_id": "u1"})
        assert resp.status_code == 200
