from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import msg_handler

from capstone_motor.command_receiver import MotorCommandReceiver
from capstone_motor.heartbeat_publisher import HeartbeatPublisher
from capstone_motor.motor_driver import MotorHardwareController
from capstone_motor.state_store import RuntimeStateStore


class MotorComponentApp:
    def __init__(
        self,
        command_receiver: MotorCommandReceiver,
        heartbeat_publisher: HeartbeatPublisher,
        motor_controller: MotorHardwareController,
        state_store: RuntimeStateStore,
        init_retry_interval_sec: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.command_receiver = command_receiver
        self.heartbeat_publisher = heartbeat_publisher
        self.motor_controller = motor_controller
        self.state_store = state_store
        self.init_retry_interval_sec = init_retry_interval_sec
        self.logger = logger or logging.getLogger(__name__)

    async def run(self) -> None:
        # Start in DEAD state and pause hardware polling until init succeeds.
        hardware_refresh = self.heartbeat_publisher.refresh_status
        self.heartbeat_publisher.refresh_status = None
        await self.state_store.mark_error(motor_status=msg_handler.MotorState.DEAD)

        try:
            async with asyncio.TaskGroup() as task_group:
                task_group.create_task(
                    self.heartbeat_publisher.run(),
                    name="motor-heartbeat-publisher",
                )
                task_group.create_task(
                    self._initialize_with_retry(task_group, hardware_refresh),
                    name="motor-init-retry",
                )
        finally:
            await self.motor_controller.robot.cleanup_all()

    async def _initialize_with_retry(
        self,
        task_group: asyncio.TaskGroup,
        hardware_refresh: Callable[[], Awaitable[None]] | None,
    ) -> None:
        while True:
            try:
                await self.motor_controller.initialize()
                self.logger.info("motor hardware initialized")
                break
            except Exception:
                self.logger.exception(
                    "motor hardware initialization failed; retrying in %.1fs",
                    self.init_retry_interval_sec,
                )
                await asyncio.sleep(self.init_retry_interval_sec)

        if hardware_refresh is not None:
            await hardware_refresh()
            self.heartbeat_publisher.refresh_status = hardware_refresh

        task_group.create_task(
            self.command_receiver.run(),
            name="motor-command-receiver",
        )
