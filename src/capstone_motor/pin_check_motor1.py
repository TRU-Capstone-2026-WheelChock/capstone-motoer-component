import lgpio
import time

chip = lgpio.gpiochip_open(4)  # 或 0
pins = [17,18,27,22]

while True:
    states = [lgpio.gpio_read(chip, pin) for pin in pins]
    print(states)
    time.sleep(0.1)