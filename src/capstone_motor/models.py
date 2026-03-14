from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import msg_handler


class HeartbeatStatusCode(IntEnum):
    OK = 200
    WARN = 299
    ERROR = 500


def resolve_applied_mode_from_status(
    status: msg_handler.MotorState,
) -> msg_handler.MotorState | None:
    if status in {msg_handler.MotorState.DEPLOYING, msg_handler.MotorState.DEPLOYED}:
        return msg_handler.MotorState.DEPLOYING
    if status in {msg_handler.MotorState.FOLDING, msg_handler.MotorState.FOLDED}:
        return msg_handler.MotorState.FOLDING
    return None


def resolve_heartbeat_status_code(
    status: msg_handler.MotorState,
) -> HeartbeatStatusCode:
    if status in {msg_handler.MotorState.DEAD, msg_handler.MotorState.ERROR}:
        return HeartbeatStatusCode.ERROR
    if status == msg_handler.MotorState.WARN:
        return HeartbeatStatusCode.WARN
    return HeartbeatStatusCode.OK


@dataclass(slots=True)
class RuntimeState:
    desired_mode: msg_handler.MotorState = msg_handler.MotorState.FOLDING
    applied_mode: msg_handler.MotorState | None = None
    motor_status: msg_handler.MotorState = msg_handler.MotorState.STARTING
    is_override_mode: bool = False

    def build_heartbeat_payload(self) -> msg_handler.HeartBeatPayload:
        return msg_handler.HeartBeatPayload(
            status=self.motor_status.value,
            status_code=int(resolve_heartbeat_status_code(self.motor_status)),
        )
