import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
pins = [17,18,27,22]
for pin in pins:
    GPIO.setup(pin, GPIO.IN)

while True:
    states = [GPIO.input(p) for p in pins]
    print(states)
    time.sleep(0.1)