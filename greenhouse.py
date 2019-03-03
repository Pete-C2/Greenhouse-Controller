#!/usr/bin/python3
"""Greenhouse Controller
Reads the configuration from an associated xml file.
Presents a set of webpages to display the temperature.
Controls the temperature of the propagator using a sensor (typically inserted
into the soil).
"""

import datetime
import xml.etree.ElementTree as ET
import os
import threading
import time
import csv
import sys

import RPi.GPIO as GPIO
from flask import Flask, render_template, request
from w1thermsensor import W1ThermSensor

from max31855 import MAX31855, MAX31855Error
import bh1750
import am2320

# Debug logging

def debug_log(log_string):
     if (debug_logging == "Enabled"):
         print(log_string)

# Display config

def print_config():
     print("Configuration:")
     print("  Temperature thermocouples:")
     for cs_pin, relay_pin, cal, meas, name, status in zip(
                                    propagator_cs_pins,
                                    propagator_relay_pins,
                                    propagator_calibrate,
                                    propagator_measured,
                                    propagator_channel_names,
                                    propagator_enabled):

          print("    Propagator: " + name)
          print("      > Chip Select = " + str(cs_pin))
          print("      > Relay = " + str(relay_pin)) 
          print("      > Calibration = " + str(cal) + "\u00B0C at " + str(meas)
          + "\u00B0C")
          print("      > Status = " + status)
     for count in temperature_schedule:
          print("    From " + str(temperature_schedule[count]["time"]) +
                ": " + str(temperature_schedule[count]["temp"]) + "\u00B0C")

     print("  Air heating:")
     print("    > Relay = " + str(air_heating_relay_pin))
     print("    > Calibration = " + str(air_calibrate) + "\u00B0C at " +
           str(air_measured) + "\u00B0C")
     print("      > Status = " + air_enabled)

     for count in air_temperature_schedule:
          print("    From " + str(air_temperature_schedule[count]["time"]) +
                ": " + str(air_temperature_schedule[count]["temp"]) + "\u00B0C")

     print("  Lighting:")
     for relay_pin, on_lux, hysteresis, name, status in zip(
                                                        lighting_relay_pins,
                                                        lighting_on_lux,
                                                        lighting_hysteresis,
                                                        lighting_channel_names,
                                                        lighting_enabled):
          print("    Light: " + name)
          print("      > Relay = " + str(relay_pin)) 
          print("      > On Lux = " + str(on_lux))
          print("      > Hysteresis = " + str (hysteresis))
          print("      > Status = " + status)
     for count in lighting_schedule:
          print("    From " + str(lighting_schedule[count]["time"]) +
                ": " + str(lighting_schedule[count]["status"]))

     print("  Units = " + units)
     print("  Title = " + title)

# Heater control code: if the temperature is too cold then turn the heater on
# (typically using a relay), else turn it off.


