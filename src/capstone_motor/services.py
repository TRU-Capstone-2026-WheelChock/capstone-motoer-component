from __future__ import annotations

import logging

import msg_handler

from capstone_motor.motor_driver import MotorHardwareController
from capstone_motor.state_store import RuntimeStateStore


class MotorCommandService:
    def __init__(
        self,
        state_store: RuntimeStateStore,
        motor_controller: MotorHardwareController,
        logger: logging.Logger | None = None,
    ) -> None:
        self.state_store = state_store
        self.motor_controller = motor_controller
        self.logger = logger or logging.getLogger(__name__)

    async def process_command(self, message: msg_handler.MotorMessage) -> None:
        await self.state_store.record_received_command(message)

        try:
            applied_status = await self.motor_controller.apply_order(
                ordered_mode=message.ordered_mode,
                is_override=message.is_override_mode
                )
        except Exception:
            await self.state_store.mark_error()
            raise

        await self.state_store.mark_applied_order(
            motor_status=applied_status,
        )

    async def refresh_status_from_hardware(self) -> None:
        status = await self.motor_controller.read_status()
        await self.state_store.set_motor_status(status)
