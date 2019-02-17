# Greenhouse Controller


Initial code for a single-channel temperature monitor with output to control a relay powering a propagator heater element.

Requires:
- The [GPIO Library](https://code.google.com/p/raspberry-gpio-python/) (Already on most Raspberry Pi OS builds).
- The [Flask web server](https://www.raspberrypi.org/learning/python-web-server-with-flask/worksheet/). Install command:
  - sudo apt-get install python3-flask
- A [Raspberry Pi](http://www.raspberrypi.org/).
- Hardware with [MAX31855 temperature monitors](https://www.maximintegrated.com/en/products/analog/sensors-and-sensor-interface/MAX31855.html).
- Hardware to control a heater element. In my case this was a propagator with a faulty control unit re-wired to drive the relay from the Raspberry Pi.
- Hardware with [BH1750 Digital 16-bit ambient light sensor](http://www.mouser.com/ds/2/348/bh1750fvi-e-186247.pdf).
- Hardware with [AM2320 Humidity and temperature sensor](https://learn.adafruit.com/adafruit-am2320-temperature-humidity-i2c-sensor/overview).

Installation:
- Copy files to a folder on the Raspberry Pi.
- Edit /etc/rc.local to autorun application:
   - sudo nano /etc/rc.local
   - Add: python /home/pi/.../greenhouse.py where ... is the location of your file.
- Edit config.xml to define your system hardware. The defaults match my hardware.
    
Recommendations (to make life easier):
- Set a [static IP address](https://www.modmypi.com/blog/tutorial-how-to-give-your-raspberry-pi-a-static-ip-address).
- Define a [hostname](http://www.simonthepiman.com/how_to_rename_my_raspberry_pi.php).
- Create a [fileshare](http://raspberrypihq.com/how-to-share-a-folder-with-a-windows-computer-from-a-raspberry-pi/).
- Install [VNC](https://www.raspberrypi.org/documentation/remote-access/vnc/) for full headless access.

## Use

See wiki.

## Changelog

### V0.5
Added reading of humidity/temperature sensor

### V0.4
Added reading of light sensor

### V0.3
Updated to match recommended style https://www.python.org/dev/peps/pep-0008/

### V0.2
Converted to Python3
Made file executable

### V0.1
Initial code copied from Propagator Thermostat project