class PropagatorHeaterThread(threading.Thread):

     def run(self):
          global propagators
          global air_temp
          global propagator_set_temperature
          
          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting propagator heater thread")

          for relay_pin in propagator_relay_pins:
               GPIO.setup(relay_pin, GPIO.OUT)
               GPIO.output(relay_pin, GPIO.LOW)

          try:
               while 1: # Control the heater forever while powered
                    thermocouples = []
                    debug_log("")
                    debug_log("Measuring propagator temperature...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    propagator_set_temperature = temperature_schedule[1]["temp"]
                    # Default to the first timed temperature
                    for count in temperature_schedule:
                          if (now >= temperature_schedule[count]["time"]):
                              propagator_set_temperature = temperature_schedule \
                                                [count]["temp"]
                              # Keep selecting a new temperature if the time is
                              # later than the start of the time schedule

                    channel = 1

                    for cs_pin in propagator_cs_pins:
                         thermocouples.append(MAX31855(cs_pin, spi_clock_pin,
                                                       spi_data_pin, units,
                                                       GPIO.BOARD))

                    for thermocouple, relay_pin, cal, meas, enabled in zip \
                            (thermocouples,
                            propagator_relay_pins,
                            propagator_calibrate,
                            propagator_measured,
                            propagator_enabled):
                         if (enabled == "Enabled"):
                              if (channel == 1):
                                   air_temp = int(thermocouple.get_rj())
                              try:
                                   tc = int(thermocouple.get()) + cal - meas
                                   propagators[channel]["temp"] = tc
                                   if (tc
                                         < propagators[channel]["min_temperature"]):
                                        propagators[channel]["min_temperature"] = tc
                                   if (tc
                                         > propagators[channel]["max_temperature"]):
                                        propagators[channel]["max_temperature"] = tc
                              except MAX31855Error as e:
                                   tc = "Error"
                                   propagators[channel]["temp"] = "Error: " + e.value


                              debug_log("Temperature: " + str(tc) + "\u00B0C"
                                        + ".  Set Temperature: "
                                        + str(propagator_set_temperature)
                                        + "\u00B0C")
                              debug_log("Min: "
                                        + str(propagators[channel]["min_temperature"])
                                        + ", Max: "
                                        + str(propagators[channel]["max_temperature"]))

                              if tc == "Error":
                                   GPIO.output(relay_pin, GPIO.LOW)
                                   # Turn off Relay (fault condition -
                                   # avoid overheating)
                                   propagators[channel]["heater_state"] \
                                                        = "Error: Off"
                                   debug_log("Error: Propagator relay off")
                              else:
                                   if tc < propagator_set_temperature:
                                        GPIO.output(relay_pin, GPIO.HIGH)
                                        # Turn on relay
                                        propagators[channel]["heater_state"] \
                                                             = "On"
                                        if (log_status == "On"):
                                             propagators[channel]["log_on"] = \
                                               propagators[channel]["log_on"]+1
                                        debug_log("Propagator relay on")
                                   else:
                                        GPIO.output(relay_pin, GPIO.LOW)
                                        # Turn off relay
                                        propagators[channel]["heater_state"] \
                                                             = "Off"
                                        if (log_status == "On"):
                                             propagators[channel]["log_off"] = \
                                               propagators[channel]["log_off"]+1
                                        debug_log("Propagator relay off")
                         else:
                              # Propagator is disabled
                              GPIO.output(relay_pin, GPIO.LOW)
                              # Turn off relay
                              propagators[channel]["heater_state"] = "Off"
                              if (log_status == "On"):
                                   propagators[channel]["log_off"] = \
                                     propagators[channel]["log_off"] + 1
                              debug_log("Propagator disabled - Relay off")

                         channel = channel + 1
                              

                    for thermocouple in thermocouples:
                         thermocouple.cleanup()
                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

class AirHeaterThread(threading.Thread):

     def run(self):
          global air_heater_state
          global air_log_on
          global air_log_off
          global air_set_temperature

          debug_log("Starting air heating thread")

          sensor = W1ThermSensor() # Assumes just one sensor available

          GPIO.setmode(GPIO.BOARD)
          GPIO.setup(air_heating_relay_pin, GPIO.OUT)
          GPIO.output(air_heating_relay_pin, GPIO.LOW)
          
          try:
               while 1: # Control the air heating forever while powered
                    debug_log("")
                    debug_log("Measuring air temperature...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    air_set_temperature = air_temperature_schedule[1]["temp"]
                    # Default to the first timed temperature
                    for count in air_temperature_schedule:
                          if (now >= air_temperature_schedule[count]["time"]):
                              air_set_temperature = air_temperature_schedule \
                                                [count]["temp"]
                              # Keep selecting a new temperature if the time is
                              # later than the start of the time schedule

                    if (air_enabled == "Enabled"):
                         air_temperature = sensor.get_temperature() \
                                             + air_calibrate - air_measured

                         debug_log("Air temperature: " +
                                   "{0:+.1f}".format(air_temperature) +
                                   "\u00B0C")
                         if air_temperature < air_set_temperature:
                              # Turn air heater relay on
                              GPIO.output(air_heating_relay_pin, GPIO.HIGH)
                              # Turn on relay
                              air_heater_state = "On"
                              if (log_status == "On"):
                                   air_log_on = air_log_on + 1
                              debug_log("Air heating relay on")
                         else:
                              GPIO.output(air_heating_relay_pin, GPIO.LOW)
                              # Turn off relay
                              air_heater_state = "Off"
                              if (log_status == "On"):
                                   air_log_off = air_log_off + 1
                              debug_log("Air heating relay off")
                    else:
                         # Air heating disabled
                         GPIO.output(air_heating_relay_pin, GPIO.LOW)
                         # Turn off relay
                         air_heater_state = "Off"
                         if (log_status == "On"):
                              air_log_off = air_log_off + 1
                         debug_log("Air heating disabled - relay off")

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

class LightingThread(threading.Thread):

     def run(self):

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting lighting thread")

          for relay_pin in lighting_relay_pins:
               GPIO.setup(relay_pin, GPIO.OUT)
               GPIO.output(relay_pin, GPIO.LOW)

          light_sensor = bh1750.BH1750()

          try:
               while 1: # Control the lighting forever while powered
                    debug_log("")
                    debug_log("Measuring light...    %s" %
                          (time.ctime(time.time())))

                    try:
                         current_lux = light_sensor.get_light_mode()
                    except:
                         debug_log("Light sensor error")
                         current_lux = 0 # Define illumination as pitch black.
                         # If the light sensor fails then the lights will be
                         # turned on for the defined timer duration irrespective
                         # of actual illumination.

                    now = datetime.datetime.now().time()

                    set_status = lighting_schedule[1]["status"]
                    # Default to the first timed status
                    for count in lighting_schedule:
                          if (now >= lighting_schedule[count]["time"]):
                              set_status = lighting_schedule[count]["status"]
                              # Keep selecting a new status if the time is
                              # later than the start of the time schedule

                    debug_log("Light level: " +
                          "{0:.1f}".format(current_lux) + " lux")

                    for relay_pin, on_lux, hysteresis, status, enabled in zip(
                                                        lighting_relay_pins,
                                                        lighting_on_lux,
                                                        lighting_hysteresis,
                                                        lighting_status,
                                                        lighting_enabled):
                         if (enabled == "Enabled"):
                              if (set_status == "On"):
                                   if (current_lux < on_lux):
                                        status = "On"
                                        # Turn on relay
                                        GPIO.output(relay_pin, GPIO.HIGH)
                                        debug_log("Light relay on")
                                   elif (current_lux > (on_lux + hysteresis)):
                                        status = "Off"
                                        # Turn off relay
                                        GPIO.output(relay_pin, GPIO.LOW)
                                        debug_log("Light relay off")
                                   else:
                                        debug_log("Light level within state change hysteresis")
                              else:
                                   # set_status should be Off (but not checked)
                                   GPIO.output(relay_pin, GPIO.LOW)
                                   debug_log("Light relay off by time schedule")
                         else:
                              # Lighting is disabled
                              GPIO.output(relay_pin, GPIO.LOW)
                              debug_log("Light disabled - relay off")

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

class HumidityThread(threading.Thread):

     def run(self):

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting humidity control thread")

          airtemp_humidity_sensor = am2320.AM2320()


          try:
               while 1: # Control the humidity forever while powered
                    debug_log("")
                    debug_log("Measuring humidity...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    try:
                         airtemp_humidity_sensor.get_data()
                         debug_log("Air temp: " +
                               str(airtemp_humidity_sensor.temperature) +
                               "\u00B0C")
                         debug_log("Humidity: " +
                               str(airtemp_humidity_sensor.humidity) + "%RH")
                    except:
                         debug_log("Humidity sensor error")

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

app = Flask(__name__)

# Initialisation

debug_logging = "Off"
display_config = "Off"

# Read any command line parameters

total = len(sys.argv)
cmdargs = str(sys.argv)
for i in range(total):
     if (str(sys.argv[i]) == "--debug"):
          debug_logging = "Enabled"
     if (str(sys.argv[i]) == "--display-config"):
          display_config = "Enabled"

# Read config from xml file

# Find directory of the program
dir = os.path.dirname(os.path.abspath(__file__))
debug_log("Configuration: " + dir+"/config.xml")
# Get the configuration
tree = ET.parse(dir+"/config.xml")
root = tree.getroot()
hardware = root.find("HARDWARE")
propagator_sensors = root.find("PROPAGATOR-SENSORS")
lighting_sensors = root.find("LIGHTING-SENSORS")
air_sensors = root.find("AIR-SENSORS")
display = root.find("DISPLAY")
logging = root.find("LOGGING")
temps_schedule = root.find("TEMPERATURES")
air_temps_schedule = root.find("AIR-TEMPERATURES")
light_schedule = root.find("LIGHTING")

# Read hardware configuration
# Clock
spi_clk = hardware.find("SPICLOCK")
spi_clock_pin = int(spi_clk.find("PIN").text)

# data
spi_data = hardware.find("SPIDATA")
spi_data_pin = int(spi_data.find("PIN").text)

# Propagator monitor and control
propagator_cs_pins = []
propagator_relay_pins = []
propagator_calibrate = []
propagator_measured = []
propagator_channel_names = []
propagator_enabled = []

for child in propagator_sensors:
     propagator_cs_pins.append(int(child.find("CSPIN").text))
     propagator_relay_pins.append(int(child.find("RELAY").text))
     propagator_calibrate.append(int(child.find("CALIBRATE").text))
     propagator_measured.append(int(child.find("MEASURED").text))
     propagator_channel_names.append(child.find("NAME").text)
     propagator_enabled.append(child.find("ENABLED").text)

for child in air_sensors:
     air_heating_relay_pin = (int(child.find("RELAY").text))
     air_calibrate = (int(child.find("CALIBRATE").text))
     air_measured = (int(child.find("MEASURED").text))
     air_enabled = (child.find("ENABLED").text)

# Lighting monitor and control
lighting_relay_pins = []
lighting_on_lux = []
lighting_hysteresis = []
lighting_channel_names = []
lighting_enabled = []
lighting_status = []
for child in lighting_sensors:
     lighting_relay_pins.append(int(child.find("RELAY").text))
     lighting_on_lux.append(int(child.find("ON-LUX").text))
     lighting_hysteresis.append(int(child.find("HYSTERESIS").text))
     lighting_channel_names.append(child.find("NAME").text)
     lighting_enabled.append(child.find("ENABLED").text)
     lighting_status.append("Off")

# Read display settings configuration
units = display.find("UNITS").text.lower()
title = display.find("TITLE").text

# Create a dictionary called propagators to store the measurements and names:
propagators = {}
channel = 1
for child in propagator_sensors:
     propagators[channel] = {"name": child.find("NAME").text,
                             "temp": "",
                             "log_on": 0, # No. of measurements heater is on
                             "log_off": 0, # No. of measurements heater is off
                             "min_temperature": 100, # greater than min will be
                             "max_temperature": -100, # less than max will be
                             "heater_state": "Undefined"} 
                             # Default values pending measurements
     channel = channel + 1

# Read temperature/lux time schedules
temperature_schedule = {}
count = 1
for child in temps_schedule:
     temp = datetime.datetime.strptime(child.find("TIME").text, "%H:%M")
     schedule_time = temp.time()
     temperature_schedule[count] = {"time": schedule_time,
                                    "temp": int(child.find("TEMPERATURE").text)
                                    }
     count = count + 1

air_temperature_schedule = {}
count = 1
for child in air_temps_schedule:
     temp = datetime.datetime.strptime(child.find("TIME").text, "%H:%M")
     schedule_time = temp.time()
     air_temperature_schedule[count] = {"time": schedule_time,
                                    "temp": int(child.find("TEMPERATURE").text)
                                    }
     count = count + 1
lighting_schedule = {}
count = 1
for child in light_schedule:
     temp = datetime.datetime.strptime(child.find("TIME").text, "%H:%M")
     schedule_time = temp.time()
     lighting_schedule[count] = {"time": schedule_time,
                                 "status": child.find("STATUS").text
                                }
     count = count + 1

# Read logging
logging = root.find("LOGGING")
log_interval = int(logging.find("INTERVAL").text)*60
# Interval in minutes from config file
log_status = "Off"  # Values: Off -> On -> Stop -> Off

air_log_on = 0 # Number of measurement intervals when air heater is on
air_log_off = 0 # Number of measurement intervals when air heater is off

# Control
control_interval = 10 # seconds. Interval between control measurements

propagator_set_temperature = 0 # Default value pending reading of correct value
air_set_temperature = 0 # Default value pending reading of correct value

if (display_config == "Enabled"):
     print_config()

PropagatorHeaterThread().start()
AirHeaterThread().start()
LightingThread().start()
HumidityThread().start()

# Flask web page code

@app.route("/")
def index():
     now = datetime.datetime.now()
     timeString = now.strftime("%H:%M on %d-%m-%Y")
     if log_status == "On":
          logging = "Active"
     else:
          logging = "Inactive"
     templatedata = {
                     "title": title,
                     "time": timeString,
                     "logging": logging,
                    }
     return render_template("main.html", **templatedata)

@app.route("/", methods=["POST"])
# Seems to be run regardless of which page the post comes from
def log_button():
     global log_status
     if request.method == "POST":
          # Get the value from the submitted form
          submitted_value = request.form["logging"]
          if submitted_value == "Log_Start":
               if (log_status == "Off"):
                    log_status = "On"
                    log_on = 0
                    log_off = 0
                    LogThread().start()

          if submitted_value =="Log_Stop":
               if (log_status == "On"):
                    log_status = "Stop"
     return index()
 
@app.route("/temp")
def temp():
     now = datetime.datetime.now()
     timeString = now.strftime("%H:%M on %d-%m-%Y")

     templatedata = {
                "title": title,
                "time": timeString,
                "air": air_temp,
                "set": propagator_set_temperature,
                "propagators": propagators,
                "units": units.upper()
                }

     return render_template("temperature.html", **templatedata)

@app.route("/confirm")
def confirm():
     templatedata = {
                "title": title
                }
     return render_template("confirm.html", **templatedata)

@app.route("/shutdown")
def shutdown():
     command = "/usr/bin/sudo /sbin/shutdown +1"
     import subprocess
     process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
     output = process.communicate()[0]
     print(output)
     templatedata = {
                "title": title
                }
     return render_template("shutdown.html", **templatedata)

@app.route("/cancel")
def cancel():
     command = "/usr/bin/sudo /sbin/shutdown -c"
     import subprocess
     process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
     output = process.communicate()[0]
     print(output)
     return index()

# Logging code: write a CSV file with header and then one set of sensor
# measurements per interval


class LogThread(threading.Thread):

     def run(self):
          global log_status
          global log_on
          global log_off
          
          now = datetime.datetime.now()
          filetime = now.strftime("%Y-%m-%d-%H-%M")
          filename=dir+"/logging/"+filetime+"_temperature_log.csv"
          with open(filename, "at") as csvfile:
               logfile = csv.writer(csvfile, delimiter=",", quotechar='"')
               row = ["Date-Time"]
               row.append("Set Temp")
               row.append("Air Temp")
               for channels in propagators:
                    row.append(propagators[channels]["name"])
                    row.append("Heating Active (%)")
                    row.append('Min Temp')
                    row.append('Max Temp')
               row.append("Light Level")
               row.append("Air Temp 2")
               row.append("Humidity")
               row.append("Air Temp 3")
               logfile.writerow(row)

          light_sensor = bh1750.BH1750()
          airtemp_humidity_sensor = am2320.AM2320()
          onewire_sensor = W1ThermSensor()

          while log_status == "On":
               with open(filename, "at") as csvfile:
                    logfile = csv.writer(csvfile, delimiter=",", quotechar='"')
                    now = datetime.datetime.now()
                    row = [now.strftime("%d/%m/%Y %H:%M")]
                    row.append(propagator_set_temperature)
                    row.append(air_temp)
                    for channels in propagators:
                         row.append(propagators[channels]["temp"])
                         if (propagators[channels]["log_off"] == 0):
                              if (propagators[channels]["log_on"] > 1):
                                   row.append(100) # Heater was always on
                              else:
                                   row.append("No measurements")
                                   # No measurement of heater on or off!
                         else:
                              row.append(int(100*propagators[channels]["log_on"]/(propagators[channels]["log_on"]+propagators[channels]["log_off"])))
                              # Calculate the percentage of time the heater was on

                         row.append(propagators[channels]["min_temperature"])
                         row.append(propagators[channels]["max_temperature"])

                    row.append(light_sensor.get_light_mode())

                    airtemp_humidity_sensor.get_data()
                    row.append(airtemp_humidity_sensor.temperature)
                    row.append(airtemp_humidity_sensor.humidity)
                    row.append(onewire_sensor.get_temperature())
                    
                    logfile.writerow(row)
                    
                    log_on = 0 # Restart heater proportion measurement
                    log_off = 0
                    min_temperature = propagators[1]['temp'] # Temporary code to capture min and max
                    max_temperature = propagators[1]['temp']
                    
               time.sleep(log_interval)
          log_status = "Off"

if __name__ == "__main__":
     app.run(debug=False, host="0.0.0.0")
