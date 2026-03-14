from __future__ import annotations

import argparse
import json
from datetime import datetime

import msg_handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bind or connect a SUB socket and print incoming motor heartbeats.",
    )
    parser.add_argument(
        "--endpoint",
        default="tcp://0.0.0.0:5555",
        help="ZMQ endpoint to bind/connect. Default: %(default)s",
    )
    parser.add_argument(
        "--topic",
        action="append",
        dest="topics",
        default=None,
        help="Topic to subscribe to. Repeat for multiple topics. Default is empty topic.",
    )
    parser.add_argument(
        "--bind",
        action="store_true",
        help="Bind the SUB socket instead of connect. Useful when acting like the center-side receiver.",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Print non-heartbeat sensor messages too.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Also print the full message JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after N printed messages. 0 means unlimited.",
    )
    return parser.parse_args()


def build_sub_options(args: argparse.Namespace) -> msg_handler.ZmqSubOptions:
    return msg_handler.ZmqSubOptions(
        endpoint=args.endpoint,
        topics=args.topics or [""],
        is_bind=args.bind,
        expected_type="sensor",
    )


def format_message(message: msg_handler.SensorMessage) -> dict[str, object]:
    payload = message.payload
    status = None
    status_code = None

    if isinstance(payload, msg_handler.HeartBeatPayload):
        status = payload.status
        status_code = payload.status_code

    return {
        "received_at": datetime.now().isoformat(timespec="seconds"),
        "sender_id": message.sender_id,
        "sender_name": message.sender_name,
        "timestamp": message.timestamp.isoformat(timespec="seconds"),
        "data_type": str(message.data_type),
        "sequence_no": message.sequence_no,
        "status": status,
        "status_code": status_code,
    }


def should_print_message(
    message: msg_handler.SensorMessage,
    *,
    show_all: bool,
) -> bool:
    if show_all:
        return True
    return message.data_type == msg_handler.GenericMessageDatatype.HEARTBEAT


def main() -> None:
    args = parse_args()
    sub_options = build_sub_options(args)

    print(
        json.dumps(
            {
                "event": "heartbeat-monitor-start",
                "endpoint": args.endpoint,
                "topics": args.topics or [""],
                "mode": "bind" if args.bind else "connect",
                "show_all": args.show_all,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    printed_count = 0

    try:
        with msg_handler.get_subscriber(sub_options) as subscriber:
            for message in subscriber:
                if not isinstance(message, msg_handler.SensorMessage):
                    continue
                if not should_print_message(message, show_all=args.show_all):
                    continue

                print(
                    json.dumps(format_message(message), ensure_ascii=False),
                    flush=True,
                )

                if args.raw:
                    print(message.model_dump_json(), flush=True)

                printed_count += 1
                if args.limit > 0 and printed_count >= args.limit:
                    return
    except KeyboardInterrupt:
        print('{"event":"heartbeat-monitor-stop","reason":"keyboard-interrupt"}', flush=True)


if __name__ == "__main__":
    main()
