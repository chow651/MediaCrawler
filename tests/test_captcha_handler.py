# -*- coding: utf-8 -*-
"""
验证码检测与处理模块测试用例
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tools.captcha_handler import CaptchaHandler, CaptchaType, CaptchaStrategy


@pytest.fixture
def mock_page():
    """创建模拟的 Playwright Page"""
    page = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.evaluate = AsyncMock(return_value="")
    page.reload = AsyncMock()
    return page


@pytest.fixture
def captcha_handler(mock_page):
    """创建验证码处理器实例"""
    return CaptchaHandler(
        page=mock_page,
        strategy=CaptchaStrategy.PAUSE,
        max_wait_time=5,
        check_interval=0.1,
        max_retries=3,
    )


class TestCaptchaType:
    """测试验证码类型枚举"""

    def test_enum_values(self):
        """测试枚举值"""
        assert CaptchaType.SLIDE.value == "slide"
        assert CaptchaType.CLICK.value == "click"
        assert CaptchaType.SMS.value == "sms"
        assert CaptchaType.GEETEST.value == "geetest"
        assert CaptchaType.UNKNOWN.value == "unknown"


class TestCaptchaStrategy:
    """测试验证码处理策略枚举"""

    def test_enum_values(self):
        """测试枚举值"""
        assert CaptchaStrategy.PAUSE.value == "pause"
        assert CaptchaStrategy.RETRY.value == "retry"
        assert CaptchaStrategy.SKIP.value == "skip"
        assert CaptchaStrategy.ABORT.value == "abort"


class TestCaptchaHandlerInit:
    """测试初始化"""

    def test_default_init(self, mock_page):
        """测试默认参数初始化"""
        handler = CaptchaHandler(page=mock_page)
        assert handler.strategy == CaptchaStrategy.PAUSE
        assert handler.max_wait_time == 300
        assert handler.check_interval == 2.0
        assert handler.max_retries == 3
        assert handler.captcha_detected_count == 0
        assert handler.captcha_resolved_count == 0
        assert handler.last_captcha_time is None

    def test_custom_init(self, mock_page):
        """测试自定义参数初始化"""
        handler = CaptchaHandler(
            page=mock_page,
            strategy=CaptchaStrategy.RETRY,
            max_wait_time=60,
            check_interval=1.0,
            max_retries=5,
        )
        assert handler.strategy == CaptchaStrategy.RETRY
        assert handler.max_wait_time == 60
        assert handler.check_interval == 1.0
        assert handler.max_retries == 5


@pytest.mark.asyncio
async def test_no_captcha(captcha_handler, mock_page):
    """测试没有验证码"""
    mock_page.query_selector.return_value = None
    result = await captcha_handler.detect_captcha()
    assert result is None


@pytest.mark.asyncio
async def test_geetest_captcha(captcha_handler, mock_page):
    """测试极验验证码"""
    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    async def mock_query_selector(selector):
        if "geetest" in selector:
            return mock_element
        return None

    mock_page.query_selector = mock_query_selector
    result = await captcha_handler.detect_captcha()
    assert result == CaptchaType.GEETEST


@pytest.mark.asyncio
async def test_slide_captcha(captcha_handler, mock_page):
    """测试滑块验证码"""
    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    async def mock_query_selector(selector):
        if "slide" in selector:
            return mock_element
        return None

    mock_page.query_selector = mock_query_selector
    result = await captcha_handler.detect_captcha()
    assert result == CaptchaType.SLIDE


@pytest.mark.asyncio
async def test_unknown_captcha(captcha_handler, mock_page):
    """测试未知验证码"""
    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    async def mock_query_selector(selector):
        # 只匹配通用验证码选择器，不匹配极验和滑块
        if selector in ["#captcha", ".verify-wrap", ".captcha_verify_container", "#captcha_container", ".verify-captcha"]:
            return mock_element
        return None

    mock_page.query_selector = mock_query_selector
    result = await captcha_handler.detect_captcha()
    assert result == CaptchaType.UNKNOWN


@pytest.mark.asyncio
async def test_captcha_by_page_text(captcha_handler, mock_page):
    """测试通过页面文本检测验证码"""
    async def mock_query_selector(selector):
        return None

    mock_page.query_selector = mock_query_selector
    mock_page.evaluate = AsyncMock(return_value="请完成验证")

    result = await captcha_handler.detect_captcha()
    assert result == CaptchaType.UNKNOWN


@pytest.mark.asyncio
async def test_handle_no_captcha(captcha_handler, mock_page):
    """测试没有验证码时处理"""
    async def mock_query_selector(selector):
        return None

    mock_page.query_selector = mock_query_selector
    result = await captcha_handler.handle_captcha()
    assert result is True
    assert captcha_handler.captcha_detected_count == 0


@pytest.mark.asyncio
async def test_handle_with_skip_strategy(mock_page):
    """测试跳过策略"""
    handler = CaptchaHandler(
        page=mock_page,
        strategy=CaptchaStrategy.SKIP,
    )

    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    async def mock_query_selector(selector):
        return mock_element

    mock_page.query_selector = mock_query_selector

    result = await handler.handle_captcha()
    assert result is True
    assert handler.captcha_detected_count == 1


@pytest.mark.asyncio
async def test_handle_with_abort_strategy(mock_page):
    """测试终止策略"""
    handler = CaptchaHandler(
        page=mock_page,
        strategy=CaptchaStrategy.ABORT,
    )

    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    async def mock_query_selector(selector):
        return mock_element

    mock_page.query_selector = mock_query_selector

    result = await handler.handle_captcha()
    assert result is False
    assert handler.captcha_detected_count == 1


@pytest.mark.asyncio
async def test_resolved_immediately(captcha_handler, mock_page):
    """测试立即解决"""
    async def mock_query_selector(selector):
        return None

    mock_page.query_selector = mock_query_selector
    result = await captcha_handler.wait_for_captcha_resolved()
    assert result is True
    assert captcha_handler.captcha_resolved_count == 1


@pytest.mark.asyncio
async def test_timeout(captcha_handler, mock_page):
    """测试超时"""
    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    async def mock_query_selector(selector):
        return mock_element

    mock_page.query_selector = mock_query_selector
    captcha_handler.max_wait_time = 0.2
    captcha_handler.check_interval = 0.05

    result = await captcha_handler.wait_for_captcha_resolved()
    assert result is False


@pytest.mark.asyncio
async def test_resolved_after_delay(captcha_handler, mock_page):
    """测试延迟后解决"""
    call_count = 0

    async def mock_query_selector(selector):
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            return None
        mock_element = AsyncMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        return mock_element

    mock_page.query_selector = mock_query_selector
    captcha_handler.check_interval = 0.05

    result = await captcha_handler.wait_for_captcha_resolved()
    assert result is True
    assert captcha_handler.captcha_resolved_count == 1


@pytest.mark.asyncio
async def test_retry_success(mock_page):
    """测试重试成功"""
    handler = CaptchaHandler(
        page=mock_page,
        strategy=CaptchaStrategy.RETRY,
        max_retries=3,
        check_interval=0.01,
    )

    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    call_count = 0

    async def mock_query_selector(selector):
        nonlocal call_count
        call_count += 1
        if call_count >= 4:  # 第一次检测 + 重试后检测
            return None
        return mock_element

    mock_page.query_selector = mock_query_selector

    result = await handler.handle_captcha()
    assert result is True


@pytest.mark.asyncio
async def test_retry_exhausted(mock_page):
    """测试重试次数用完"""
    handler = CaptchaHandler(
        page=mock_page,
        strategy=CaptchaStrategy.RETRY,
        max_retries=2,
        check_interval=0.01,
    )

    mock_element = AsyncMock()
    mock_element.is_visible = AsyncMock(return_value=True)

    async def mock_query_selector(selector):
        return mock_element

    mock_page.query_selector = mock_query_selector

    result = await handler.handle_captcha()
    assert result is False


class TestGetStats:
    """测试统计信息"""

    def test_initial_stats(self, captcha_handler):
        """测试初始统计"""
        stats = captcha_handler.get_stats()
        assert stats["captcha_detected"] == 0
        assert stats["captcha_resolved"] == 0
        assert stats["last_captcha_time"] is None
        assert stats["strategy"] == "pause"

    def test_stats_after_detection(self, captcha_handler):
        """测试检测后的统计"""
        captcha_handler.captcha_detected_count = 3
        captcha_handler.captcha_resolved_count = 2
        captcha_handler.last_captcha_time = 1234567890.0

        stats = captcha_handler.get_stats()
        assert stats["captcha_detected"] == 3
        assert stats["captcha_resolved"] == 2
        assert stats["last_captcha_time"] == 1234567890.0
