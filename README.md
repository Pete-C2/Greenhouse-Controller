# Greenhouse Controller


Greenhouse Controllder to monitor and control:
- Multiple temperature monitors, each controlling a plant propagator with outputs to control a relay powering a propagator heater element.
- Air temperature monitor controlling an air heater.
- Light level monitor controlling lighting.
- Temperature and humidity monitor.

Requires:
- The [GPIO Library](https://code.google.com/p/raspberry-gpio-python/) (Already on most Raspberry Pi OS builds).
- The [Flask web server](https://www.raspberrypi.org/learning/python-web-server-with-flask/worksheet/). Install command:
  - sudo apt-get install python3-flask
- A [Raspberry Pi](http://www.raspberrypi.org/) with Raspbian Stretch OS installed (require python3.5 to support Influxdb).
- Database setup in [Influxdb](https://docs.influxdata.com/influxdb/v1.7/). The intention behind logging measurements to a database is to allow graphical monitoring of the greenhouse history. My plan is to use Grafana - see [How to install Grafana+InfluxDB on the Raspberry Pi](https://www.circuits.dk/install-grafana-influxdb-raspberry/) for more information, although at this stage full documentation is not presented here for using Grafana with the Greenhouse Controller.
- Hardware with [MAX31855 temperature monitors](https://www.maximintegrated.com/en/products/analog/sensors-and-sensor-interface/MAX31855.html).
- Hardware to control a heater elements. In my case this was one propagator with a faulty control unit re-wired to drive the relay from the Raspberry Pi and an eight-relay board to switch mains voltages.
- Hardware with [BH1750 Digital 16-bit ambient light sensor](http://www.mouser.com/ds/2/348/bh1750fvi-e-186247.pdf).
- Hardware with [AM2320 Humidity and temperature sensor](https://learn.adafruit.com/adafruit-am2320-temperature-humidity-i2c-sensor/overview).
- Hardware with [DS18B20 one wire temperature sensor](https://datasheets.maximintegrated.com/en/ds/DS18B20.pdf)

Installation:
- Copy files to a folder on the Raspberry Pi.
- Edit /etc/rc.local to autorun application:
   - sudo nano /etc/rc.local
   - Add: python /home/pi/.../greenhouse.py where ... is the location of your file.
- Install supplementary software:
  - sudo apt-get install python3-flask
  - sudo apt-get install python3-w1thermsensor
  - Install Influxdb and assume that Raspbian Stretch OS is installed. My instructions are based on [How to install Grafana+InfluxDB on the Raspberry Pi](https://www.circuits.dk/install-grafana-influxdb-raspberry/)
    - curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -
    - source /etc/os-release
    - echo deb https://repos.influxdata.com/debian stretch stable | sudo tee /etc/apt/sources.list.d/influxdb.list
    - sudo apt-get update && sudo apt-get install influxdb
    - sudo service influxdb start
    - sudo nano /etc/influxdb/influxdb.conf
    - Edit the configuration to enable http on port 8086 with no authentication.
    - sudo service influxdb restart
    - sudo pip install influxdb
    - python3 -m pip install influxdb
    - influx -precision rfc3339
    - create database greenhouse
- Edit config.xml to define your system hardware. The defaults match my hardware.
    
Recommendations (to make life easier):
- Set a [static IP address](https://www.modmypi.com/blog/tutorial-how-to-give-your-raspberry-pi-a-static-ip-address).
- Define a [hostname](http://www.simonthepiman.com/how_to_rename_my_raspberry_pi.php).
- Create a [fileshare](http://raspberrypihq.com/how-to-share-a-folder-with-a-windows-computer-from-a-raspberry-pi/).
- Install [VNC](https://www.raspberrypi.org/documentation/remote-access/vnc/) for full headless access.

## Use

See wiki.

## Changelog

### V0.22
Modifed values so that parameters that are/could be floats are stored into the database with the type float as the type cannot subsequently be changed.

### V0.21
Added database logging.

### V0.20
Corrected CSV logging.

### V0.19
Added all parameters to web status page.

Modified all measurement threads to be the only place in which sensors are read, saving readings for use elsewhere.

### V0.18
Added raise exception if humidity sensor fails.

Added e-mail notification of sensor failure or paramter exceeding defined value.

### V0.17
Individual monitoring of min, max temperature, heater state, proportion of heating time per propagator.

Separated air heater and propagator heater set temperatures.

### V0.16
Removed unneccessary defintion of global variables.

Added missing defintion of air temperature logging variables.

### V0.15
Added detection of fault in reading humidity sensor.

### V0.14
Added detection of fault in reading light sensor. Default to turn lighting on for the timed duration.

### V0.13
Added individual enable/disable for each control

### V0.12
Added timed control of lighting

### V0.11
Completed display of defined configuration

### V0.10
Added one-wire temperature sensor and control of air heater

### V0.9
Added option to display the defined configuration

### V0.8
Added basic control of lighting relay with a fixed lux level

### V0.7
Moved print output into debug function so that when complete the application runs with a cleaner interface, with optional debug output

### V0.6
Split control elements into separate threads

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