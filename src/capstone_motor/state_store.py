from __future__ import annotations

import asyncio
from copy import deepcopy

import msg_handler

from capstone_motor.models import RuntimeState, resolve_applied_mode_from_status


class RuntimeStateStore:
    def __init__(self, initial_state: RuntimeState | None = None) -> None:
        self._state = initial_state or RuntimeState()
        self._lock = asyncio.Lock()

    async def snapshot(self) -> RuntimeState:
        async with self._lock:
            return deepcopy(self._state)

    async def record_received_command(
        self,
        message: msg_handler.MotorMessage,
    ) -> None:
        async with self._lock:
            self._state.desired_mode = message.ordered_mode
            self._state.is_override_mode = message.is_override_mode

    async def mark_applied_order(
        self,
        *,
        motor_status: msg_handler.MotorState,
    ) -> None:
        async with self._lock:
            self._state.applied_mode = resolve_applied_mode_from_status(motor_status)
            self._state.motor_status = motor_status

    async def set_motor_status(
        self,
        motor_status: msg_handler.MotorState,
    ) -> None:
        async with self._lock:
            self._state.applied_mode = resolve_applied_mode_from_status(motor_status)
            self._state.motor_status = motor_status

    async def mark_error(
        self,
        *,
        motor_status: msg_handler.MotorState = msg_handler.MotorState.ERROR,
    ) -> None:
        async with self._lock:
            self._state.applied_mode = resolve_applied_mode_from_status(motor_status)
            self._state.motor_status = motor_status
