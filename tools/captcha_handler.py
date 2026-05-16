# -*- coding: utf-8 -*-
"""
验证码检测与处理模块
检测页面中的验证码，支持暂停等待人工处理或自动重试
"""

import asyncio
import time
from enum import Enum
from typing import Optional
from playwright.async_api import Page
from tools import utils


class CaptchaType(Enum):
    """验证码类型"""
    SLIDE = "slide"           # 滑块验证码
    CLICK = "click"           # 点选验证码
    SMS = "sms"               # 短信验证码
    GEETEST = "geetest"       # 极验验证码
    UNKNOWN = "unknown"       # 未知类型


class CaptchaStrategy(Enum):
    """验证码处理策略"""
    PAUSE = "pause"           # 暂停等待人工处理
    RETRY = "retry"           # 重试请求
    SKIP = "skip"             # 跳过当前项
    ABORT = "abort"           # 终止爬取


class CaptchaHandler:
    """验证码处理器"""
    
    # 常见验证码元素选择器
    CAPTCHA_SELECTORS = (
        # 极验
        ".geetest_panel",
        ".geetest_widget",
        "#geetestcaptcha",
        # 腾讯验证码
        "#tcaptcha_iframe",
        ".tc-fg-item",
        # 网易易盾
        ".yidun_modal",
        ".yidun_panel",
        # 通用滑块
        ".captcha-slider",
        ".slide-verify",
        "#captcha",
        ".verify-wrap",
        # 抖音特定
        ".captcha_verify_container",
        "#captcha_container",
        ".verify-captcha",
    )
    
    def __init__(
        self,
        page: Page,
        strategy: CaptchaStrategy = CaptchaStrategy.PAUSE,
        max_wait_time: int = 300,
        check_interval: float = 2.0,
        max_retries: int = 3,
    ):
        """
        Args:
            page: Playwright Page 实例
            strategy: 验证码处理策略
            max_wait_time: 暂停策略下的最大等待时间（秒）
            check_interval: 检查验证码是否消失的间隔（秒）
            max_retries: 重试策略下的最大重试次数
        """
        self.page = page
        self.strategy = strategy
        self.max_wait_time = max_wait_time
        self.check_interval = check_interval
        self.max_retries = max_retries
        
        self.captcha_detected_count = 0
        self.captcha_resolved_count = 0
        self.last_captcha_time: Optional[float] = None
    
    async def detect_captcha(self) -> Optional[CaptchaType]:
        """检测页面中是否存在验证码"""
        for selector in self.CAPTCHA_SELECTORS:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    # 判断验证码类型
                    if "geetest" in selector.lower():
                        return CaptchaType.GEETEST
                    elif "slide" in selector.lower():
                        return CaptchaType.SLIDE
                    elif "sms" in selector.lower():
                        return CaptchaType.SMS
                    else:
                        return CaptchaType.UNKNOWN
            except Exception:
                continue
        
        # 额外检查：页面标题或文本中是否包含验证码相关关键词
        try:
            page_text = await self.page.evaluate("() => document.body.innerText")
            captcha_keywords = ["验证码", "captcha", "verify", "请完成验证", "人机识别"]
            for keyword in captcha_keywords:
                if keyword in page_text.lower():
                    return CaptchaType.UNKNOWN
        except Exception:
            pass
        
        return None
    
    async def wait_for_captcha_resolved(self) -> bool:
        """等待验证码被解决"""
        start_time = time.time()
        
        while True:
            captcha = await self.detect_captcha()
            if captcha is None:
                self.captcha_resolved_count += 1
                utils.logger.info("[CaptchaHandler] 验证码已解决")
                return True
            
            elapsed = time.time() - start_time
            if elapsed > self.max_wait_time:
                utils.logger.warning(
                    f"[CaptchaHandler] 等待验证码超时 ({self.max_wait_time}s)"
                )
                return False
            
            utils.logger.info(
                f"[CaptchaHandler] 检测到 {captcha.value} 验证码，"
                f"等待人工处理... ({elapsed:.0f}s / {self.max_wait_time}s)"
            )
            await asyncio.sleep(self.check_interval)
    
    async def handle_captcha(self) -> bool:
        """
        处理验证码
        Returns: True 表示可以继续，False 表示应该停止
        """
        captcha = await self.detect_captcha()
        if captcha is None:
            return True
        
        self.captcha_detected_count += 1
        self.last_captcha_time = time.time()
        
        utils.logger.warning(
            f"[CaptchaHandler] 检测到验证码: {captcha.value}, "
            f"策略: {self.strategy.value}, "
            f"累计检测: {self.captcha_detected_count} 次"
        )
        
        if self.strategy == CaptchaStrategy.PAUSE:
            return await self._handle_pause()
        elif self.strategy == CaptchaStrategy.RETRY:
            return await self._handle_retry()
        elif self.strategy == CaptchaStrategy.SKIP:
            return self._handle_skip()
        elif self.strategy == CaptchaStrategy.ABORT:
            return self._handle_abort()
        
        return False
    
    async def _handle_pause(self) -> bool:
        """暂停策略：等待人工处理"""
        utils.logger.info(
            "[CaptchaHandler] 暂停等待人工处理验证码，"
            f"最大等待时间: {self.max_wait_time}s"
        )
        
        resolved = await self.wait_for_captcha_resolved()
        if resolved:
            # 验证码解决后等待一小段时间，让页面加载
            await asyncio.sleep(2)
            return True
        
        utils.logger.error("[CaptchaHandler] 等待验证码处理超时")
        return False
    
    async def _handle_retry(self) -> bool:
        """重试策略：刷新页面重试"""
        for attempt in range(self.max_retries):
            utils.logger.info(
                f"[CaptchaHandler] 尝试刷新页面重试 ({attempt + 1}/{self.max_retries})"
            )
            
            try:
                await self.page.reload(wait_until="networkidle")
                await asyncio.sleep(3)
                
                captcha = await self.detect_captcha()
                if captcha is None:
                    utils.logger.info("[CaptchaHandler] 重试成功，验证码已消失")
                    return True
            except Exception as e:
                utils.logger.error(f"[CaptchaHandler] 重试失败: {e}")
        
        utils.logger.error("[CaptchaHandler] 重试次数已用完")
        return False
    
    def _handle_skip(self) -> bool:
        """跳过策略：跳过当前项"""
        utils.logger.warning("[CaptchaHandler] 跳过当前项")
        return True
    
    def _handle_abort(self) -> bool:
        """终止策略：停止爬取"""
        utils.logger.error("[CaptchaHandler] 终止爬取")
        return False
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "captcha_detected": self.captcha_detected_count,
            "captcha_resolved": self.captcha_resolved_count,
            "last_captcha_time": self.last_captcha_time,
            "strategy": self.strategy.value,
        }

