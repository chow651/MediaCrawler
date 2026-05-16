# -*- coding: utf-8 -*-
"""
自适应请求频率控制模块
根据平台响应状态动态调整请求间隔，避免触发反爬机制
"""

import asyncio
import random
import time
from typing import Optional
from tools import utils


class AdaptiveDelay:
    """自适应延迟控制器"""
    
    def __init__(
        self,
        base_delay: float = 2.0,
        min_delay: float = 0.5,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        recovery_factor: float = 0.5,
        success_threshold: int = 5,
    ):
        """
        Args:
            base_delay: 基础延迟秒数
            min_delay: 最小延迟秒数
            max_delay: 最大延迟秒数
            backoff_factor: 触发限流时的退避倍数
            recovery_factor: 连续成功后的恢复倍数
            success_threshold: 触发恢复所需的连续成功次数
        """
        self.base_delay = base_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.success_threshold = success_threshold
        
        self.current_delay = base_delay
        self.consecutive_success = 0
        self.consecutive_errors = 0
        self.last_request_time = 0.0
        self.total_requests = 0
        self.total_errors = 0
        
    def _clamp_delay(self, delay: float) -> float:
        """将延迟限制在有效范围内"""
        return max(self.min_delay, min(delay, self.max_delay))
    
    def on_success(self):
        """请求成功时调用"""
        self.consecutive_success += 1
        self.consecutive_errors = 0
        self.total_requests += 1
        
        # 连续成功达到阈值后，逐步恢复到基础速度
        if self.consecutive_success >= self.success_threshold:
            self.current_delay = self._clamp_delay(
                self.current_delay * self.recovery_factor
            )
            # 恢复后重置计数，避免持续降低
            if self.current_delay <= self.base_delay:
                self.current_delay = self.base_delay
                self.consecutive_success = 0
                
    def on_rate_limit(self, retry_after: Optional[float] = None):
        """触发限流时调用"""
        self.consecutive_errors += 1
        self.consecutive_success = 0
        self.total_errors += 1
        
        if retry_after:
            # 如果平台返回了 Retry-After 头，使用该值
            self.current_delay = self._clamp_delay(retry_after)
        else:
            # 否则使用指数退避
            self.current_delay = self._clamp_delay(
                self.current_delay * self.backoff_factor
            )
        
        utils.logger.warning(
            f"[AdaptiveDelay] 触发限流，当前延迟调整为 {self.current_delay:.1f}s "
            f"(连续错误: {self.consecutive_errors})"
        )
    
    def on_error(self, status_code: int = 0):
        """请求错误时调用"""
        self.consecutive_success = 0
        self.total_requests += 1

        if status_code == 429:
            self.on_rate_limit()
        else:
            self.consecutive_errors += 1
            self.total_errors += 1
            if status_code in (403, 401):
                self.current_delay = self._clamp_delay(
                    self.current_delay * self.backoff_factor * 2
                )
            elif status_code >= 500:
                self.current_delay = self._clamp_delay(
                    self.current_delay * 1.5
                )
    
    async def wait(self):
        """执行自适应等待"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            remaining = self.current_delay - elapsed
            
            if remaining > 0:
                # 添加随机抖动，避免固定间隔被识别
                jitter = remaining * 0.2 * (random.random() * 2 - 1)
                wait_time = max(0, remaining + jitter)
                
                if wait_time > 0:
                    utils.logger.debug(
                        f"[AdaptiveDelay] 等待 {wait_time:.1f}s "
                        f"(当前延迟: {self.current_delay:.1f}s)"
                    )
                    await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "current_delay": round(self.current_delay, 2),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": round(self.total_errors / max(1, self.total_requests), 4),
            "consecutive_success": self.consecutive_success,
            "consecutive_errors": self.consecutive_errors,
        }
    
    def reset(self):
        """重置到初始状态"""
        self.current_delay = self.base_delay
        self.consecutive_success = 0
        self.consecutive_errors = 0
        self.last_request_time = 0.0
