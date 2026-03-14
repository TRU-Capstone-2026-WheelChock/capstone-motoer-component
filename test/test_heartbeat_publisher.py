from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import msg_handler
import pytest

import capstone_motor.heartbeat_publisher as target
from capstone_motor.config import HeartbeatPublicationConfig, MotorComponentConfig
from capstone_motor.heartbeat_publisher import HeartbeatPublisher
from capstone_motor.state_store import RuntimeStateStore


def build_component_config(*, interval_sec: float = 1.0) -> MotorComponentConfig:
    return MotorComponentConfig(
        component_id="motor-test",
        component_name="motor-mock",
        heartbeat=HeartbeatPublicationConfig(interval_sec=interval_sec),
    )


def build_pub_opt() -> msg_handler.ZmqPubOptions:
    return msg_handler.ZmqPubOptions(endpoint="inproc://heartbeat-test")


@pytest.mark.asyncio
async def test_build_message_uses_state_status() -> None:
    state_store = RuntimeStateStore()
    await state_store.set_motor_status(msg_handler.MotorState.DEPLOYED)

    publisher = HeartbeatPublisher(
        component_config=build_component_config(),
        state_store=state_store,
        pub_opt=build_pub_opt(),
    )

    message = await publisher.build_message()

    assert message.sender_id == "motor-test"
    assert message.sender_name == "motor-mock"
    assert message.data_type == msg_handler.GenericMessageDatatype.HEARTBEAT
    assert isinstance(message.payload, msg_handler.HeartBeatPayload)
    assert message.payload.status == msg_handler.MotorState.DEPLOYED.value
    assert message.payload.status_code == 200


@pytest.mark.asyncio
async def test_publish_once_refreshes_status_before_sending() -> None:
    state_store = RuntimeStateStore()
    events: list[str] = []
    sent_messages: list[msg_handler.SensorMessage] = []

    async def refresh_status() -> None:
        events.append("refresh")
        await state_store.set_motor_status(msg_handler.MotorState.FOLDING)

    class FakePublisher:
        async def send(self, msg: msg_handler.SensorMessage) -> None:
            events.append("send")
            sent_messages.append(msg)

    publisher = HeartbeatPublisher(
        component_config=build_component_config(),
        state_store=state_store,
        pub_opt=build_pub_opt(),
        refresh_status=refresh_status,
    )

    await publisher.publish_once(FakePublisher())

    assert events == ["refresh", "send"]
    assert len(sent_messages) == 1
    assert sent_messages[0].payload.status == msg_handler.MotorState.FOLDING.value
    assert sent_messages[0].payload.status_code == 200


@pytest.mark.asyncio
async def test_run_publishes_heartbeat_periodically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[msg_handler.SensorMessage] = []
    sent_event = asyncio.Event()

    class FakePublisher:
        async def send(self, msg: msg_handler.SensorMessage) -> None:
            sent_messages.append(msg)
            if len(sent_messages) >= 3:
                sent_event.set()

    @asynccontextmanager
    async def fake_publisher_ctx(_pub_opt: object) -> AsyncIterator[FakePublisher]:
        yield FakePublisher()

    monkeypatch.setattr(target.msg_handler, "get_async_publisher", fake_publisher_ctx)

    state_store = RuntimeStateStore()
    await state_store.set_motor_status(msg_handler.MotorState.FOLDED)

    publisher = HeartbeatPublisher(
        component_config=build_component_config(interval_sec=0.01),
        state_store=state_store,
        pub_opt=build_pub_opt(),
    )

    task = asyncio.create_task(publisher.run())
    try:
        await asyncio.wait_for(sent_event.wait(), timeout=1.0)
        assert len(sent_messages) >= 3
        assert all(
            msg.data_type == msg_handler.GenericMessageDatatype.HEARTBEAT
            for msg in sent_messages
        )
        assert all(
            isinstance(msg.payload, msg_handler.HeartBeatPayload)
            for msg in sent_messages
        )
        assert all(
            msg.payload.status == msg_handler.MotorState.FOLDED.value
            for msg in sent_messages
        )
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
