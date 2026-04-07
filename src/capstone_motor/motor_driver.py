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
        self._lock = asyncio.Lock()
        self._status: msg_handler.MotorState = msg_handler.MotorState.STARTING

    async def initialize(self) -> None:
        """Reserve GPIO, serial, CAN, or any other hardware resources here."""
        self.robot = Robot(self.step_1, self.step_2)
        self._status = msg_handler.MotorState.FOLDED

    async def apply_order(
        self,
        ordered_mode: msg_handler.MotorState,
        is_override: bool = False,
    ) -> msg_handler.MotorState:
        async with self._lock:
            if ordered_mode == msg_handler.MotorState.DEPLOYING and self._status == msg_handler.MotorState.DEPLOYED:
                self.logger.info("Already DEPLOYED, ignoring DEPLOYING order")
                return self._status
            if ordered_mode == msg_handler.MotorState.FOLDING and self._status == msg_handler.MotorState.FOLDED:
                self.logger.info("Already FOLDED, ignoring FOLDING order")
                return self._status
            if self._status in (msg_handler.MotorState.DEPLOYING, msg_handler.MotorState.FOLDING):
                opposite_mode = None
                if self._status == msg_handler.MotorState.DEPLOYING:
                    opposite_mode = msg_handler.MotorState.FOLDING
                elif self._status == msg_handler.MotorState.FOLDING:
                    opposite_mode = msg_handler.MotorState.DEPLOYING

                if is_override and opposite_mode is not None and opposite_mode == ordered_mode:
                    self.logger.info(
                            "Override: reversing direction from %s to %s",
                            self._status, ordered_mode
                        )
                    await self._stop_current_motion()
                    return await self._start_motion(ordered_mode)
                else:
                    self.logger.warning(
                        "Motor is already moving (%s), ignoring new order: %s (override=%s)",
                        self._status, ordered_mode, is_override
                    )
                    return self._status
            if is_override:
                self.logger.info("Override: Ignore all orders")
                return None
            else:
                await self._start_motion(ordered_mode)
    
    async def _stop_current_motion(self) -> None:
        """Cancel the current motion task and stop hardware immediately."""
        if self._current_motion_task is not None and not self._current_motion_task.done():
            self.logger.info("Cancelling current motion task")
            self._current_motion_task.cancel()
            try:
                await self._current_motion_task
            except asyncio.CancelledError:
                self.logger.info("Motion task cancelled successfully")
            except Exception as e:
                self.logger.error("Error during task cancellation: %s", e)
            finally:
                self._current_motion_task = None

        if self.robot is not None:
            self.robot.stop_all()
            self.logger.debug("Stopped all motors")
    
    async def _start_motion(self, target_mode: msg_handler.MotorState) -> msg_handler.MotorState:
        """Start a motion task and wait for it to complete."""
        if target_mode == msg_handler.MotorState.DEPLOYING:
            motion_coro = self._deploy()
        elif target_mode == msg_handler.MotorState.FOLDING:
            motion_coro = self._fold()
        else:
            raise ValueError(f"Invalid target mode: {target_mode}")

        self._current_motion_task = asyncio.create_task(motion_coro)
        try:
            await self._current_motion_task
        except asyncio.CancelledError:
            self.logger.info("Motion task cancelled")
            raise
        finally:
            self._current_motion_task = None
        return self._status
                
    async def _deploy(self) -> None:
        if self.robot is None:
            raise RuntimeError("Motor hardware not initialized")
        self.logger.info("Starting deployment")
        self._status = msg_handler.MotorState.DEPLOYING
        try:
            await self.robot.deploy(1)
            self._status = msg_handler.MotorState.DEPLOYED
            self.logger.info("Deployment completed")
        except asyncio.CancelledError:
            self.logger.info("Deployment cancelled")
            self._status = msg_handler.MotorState.FOLDED
            raise
        except Exception as e:
            self.logger.error("Deployment failed: %s", e)
            self._status = msg_handler.MotorState.FOLDED
            raise

    async def _fold(self) -> None:
        if self.robot is None:
            raise RuntimeError("Motor hardware not initialized")
        self.logger.info("Starting folding")
        self._status = msg_handler.MotorState.FOLDING
        try:
            await self.robot.deploy(-1)  # direction=-1 为折叠
            self._status = msg_handler.MotorState.FOLDED
            self.logger.info("Folding completed")
        except asyncio.CancelledError:
            self.logger.info("Folding cancelled")
            self._status = msg_handler.MotorState.FOLDED
            raise
        except Exception as e:
            self.logger.error("Folding failed: %s", e)
            self._status = msg_handler.MotorState.FOLDED
            raise

    async def read_status(self) -> msg_handler.MotorState:
        return self._status

    async def stop(self) -> None:
        """Release hardware resources or stop the motor safely here."""
        await self._stop_current_motion()
        if self.robot is not None:
            self.robot.cleanup_all()
            self.robot = None
        self._status = msg_handler.MotorState.STARTING

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
        is_override: bool = False,
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
