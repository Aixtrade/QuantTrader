"""熔断器实现

提供服务熔断保护，防止故障扩散。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（试探）


@dataclass
class CircuitStats:
    """熔断器统计"""

    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[float]
    last_state_change: float


class CircuitBreaker:
    """熔断器

    状态转换：
    - CLOSED -> OPEN: 失败次数达到阈值
    - OPEN -> HALF_OPEN: 等待超时后自动进入
    - HALF_OPEN -> CLOSED: 试探请求成功
    - HALF_OPEN -> OPEN: 试探请求失败
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 30.0,
        name: str = "default",
    ) -> None:
        """
        Args:
            failure_threshold: 触发熔断的连续失败次数
            success_threshold: 半开状态下恢复所需的成功次数
            timeout: 熔断超时时间（秒）
            name: 熔断器名称（用于日志）
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change = time.time()

    @property
    def state(self) -> CircuitState:
        """当前状态（自动检查是否应从 OPEN 转为 HALF_OPEN）"""
        if self._state == CircuitState.OPEN:
            if self._should_try_reset():
                self._set_state(CircuitState.HALF_OPEN)
        return self._state

    def _should_try_reset(self) -> bool:
        """检查是否应该尝试重置"""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.timeout

    def _set_state(self, state: CircuitState) -> None:
        """设置状态"""
        if self._state != state:
            self._state = state
            self._last_state_change = time.time()
            if state == CircuitState.HALF_OPEN:
                self._success_count = 0

    def allow_request(self) -> bool:
        """检查是否允许请求"""
        current_state = self.state  # 会自动检查 OPEN -> HALF_OPEN

        if current_state == CircuitState.CLOSED:
            return True
        elif current_state == CircuitState.HALF_OPEN:
            return True  # 允许试探请求
        else:  # OPEN
            return False

    def record_success(self) -> None:
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._set_state(CircuitState.CLOSED)
                self._failure_count = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # 半开状态下失败，立即熔断
            self._set_state(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._set_state(CircuitState.OPEN)

    def reset(self) -> None:
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._last_state_change = time.time()

    def stats(self) -> CircuitStats:
        """获取熔断器统计"""
        return CircuitStats(
            state=self.state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            last_state_change=self._last_state_change,
        )

    def is_open(self) -> bool:
        """是否处于熔断状态"""
        return self.state == CircuitState.OPEN


class CircuitBreakerOpenError(Exception):
    """熔断器开启时抛出的异常"""

    def __init__(self, breaker: CircuitBreaker):
        self.breaker = breaker
        super().__init__(
            f"Circuit breaker '{breaker.name}' is open. "
            f"Retry after {breaker.timeout} seconds."
        )
