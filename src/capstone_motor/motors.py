import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

class Step_Motor:
# IN1 = 17
# IN2 = 18
# IN3 = 27
# IN4 = 22
     _seq=[
          [1,0,0,1],
          [1,0,0,0],
          [1,1,0,0],
          [0,1,0,0],
          [0,0,1,0],
          [0,0,1,1],
          [0,0,0,1]
          ]

     def __init__(self, pin1, pin2, pin3, pin4, delay=0.002):
          self.pins = [pin1, pin2, pin3, pin4]
          self.delay = delay
          for pin in self.pins:
               GPIO.setup(pin, GPIO.OUT)
               GPIO.output(pin, GPIO.LOW)

     def _set_step(self, w1, w2, w3, w4):
          GPIO.output(self.pins[0], w1)
          GPIO.output(self.pins[1], w2)
          GPIO.output(self.pins[2], w3)
          GPIO.output(self.pins[3], w4)

     def step_once(self, directiron=1):
          if directiron == 1:
               for step in self._seq:
                    self._set_step(*step)
                    time.sleep(self.delay)
          else:
               for step in reversed(self._seq):
                    self._set_step(*step)
                    time.sleep(self.delay)

     def rotate(self, steps, direction=1):
          for _ in range(steps):
               self.step_once(direction)

     def rotate_degress(self, degrees, direction=1):
          step_per_rev = 4096
          steps = int(degrees / 360.0 * step_per_rev)
          self.rotate(steps, direction)

     def stop(self):
          for pin in self.pins:
               GPIO.output(pin, GPIO.LOW)

     def cleanup(self):
          self.stop()

class DCMotor:
     def __init__(self, in1, in2, ena, freq=1000):
          self.in1 = in1
          self.in2 = in2
          self.ena = ena

          GPIO.setup([in1, in2, ena], GPIO.OUT)
          GPIO.output([in1, in2, ena], GPIO.LOW)

          self.pwm = GPIO.PWM(ena, freq)
          self.pwm.start(0)
          self.speed = 0

     def forward(self, speed_percent):
          GPIO.output(self.in1, GPIO.HIGH)
          GPIO.output(self.in2, GPIO.LOW)
          self.pwm.ChangeDutyCycle(speed_percent)
          self.speed = speed_percent

     def backward(self, speed_percent):
          GPIO.output(self.in1, GPIO.LOW)
          GPIO.output(self.in2, GPIO.HIGH)
          self.pwm.ChangeDutyCycle(speed_percent)
          self.speed = speed_percent

     def stop(self):
          GPIO.output([self.in1, self.in2], GPIO.LOW)
          self.pwm.ChangeDutyCycle(0)
          self.speed = 0

     def set_speed(self, speed_precent):
          if self.speed > 0:
               self.forward(speed_precent)
          elif self.speed < 0:
               self.backword(speed_precent)
          else:
               self.pwm.ChangeDutyCycle(speed_precent)

     def cleanup(self):
          self.pwm.stop()
          GPIO.output([self.in1, self.in2, self.ena], GPIO.LOW)

class Robot:
     def __init__(self, step_pins, dc_pins, step_delay=0.002, dc_freq=1000):
          self.step_motor = Step_Motor(*step_pins, delay=step_delay)
          self.dc_motor = DCMotor(*dc_pins, freq=dc_freq)
          
     def cleanup_all(self):
          self.step_motor.cleanup()
          self.dc_motor.cleanup()
          GPIO.cleanup()

if __name__ == "__main__":
     print("Try to test motor control classes...")
     step_pins = [17,18,27,22]
     dc_pins = [23,24,25]

     robot = Robot(step_pins, dc_pins)

     try:
          print("Step motor forward 1 round")
          robot.step_motor.rotate(4096)
          time.sleep(1)

          print("DC motor forward")
          robot.dc_motor.forward(50)
          time.sleep(2)
          print("DC motor backward")
          robot.dc_motor.backward(70)
          time.sleep(2)
          robot.dc_motor.stop()

     except KeyboardInterrupt:
          print("User Interrupt")
     finally:
          robot.cleanup_all()
          print("GPIO Cleaned up")