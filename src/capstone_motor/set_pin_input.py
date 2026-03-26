import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

motor_pins = [17,18,27,22,23,24,25,16]

for pin in motor_pins:
    GPIO.setup(pin, GPIO.IN)
    
# GPIO.cleanup()