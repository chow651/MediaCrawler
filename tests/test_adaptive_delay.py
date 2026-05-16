# -*- coding: utf-8 -*-
"""
自适应延迟控制模块测试用例
"""

import asyncio
import time
import pytest
from tools.adaptive_delay import AdaptiveDelay


class TestAdaptiveDelayInit:
    """测试初始化"""

    def test_default_init(self):
        """测试默认参数初始化"""
        delay = AdaptiveDelay()
        assert delay.base_delay == 2.0
        assert delay.min_delay == 0.5
        assert delay.max_delay == 30.0
        assert delay.backoff_factor == 2.0
        assert delay.recovery_factor == 0.5
        assert delay.success_threshold == 5
        assert delay.current_delay == 2.0
        assert delay.consecutive_success == 0
        assert delay.consecutive_errors == 0
        assert delay.total_requests == 0
        assert delay.total_errors == 0

    def test_custom_init(self):
        """测试自定义参数初始化"""
        delay = AdaptiveDelay(
            base_delay=1.0,
            min_delay=0.1,
            max_delay=60.0,
            backoff_factor=3.0,
            recovery_factor=0.3,
            success_threshold=10,
        )
        assert delay.base_delay == 1.0
        assert delay.min_delay == 0.1
        assert delay.max_delay == 60.0
        assert delay.backoff_factor == 3.0
        assert delay.recovery_factor == 0.3
        assert delay.success_threshold == 10


class TestClampDelay:
    """测试延迟范围限制"""

    def test_within_range(self):
        """测试在有效范围内的值"""
        delay = AdaptiveDelay(min_delay=0.5, max_delay=30.0)
        assert delay._clamp_delay(2.0) == 2.0
        assert delay._clamp_delay(10.0) == 10.0

    def test_below_min(self):
        """测试低于最小值"""
        delay = AdaptiveDelay(min_delay=0.5, max_delay=30.0)
        assert delay._clamp_delay(0.1) == 0.5

    def test_above_max(self):
        """测试高于最大值"""
        delay = AdaptiveDelay(min_delay=0.5, max_delay=30.0)
        assert delay._clamp_delay(50.0) == 30.0

    def test_boundary_values(self):
        """测试边界值"""
        delay = AdaptiveDelay(min_delay=0.5, max_delay=30.0)
        assert delay._clamp_delay(0.5) == 0.5
        assert delay._clamp_delay(30.0) == 30.0


class TestOnSuccess:
    """测试成功回调"""

    def test_single_success(self):
        """测试单次成功"""
        delay = AdaptiveDelay()
        delay.on_success()
        assert delay.consecutive_success == 1
        assert delay.consecutive_errors == 0
        assert delay.total_requests == 1

    def test_multiple_success(self):
        """测试多次成功"""
        delay = AdaptiveDelay()
        for _ in range(3):
            delay.on_success()
        assert delay.consecutive_success == 3
        assert delay.total_requests == 3

    def test_recovery_after_threshold(self):
        """测试达到阈值后恢复"""
        delay = AdaptiveDelay(base_delay=2.0, recovery_factor=0.5, success_threshold=5)
        delay.current_delay = 10.0  # 模拟退避后的延迟

        # 连续成功 5 次
        for _ in range(5):
            delay.on_success()

        # 延迟应该恢复
        assert delay.current_delay < 10.0

    def test_reset_after_recovery_to_base(self):
        """测试恢复到基础延迟后重置计数"""
        delay = AdaptiveDelay(base_delay=2.0, recovery_factor=0.5, success_threshold=5)
        delay.current_delay = 2.5

        # 连续成功 5 次
        for _ in range(5):
            delay.on_success()

        # 延迟应该恢复到基础值
        assert delay.current_delay == 2.0
        assert delay.consecutive_success == 0


