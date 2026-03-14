from __future__ import annotations

import logging

import msg_handler
from pydantic import ValidationError

from capstone_motor.services import MotorCommandService


class MotorCommandReceiver:
    def __init__(
        self,
        command_service: MotorCommandService,
        sub_opt: msg_handler.ZmqSubOptions,
        logger: logging.Logger | None = None,
    ) -> None:
        self.command_service = command_service
        self.sub_opt = sub_opt
        self.logger = logger or logging.getLogger(__name__)

    async def handle_message(self, message: msg_handler.MotorMessage) -> None:
        self.logger.info(
            "received motor order=%s override=%s sender_id=%s",
            message.ordered_mode,
            message.is_override_mode,
            message.sender_id,
        )
        await self.command_service.process_command(message)

    async def run(self) -> None:
        async with msg_handler.get_async_subscriber(self.sub_opt) as subscriber:
            self.logger.info("motor command subscriber is UP")
            async for raw in subscriber:
                try:
                    message = msg_handler.MotorMessage.model_validate(raw)
                    await self.handle_message(message)
                except ValidationError:
                    self.logger.exception("Drop invalid motor message")
                except Exception:
                    self.logger.exception("Unexpected error while processing motor command")
