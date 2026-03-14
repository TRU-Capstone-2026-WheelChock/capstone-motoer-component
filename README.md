# capstone-motoer-component

Motor component for receiving motor orders from `capstone-center` and sending
heartbeat messages back.

The current repository focuses on:

- a component skeleton with clear class boundaries
- a `mock` motor driver for local development
- Docker-based local verification tools under `visualizert/`

## Overview

The motor component has these responsibilities:

- subscribe to motor orders
- apply the ordered motor mode through a controller class
- keep runtime state
- publish heartbeat periodically

The direct motor control code is isolated in `src/capstone_motor/motor_driver.py`.
For local testing, the mock controller simulates motion over time:

- `DEPLOYING` takes 5 seconds, then becomes `DEPLOYED`
- `FOLDING` takes 5 seconds, then becomes `FOLDED`
- if the reverse order arrives during motion, the current motion finishes first
  and the reverse order is queued

## Main Files

- `src/capstone_motor/main.py`
  - application wiring and startup
- `src/capstone_motor/command_receiver.py`
  - receives motor orders from ZMQ
- `src/capstone_motor/services.py`
  - applies orders and syncs state
- `src/capstone_motor/state_store.py`
  - runtime state storage
- `src/capstone_motor/heartbeat_publisher.py`
  - periodic heartbeat publishing
- `src/capstone_motor/motor_driver.py`
  - motor controller implementations, including `MockMotorController`
- `config/config.yml`
  - normal container config
- `visualizert/`
  - local test tools for heartbeat viewing and order injection

## Config

The component reads config from `MOTOR_CONFIG_PATH`. If unset, it falls back to
`config.yml`.

Current config sections:

- `component`
  - `id`, `name`
- `logging`
  - `level`
- `driver`
  - `kind`
  - `motion_duration_sec`
  - `initial_status`
- `command`
  - subscriber endpoint and topics
- `heartbeat`
  - publisher endpoint and interval

Example:

```yaml
component:
  id: motor-001
  name: motor

logging:
  level: INFO

driver:
  kind: mock
  motion_duration_sec: 5.0
  initial_status: FOLDED

command:
  endpoint: "tcp://host.docker.internal:5557"
  topics:
    - ""
  is_bind: false

heartbeat:
  endpoint: "tcp://host.docker.internal:5555"
  topic: ""
  is_connect: true
  interval_sec: 1.0
```

## Local Test With Docker

The easiest local check is the visualizer stack.

Start it from the repository root:

```bash
docker compose -f visualizert/docker-compose.yml up --build
```

This starts:

- `motor`
  - the mock motor component
- `heartbeat-monitor`
  - prints received heartbeat JSON lines
- `order-terminal`
  - helper container used to send new orders while the stack is running

## Change Order While Running

In another terminal, send `DEPLOYING`:

```bash
docker compose -f visualizert/docker-compose.yml exec order-terminal \
  poetry run python visualizert/send_order.py --order DEPLOYING
```

Then send `FOLDING` while the motor is still moving:

```bash
docker compose -f visualizert/docker-compose.yml exec order-terminal \
  poetry run python visualizert/send_order.py --order FOLDING
```

You can also send override mode:

```bash
docker compose -f visualizert/docker-compose.yml exec order-terminal \
  poetry run python visualizert/send_order.py --order FOLDING --override
```

## Watch Logs

To follow both motor-side logs and heartbeat output:

```bash
docker compose -f visualizert/docker-compose.yml logs -f motor heartbeat-monitor
```

Useful things to look for:

- `received motor order=...`
- `mock motor started order=...`
- heartbeat status transitions such as `DEPLOYING`, `DEPLOYED`, `FOLDING`,
  `FOLDED`

## Troubleshooting

If you changed config or the visualizer scripts but behavior still looks old,
recreate the containers:

```bash
docker compose -f visualizert/docker-compose.yml up -d --force-recreate \
  motor heartbeat-monitor order-terminal
```

This matters especially after editing:

- `visualizert/config.visualizer.yml`
- `visualizert/send_order.py`
- `src/capstone_motor/command_receiver.py`

If you only want to stop the local stack:

```bash
docker compose -f visualizert/docker-compose.yml down
```

## Raspberry Pi Deployment Note

The current repo is ready for local testing with the mock driver. For Raspberry
Pi deployment, the intended next step is to add a hardware-specific controller
implementation under `src/capstone_motor/motor_driver.py` and switch it through
`driver.kind`.
