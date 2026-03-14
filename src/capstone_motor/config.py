from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import msg_handler
import yaml
import zmq.asyncio


@dataclass(frozen=True, slots=True)
class CommandSubscriptionConfig:
    endpoint: str = "tcp://localhost:5557"
    topics: list[str] = field(default_factory=lambda: [""])
    is_bind: bool = False


@dataclass(frozen=True, slots=True)
class HeartbeatPublicationConfig:
    endpoint: str = "tcp://localhost:5555"
    topic: str = ""
    is_connect: bool = True
    interval_sec: float = 1.0


@dataclass(frozen=True, slots=True)
class DriverConfig:
    kind: str = "mock"
    motion_duration_sec: float = 5.0
    initial_status: msg_handler.MotorState = msg_handler.MotorState.FOLDED


@dataclass(frozen=True, slots=True)
class MotorComponentConfig:
    component_id: str = "motor-1"
    component_name: str = "motor"
    logging_level: str = "INFO"
    command: CommandSubscriptionConfig = field(default_factory=CommandSubscriptionConfig)
    heartbeat: HeartbeatPublicationConfig = field(
        default_factory=HeartbeatPublicationConfig
    )
    driver: DriverConfig = field(default_factory=DriverConfig)


def load_config(path: str = "config.yml") -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    except FileNotFoundError as exc:
        raise SystemExit(f"config not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise SystemExit(f"invalid yaml: {exc}") from exc

    if not isinstance(config, dict):
        raise SystemExit("config root must be a mapping")
    return config


def _coerce_topics(value: Any) -> list[str]:
    if value is None:
        return [""]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SystemExit("command.topics must be a list of strings")
    return value


def build_motor_component_config(raw_config: dict[str, Any]) -> MotorComponentConfig:
    component = raw_config.get("component", {})
    logging_cfg = raw_config.get("logging", {})
    command = raw_config.get("command", {})
    heartbeat = raw_config.get("heartbeat", {})
    driver = raw_config.get("driver", {})

    if not isinstance(component, dict):
        raise SystemExit("component must be a mapping")
    if not isinstance(logging_cfg, dict):
        raise SystemExit("logging must be a mapping")
    if not isinstance(command, dict):
        raise SystemExit("command must be a mapping")
    if not isinstance(heartbeat, dict):
        raise SystemExit("heartbeat must be a mapping")
    if not isinstance(driver, dict):
        raise SystemExit("driver must be a mapping")

    return MotorComponentConfig(
        component_id=str(component.get("id", "motor-1")),
        component_name=str(component.get("name", "motor")),
        logging_level=str(logging_cfg.get("level", "INFO")).upper(),
        command=CommandSubscriptionConfig(
            endpoint=str(command.get("endpoint", "tcp://localhost:5557")),
            topics=_coerce_topics(command.get("topics", [""])),
            is_bind=bool(command.get("is_bind", False)),
        ),
        heartbeat=HeartbeatPublicationConfig(
            endpoint=str(heartbeat.get("endpoint", "tcp://localhost:5555")),
            topic=str(heartbeat.get("topic", "")),
            is_connect=bool(heartbeat.get("is_connect", True)),
            interval_sec=float(heartbeat.get("interval_sec", 1.0)),
        ),
        driver=DriverConfig(
            kind=str(driver.get("kind", "mock")),
            motion_duration_sec=float(driver.get("motion_duration_sec", 5.0)),
            initial_status=msg_handler.MotorState(
                str(driver.get("initial_status", msg_handler.MotorState.FOLDED))
            ),
        ),
    )


def build_command_sub_options(
    config: MotorComponentConfig,
    *,
    context: zmq.asyncio.Context,
) -> msg_handler.ZmqSubOptions:
    return msg_handler.ZmqSubOptions(
        endpoint=config.command.endpoint,
        topics=config.command.topics,
        is_bind=config.command.is_bind,
        expected_type="auto",
        context=context,
    )


def build_heartbeat_pub_options(
    config: MotorComponentConfig,
    *,
    context: zmq.asyncio.Context,
) -> msg_handler.ZmqPubOptions:
    return msg_handler.ZmqPubOptions(
        endpoint=config.heartbeat.endpoint,
        topic=config.heartbeat.topic,
        is_connect=config.heartbeat.is_connect,
        context=context,
    )
