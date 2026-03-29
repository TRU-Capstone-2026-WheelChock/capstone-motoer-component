from __future__ import annotations

import argparse
import time

import msg_handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one mock motor order into the running visualizer stack.",
    )
    parser.add_argument(
        "--endpoint",
        default="tcp://motor:5557",
        help="ZMQ endpoint to bind/connect for motor orders. Default: %(default)s",
    )
    parser.add_argument(
        "--order",
        required=True,
        choices=[
            msg_handler.MotorState.DEPLOYING,
            msg_handler.MotorState.FOLDING,
        ],
        help="Motor order to send.",
    )
    parser.add_argument(
        "--sender-id",
        default="visualizer-order-sender",
        help="sender_id used in the outbound MotorMessage.",
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Set is_override_mode=true on the outbound message.",
    )
    parser.add_argument(
        "--bind",
        action="store_true",
        help="Bind the PUB socket instead of connect.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=10,
        help="How many times to resend the same order. Default: %(default)s",
    )
    parser.add_argument(
        "--settle-sec",
        type=float,
        default=0.6,
        help="Wait time after bind/connect before the first send. Default: %(default)s",
    )
    parser.add_argument(
        "--interval-sec",
        type=float,
        default=0.1,
        help="Delay between repeated sends. Default: %(default)s",
    )
    return parser.parse_args()


def build_message(args: argparse.Namespace) -> msg_handler.MotorMessage:
    return msg_handler.MotorMessage(
        sender_id=args.sender_id,
        is_override_mode=args.override,
        ordered_mode=msg_handler.MotorState(args.order),
    )


def build_pub_options(args: argparse.Namespace) -> msg_handler.ZmqPubOptions:
    return msg_handler.ZmqPubOptions(
        endpoint=args.endpoint,
        is_connect=not args.bind,
    )


def main() -> None:
    args = parse_args()
    message = build_message(args)
    pub_options = build_pub_options(args)

    with msg_handler.get_publisher(pub_options) as publisher:
        time.sleep(args.settle_sec)

        for index in range(args.repeats):
            publisher.send(message)
            print(
                f"sent {index + 1}/{args.repeats}: order={message.ordered_mode} "
                f"override={message.is_override_mode} endpoint={args.endpoint}",
                flush=True,
            )
            if index + 1 < args.repeats:
                time.sleep(args.interval_sec)


if __name__ == "__main__":
    main()
