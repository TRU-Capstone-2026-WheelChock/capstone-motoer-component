from __future__ import annotations

import asyncio
import logging

import msg_handler
from capstone_motor.motors import Robot

from capstone_motor.config import DriverConfig


class MotorHardwareController:
    """Place all direct motor hardware code in this class."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.step_1=[17,18,27,22]
        self.step_2=[23,24,25,16]
        self.robot: Robot | None = None
        self.deploy_direction = 1
        self._status: msg_handler.MotorState = msg_handler.MotorState.STARTING

    async def initialize(self) -> None:
        """Reserve GPIO, serial, CAN, or any other hardware resources here."""
        self.robot = Robot(self.step_1, self.step_2)
        self._status = msg_handler.MotorState.FOLDED

    async def apply_order(
        self,
        ordered_mode: msg_handler.MotorState,
    ) -> msg_handler.MotorState:
        if ordered_mode == msg_handler.MotorState.DEPLOYING:
            return await self.deploy()
        if ordered_mode == msg_handler.MotorState.FOLDING:
            return await self.fold()
        raise ValueError(f"Unsupported motor order: {ordered_mode}")

    async def deploy(self) -> msg_handler.MotorState:
        if self.robot is None:
            raise RuntimeError("motor hardware not initialized")
        self.logger.info("deploy Order Received! @ Deploy")
        self.deploy_direction = 1
        self._status = msg_handler.MotorState.DEPLOYING
        await self.robot.deploy(self.deploy_direction)
        self.logger.info("deploy Order FINISHED @ deploy, Changing State")
        self._status = msg_handler.MotorState.DEPLOYED
        return self._status

    async def fold(self) -> msg_handler.MotorState:
        if self.robot is None:
            raise RuntimeError("motor hardware not initialized")
        self.deploy_direction = -1
        self.logger.info("FOLD Order Received! @ FOLD")
        self._status = msg_handler.MotorState.FOLDING
        await self.robot.deploy(self.deploy_direction)
        self.logger.info("FOLD Order FINISHED @ FOLD")
        self._status = msg_handler.MotorState.FOLDED
        return self._status

    async def read_status(self) -> msg_handler.MotorState:
        return self._status

    async def stop(self) -> None:
        """Release hardware resources or stop the motor safely here."""
        if self.robot is not None:
            self.robot.cleanup_all()
            self.robot = None

class MockMotorController(MotorHardwareController):
    """Mock motor controller for local development.

    Behavior:
    - DEPLOYING takes `motion_duration_sec` seconds, then becomes DEPLOYED.
    - FOLDING takes `motion_duration_sec` seconds, then becomes FOLDED.
    - If the opposite order arrives during motion, it is queued and runs after
      the current motion fully completes.
    - If the current direction is requested again, any queued reverse order is
      cleared so the latest command wins.
    """

    def __init__(
        self,
        *,
        motion_duration_sec: float = 5.0,
        initial_status: msg_handler.MotorState = msg_handler.MotorState.FOLDED,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(logger=logger)
        self.motion_duration_sec = motion_duration_sec
        self._status = initial_status
        self._queued_order: msg_handler.MotorState | None = None
        self._motion_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self._lock:
            if self._status == msg_handler.MotorState.STARTING:
                self._status = msg_handler.MotorState.FOLDED
            self.logger.info("mock motor initialized with status=%s", self._status)

    async def apply_order(
        self,
        ordered_mode: msg_handler.MotorState,
    ) -> msg_handler.MotorState:
        if ordered_mode not in {
            msg_handler.MotorState.DEPLOYING,
            msg_handler.MotorState.FOLDING,
        }:
            raise ValueError(f"Unsupported motor order: {ordered_mode}")

        async with self._lock:
            if self._motion_task is not None and not self._motion_task.done():
                if self._status == ordered_mode:
                    self._queued_order = None
                    self.logger.info(
                        "mock motor keeps current motion=%s and clears queued reverse order",
                        self._status,
                    )
                    return self._status

                self._queued_order = ordered_mode
                self.logger.info(
                    "mock motor queued next order=%s while current motion=%s is running",
                    ordered_mode,
                    self._status,
                )
                return self._status

            if self._status == self._terminal_status_for_order(ordered_mode):
                self.logger.info("mock motor already at target for order=%s", ordered_mode)
                return self._status

            self._status = ordered_mode
            self._motion_task = asyncio.create_task(
                self._run_motion_loop(ordered_mode),
                name=f"mock-motor-{ordered_mode.lower()}",
            )
            self.logger.info(
                "mock motor started order=%s duration=%.1fs",
                ordered_mode,
                self.motion_duration_sec,
            )
            return self._status

    async def deploy(self) -> msg_handler.MotorState:
        return await self.apply_order(msg_handler.MotorState.DEPLOYING)

    async def fold(self) -> msg_handler.MotorState:
        return await self.apply_order(msg_handler.MotorState.FOLDING)

    async def read_status(self) -> msg_handler.MotorState:
        async with self._lock:
            return self._status

    async def stop(self) -> None:
        async with self._lock:
            task = self._motion_task
            self._motion_task = None
            self._queued_order = None

        if task is None:
            return

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            self.logger.info("mock motor motion task cancelled")

    def _terminal_status_for_order(
        self,
        ordered_mode: msg_handler.MotorState,
    ) -> msg_handler.MotorState:
        if ordered_mode == msg_handler.MotorState.DEPLOYING:
            return msg_handler.MotorState.DEPLOYED
        if ordered_mode == msg_handler.MotorState.FOLDING:
            return msg_handler.MotorState.FOLDED
        raise ValueError(f"Unsupported motor order: {ordered_mode}")

    async def _run_motion_loop(self, first_order: msg_handler.MotorState) -> None:
        current_order = first_order
        try:
            while True:
                self.logger.info(
                    "mock motor executing order=%s for %.1fs",
                    current_order,
                    self.motion_duration_sec,
                )
                await asyncio.sleep(self.motion_duration_sec)

                async with self._lock:
                    self._status = self._terminal_status_for_order(current_order)
                    self.logger.info("mock motor reached status=%s", self._status)

                    queued_order = self._queued_order
                    self._queued_order = None

                    if queued_order is None:
                        self._motion_task = None
                        return

                    if self._status == self._terminal_status_for_order(queued_order):
                        self._motion_task = None
                        return

                    self._status = queued_order
                    current_order = queued_order
                    self.logger.info(
                        "mock motor starting queued order=%s after completing previous motion",
                        current_order,
                    )
        except asyncio.CancelledError:
            raise


def build_motor_controller(
    driver_config: DriverConfig,
    *,
    logger: logging.Logger | None = None,
) -> MotorHardwareController:
    if driver_config.kind == "mock":
        return MockMotorController(
            motion_duration_sec=driver_config.motion_duration_sec,
            initial_status=driver_config.initial_status,
            logger=logger,
        )
    if driver_config.kind == "hardware":
        return MotorHardwareController(logger=logger)

    raise ValueError(f"Unsupported driver kind: {driver_config.kind}")
