import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
pins = [23,24,25,16]
for pin in pins:
    GPIO.setup(pin, GPIO.IN)

while True:
    states = [GPIO.input(p) for p in pins]
    print(states)
    time.sleep(0.1)