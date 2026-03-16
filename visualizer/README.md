# Heartbeat Visualizer

This folder collects local tools for checking whether the motor component is
actually sending heartbeat messages.

## Quick Start With Docker

Run:

```bash
docker compose -f visualizer/docker-compose.yml up --build
```

What this does:

- `motor` runs the mock motor component
- `heartbeat-monitor` acts like a temporary center-side heartbeat receiver
- `order-terminal` is a helper container you can `exec` into to send new orders while the stack is running
- the monitor prints each received heartbeat JSON line to the terminal

## Change Order While Running

Start the stack:

```bash
docker compose -f visualizer/docker-compose.yml up --build
```

In another terminal, send `DEPLOYING`:

```bash
docker compose -f visualizer/docker-compose.yml exec order-terminal \
  poetry run python visualizer/send_order.py --order DEPLOYING
```

Then, while the mock motor is still moving, send `FOLDING`:

```bash
docker compose -f visualizer/docker-compose.yml exec order-terminal \
  poetry run python visualizer/send_order.py --order FOLDING
```

This works with the current mock controller behavior:

- the active motion completes first
- the reverse order is queued
- the next motion starts immediately after the first one finishes

If you want to mark the command as override mode:

```bash
docker compose -f visualizer/docker-compose.yml exec order-terminal \
  poetry run python visualizer/send_order.py --order FOLDING --override
```

## Run Only The Monitor On Your Host

If you want to keep the motor component running elsewhere and just inspect
incoming heartbeats on your host:

```bash
poetry run python visualizer/heartbeat_monitor.py --endpoint tcp://0.0.0.0:5555 --bind
```

This is useful when:

- the motor component connects to your machine on port `5555`
- you want a terminal view without the full `capstone-center`

## Optional Flags

Show all sensor-type messages, not only heartbeat:

```bash
poetry run python visualizer/heartbeat_monitor.py --endpoint tcp://0.0.0.0:5555 --bind --show-all
```

Show the full raw JSON after each formatted line:

```bash
poetry run python visualizer/heartbeat_monitor.py --endpoint tcp://0.0.0.0:5555 --bind --raw
```

Stop after 5 printed messages:

```bash
poetry run python visualizer/heartbeat_monitor.py --endpoint tcp://0.0.0.0:5555 --bind --limit 5
```

## Notes

- The monitor uses a `SUB` socket and defaults to `--bind` because the current
  motor heartbeat publisher uses `connect` in the local testing setup.
- `visualizer/config.visualizer.yml` points the motor heartbeat endpoint to
  `tcp://heartbeat-monitor:5555` so the bundled Docker setup works without a
  real center process.
- `visualizer/config.visualizer.yml` makes the motor-side subscriber bind on
  `tcp://0.0.0.0:5557`, so one-shot senders can connect reliably while the stack
  keeps running.
