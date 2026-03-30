"""
Pytest 配置：在测试中初始化 FastAPI 的 lifespan 依赖（_service）。

ASGITransport 在某些环境下不会自动触发 app lifespan，
通过 autouse fixture 显式初始化 _service，确保 API 测试可正常运行。
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
from moderation_service import ModerationService


@pytest.fixture(autouse=True)
def initialize_service():
    """在每个测试前确保 _service 已初始化"""
    main._service = ModerationService(openai_key="mock-key", anthropic_key="mock-key")
    yield
    main._service = None
