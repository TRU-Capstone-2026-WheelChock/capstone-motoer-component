from __future__ import annotations

import asyncio
import logging
import os

import zmq.asyncio

from capstone_motor.app import MotorComponentApp
from capstone_motor.command_receiver import MotorCommandReceiver
from capstone_motor.config import (
    build_command_sub_options,
    build_heartbeat_pub_options,
    build_motor_component_config,
    load_config,
)
from capstone_motor.heartbeat_publisher import HeartbeatPublisher
from capstone_motor.motor_driver import build_motor_controller
from capstone_motor.services import MotorCommandService
from capstone_motor.state_store import RuntimeStateStore


def setup_logger(level_name: str) -> logging.Logger:
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        raise SystemExit(f"invalid logging level: {level_name}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    return logging.getLogger("capstone_motor")


def build_app(config_path: str | None = None) -> MotorComponentApp:
    resolved_config_path = config_path or os.getenv("MOTOR_CONFIG_PATH", "config.yml")
    raw_config = load_config(resolved_config_path)
    component_config = build_motor_component_config(raw_config)
    logger = setup_logger(component_config.logging_level)

    zmq_context = zmq.asyncio.Context()
    state_store = RuntimeStateStore()

    motor_controller = build_motor_controller(component_config.driver, logger=logger)
    command_service = MotorCommandService(
        state_store=state_store,
        motor_controller=motor_controller,
        logger=logger,
    )
    command_receiver = MotorCommandReceiver(
        command_service=command_service,
        sub_opt=build_command_sub_options(component_config, context=zmq_context),
        logger=logger,
    )
    heartbeat_publisher = HeartbeatPublisher(
        component_config=component_config,
        state_store=state_store,
        pub_opt=build_heartbeat_pub_options(component_config, context=zmq_context),
        refresh_status=command_service.refresh_status_from_hardware,
        logger=logger,
    )

    return MotorComponentApp(
        command_receiver=command_receiver,
        heartbeat_publisher=heartbeat_publisher,
        motor_controller=motor_controller,
        logger=logger,
    )


def main(config_path: str | None = None) -> None:
    app = build_app(config_path)
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
