from __future__ import annotations

import asyncio

import msg_handler
import pytest

from capstone_motor.config import DriverConfig
from capstone_motor.motor_driver import MockMotorController, build_motor_controller


@pytest.mark.asyncio
async def test_mock_motor_controller_deploys_after_duration() -> None:
    controller = MockMotorController(motion_duration_sec=0.05)
    await controller.initialize()

    status = await controller.apply_order(msg_handler.MotorState.DEPLOYING)
    assert status == msg_handler.MotorState.DEPLOYING

    await asyncio.sleep(0.07)
    assert await controller.read_status() == msg_handler.MotorState.DEPLOYED

    await controller.stop()


@pytest.mark.asyncio
async def test_mock_motor_controller_queues_reverse_order_until_current_motion_finishes() -> None:
    controller = MockMotorController(motion_duration_sec=0.05)
    await controller.initialize()

    await controller.apply_order(msg_handler.MotorState.DEPLOYING)
    await asyncio.sleep(0.01)
    status = await controller.apply_order(msg_handler.MotorState.FOLDING)

    assert status == msg_handler.MotorState.DEPLOYING

    await asyncio.sleep(0.12)
    assert await controller.read_status() == msg_handler.MotorState.FOLDED

    await controller.stop()


@pytest.mark.asyncio
async def test_mock_motor_controller_latest_command_clears_queued_reverse_order() -> None:
    controller = MockMotorController(motion_duration_sec=0.05)
    await controller.initialize()

    await controller.apply_order(msg_handler.MotorState.DEPLOYING)
    await asyncio.sleep(0.01)
    await controller.apply_order(msg_handler.MotorState.FOLDING)
    await asyncio.sleep(0.01)
    status = await controller.apply_order(msg_handler.MotorState.DEPLOYING)

    assert status == msg_handler.MotorState.DEPLOYING

    await asyncio.sleep(0.08)
    assert await controller.read_status() == msg_handler.MotorState.DEPLOYED

    await controller.stop()


def test_build_motor_controller_returns_mock_controller() -> None:
    controller = build_motor_controller(
        DriverConfig(kind="mock", motion_duration_sec=0.1),
    )

    assert isinstance(controller, MockMotorController)
