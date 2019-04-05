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
- Install [Grafana](https://www.circuits.dk/install-grafana-influxdb-raspberry/) to monitor the performance over time.

## Use

See wiki.

## Changelog

### V3.0.0-0.4.0
Restricted relay activations if there has been a recent activation.

Added write of activations to configuration XML file.

### V3.0.0-0.3.0
Added count of relay activations.

Added command line option for fake lighting.

### V3.0.0-0.2.0
Added delay before temperature offset is calculated as the first measurement showed no error.

Added ability to globally enable or disable e-mail notifications.

Added test code to fake the lighting control for testing.

### V3.0.0-0.1.0
Added setting for Lighting induced temperature offset to print of configuration.

Add count for number of errors detected on thermocouple per logging period.

Add overall e-mail enable/disable.

### V2.0.1
Corrected failure to detect lights being turned on.

Added write debug to a file for analysis.

### V2.0.0
Added adjustment of temperature due to interference from lighting.

Turning on of growlights caused a sudden drop in measured temperature and a similar increase when the lights turn off; this is likely due to EMC interference from the lights on the thermocouples. This causes the propagator heating to turn on and overheat the propagator (compared to the set temperature). To avoid this, an optional (defined in the configuration file), setting to measure the offset caused, per propagator, when the lights are on is added.

### V1.1.0-0.3.0
Disabled creation of some errors when hardware is disabled.

### V1.1.0-0.2.0
Limit error disable of propagator relay to only if more than a defined number of consecutive error states occur. Avoids current condition where the temperature
can be below the defined level, but due to error conditions the relay turns the heater off and the configured temperature is not acheived.

### V1.1.0-0.1.0
Limit maximum change of temperature per measurement cycle. Observed that some channels once deployed occasionally jump (e.g. from 20degC to 0degC) within one 10s
measurement cycle. It is not generally possible to jump big temperature differences in one measurement cycle, even if the heater is enabled; the exception to this
could be adding cold water. The result on a large jump is to (unnecessarily) turn on the heater for one (or a few) measurement cycle(s). This will cause
unnecessary wear on the relay (reducing the lifetime of the system) and unnecessary energy consumption. By limiting the temperature change, incorrect measurements
have no/minimal effect (the correct temperature will soon be read) and genuine large jumps will take a few measurement cycles to be established (but short in the
overall scheme of a greenhouse controller).

### V1.0.0
Modified config schedules.

Installed in greenhouse.

### V0.37
Corrected config display of calibration vs measurement.

Added calibration for humidity sensor.

### V0.36
Added e-mail alert if air temperature sensor is missing on restart.

Corrected debug log of air temperature in the event the sensor fails.

### V0.35
Moved e-mail into a thread, allowing for network outages without throwing an exception and maintaining a queue up to max 10 e-mails.

Added ability of e-mail text to include non alphanumeric codes through MIME encoding.

### V0.34
Added hysteresis to monitor of CPU core temperature

### V0.33
Added monitor of CPU core temperature.

### V0.32
Modified min/max calculation of thermocouple temperatures to cope with errors.

### V0.31
Added exception if humidity sensor is not connected/faulty.

Detection if one-wire temperature sensor is not connected.

Added test for all relays on - maximum power consumption.

New config for the actual hardware build.

### V0.30
Defined logging to align to the boundary of the minute interval

### V0.29
Added function to self-test hardware implementation as defined by the configuration.

### V0.28
Added calculation of average lighting on time.

### V0.27
Added calculation of average air heating on time.

Removed temprary code as there was no calculation error.

### V0.26
Added error checking code for heating air temperature sensor. NOT yet tested for sensore failure as the sensor is soldered into the test board.

Added temporary code to print propagator heater logging values as there may be a calculation error.

### V0.25
Added checking for sensor errors before adding data to database

### V0.24
Enabled logging based on config file setting

### V0.23
Added initial setting of logging state from config file

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