class TestOnRateLimit:
    """测试限流回调"""

    def test_rate_limit_without_retry_after(self):
        """测试没有 Retry-After 的限流"""
        delay = AdaptiveDelay(base_delay=2.0, backoff_factor=2.0)
        delay.on_rate_limit()
        assert delay.current_delay == 4.0
        assert delay.consecutive_errors == 1
        assert delay.total_errors == 1
        assert delay.consecutive_success == 0

    def test_rate_limit_with_retry_after(self):
        """测试有 Retry-After 的限流"""
        delay = AdaptiveDelay()
        delay.on_rate_limit(retry_after=10.0)
        assert delay.current_delay == 10.0

    def test_multiple_rate_limits(self):
        """测试多次限流"""
        delay = AdaptiveDelay(base_delay=2.0, backoff_factor=2.0, max_delay=30.0)
        delay.on_rate_limit()
        delay.on_rate_limit()
        assert delay.current_delay == 8.0
        assert delay.consecutive_errors == 2

    def test_rate_limit_max_delay(self):
        """测试限流不超过最大延迟"""
        delay = AdaptiveDelay(base_delay=20.0, backoff_factor=2.0, max_delay=30.0)
        delay.on_rate_limit()
        assert delay.current_delay == 30.0


class TestOnError:
    """测试错误回调"""

    def test_error_429(self):
        """测试 429 错误"""
        delay = AdaptiveDelay(base_delay=2.0, backoff_factor=2.0)
        delay.on_error(status_code=429)
        assert delay.current_delay == 4.0
        assert delay.total_errors == 1

    def test_error_403(self):
        """测试 403 错误"""
        delay = AdaptiveDelay(base_delay=2.0, backoff_factor=2.0)
        delay.on_error(status_code=403)
        assert delay.current_delay == 8.0  # backoff_factor * 2

    def test_error_500(self):
        """测试 500 错误"""
        delay = AdaptiveDelay(base_delay=2.0)
        delay.on_error(status_code=500)
        assert delay.current_delay == 3.0  # 2.0 * 1.5

    def test_error_generic(self):
        """测试通用错误"""
        delay = AdaptiveDelay(base_delay=2.0)
        delay.on_error(status_code=0)
        assert delay.consecutive_errors == 1
        assert delay.total_requests == 1


class TestGetStats:
    """测试统计信息"""

    def test_initial_stats(self):
        """测试初始统计"""
        delay = AdaptiveDelay()
        stats = delay.get_stats()
        assert stats["current_delay"] == 2.0
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0
        assert stats["error_rate"] == 0.0
        assert stats["consecutive_success"] == 0
        assert stats["consecutive_errors"] == 0

    def test_stats_after_operations(self):
        """测试操作后的统计"""
        delay = AdaptiveDelay()
        delay.on_success()
        delay.on_success()
        delay.on_rate_limit()

        stats = delay.get_stats()
        assert stats["total_requests"] == 2
        assert stats["total_errors"] == 1
        assert stats["consecutive_success"] == 0
        assert stats["consecutive_errors"] == 1
        assert stats["error_rate"] == pytest.approx(0.5, rel=0.01)


class TestReset:
    """测试重置功能"""

    def test_reset(self):
        """测试重置"""
        delay = AdaptiveDelay(base_delay=2.0)
        delay.on_rate_limit()
        delay.on_success()
        delay.on_success()
        delay.last_request_time = time.time()

        delay.reset()
        assert delay.current_delay == 2.0
        assert delay.consecutive_success == 0
        assert delay.consecutive_errors == 0
        assert delay.last_request_time == 0.0


@pytest.mark.asyncio
async def test_first_wait_no_delay():
    """测试首次等待不延迟"""
    delay = AdaptiveDelay(base_delay=1.0)
    start = time.time()
    await delay.wait()
    elapsed = time.time() - start
    assert elapsed < 0.1  # 首次等待几乎不延迟


@pytest.mark.asyncio
async def test_wait_respects_delay():
    """测试等待遵守延迟"""
    delay = AdaptiveDelay(base_delay=0.5)
    delay.last_request_time = time.time()
    start = time.time()
    await delay.wait()
    elapsed = time.time() - start
    assert elapsed >= 0.3  # 应该等待至少部分延迟时间


@pytest.mark.asyncio
async def test_wait_no_delay_if_enough_time_passed():
    """测试如果已经过了足够时间则不延迟"""
    delay = AdaptiveDelay(base_delay=1.0)
    delay.last_request_time = time.time() - 2.0  # 2 秒前
    start = time.time()
    await delay.wait()
    elapsed = time.time() - start
    assert elapsed < 0.1
