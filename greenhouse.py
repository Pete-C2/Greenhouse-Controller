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
# ** ADD: import for one wire thermometer sensor:
# https://github.com/timofurrer/w1thermsensor

from max31855 import MAX31855, MAX31855Error
import bh1750
import am2320

# Debug logging

def debug_log(log_string):
     global debug_logging
     if (debug_logging == "Enabled"):
         print(log_string)

# Heater control code: if the temperature is too cold then turn the heater on
# (typically using a relay), else turn it off.


class PropagatorHeaterThread(threading.Thread):

     def run(self):
          global control_interval
          global propagator_cs_pins
          global spi_clock_pin
          global spi_data_pin
          global units
          global heater_state
          global temps
          global air_temp
          global log_on
          global log_off
          global set_temperature
          global logging

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting heater thread")

          for relay_pin in propagator_relay_pins:
               GPIO.setup(relay_pin, GPIO.OUT)
               GPIO.output(relay_pin, GPIO.LOW)

          try:
               while 1: # Control the heater forever while powered
                    thermocouples = []
                    debug_log("")
                    debug_log("Measuring temperature...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    set_temperature = temperature_schedule[1]["temp"]
                    # Default to the first timed temperature
                    for count in temperature_schedule:
                          if (now >= temperature_schedule[count]["time"]):
                              set_temperature = temperature_schedule \
                                                [count]["temp"]
                              # Keep selecting a new temperature if the time is
                              # later than the start of the time schedule

                    channel = 1

                    for cs_pin in propagator_cs_pins:
                         thermocouples.append(MAX31855(cs_pin, spi_clock_pin,
                                                       spi_data_pin, units,
                                                       GPIO.BOARD))

                    for thermocouple, relay_pin, cal, meas in zip(thermocouples,
                                                        propagator_relay_pins,
                                                        propagator_calibrate,
                                                        propagator_measured):
                         if (channel == 1):
                              air_temp = int(thermocouple.get_rj())
                         try:
                              tc = int(thermocouple.get()) + cal - meas
                              temps[channel]["temp"] = tc
                         except MAX31855Error as e:
                              tc = "Error"
                              temps[channel]["temp"] = "Error: " + e.value

                         channel = channel + 1

                         debug_log("Temperature: " + str(tc) +
                                ".  Set Temperature: " + str(set_temperature))

                         if tc == "Error":
                              GPIO.output(relay_pin, GPIO.LOW)
                              # Turn off Relay (fault condition -
                              # avoid overheating)
                              heater_state = "Error: Off"
                              debug_log("Error: Relay off")
                         else:
                              if tc < set_temperature:
                                   GPIO.output(relay_pin, GPIO.HIGH)
                                   # Turn on relay
                                   heater_state = "On"
                                   if (log_status == "On"):
                                        log_on = log_on + 1
                                   debug_log("Relay on")
                              else:
                                   GPIO.output(relay_pin, GPIO.LOW)
                                   # Turn off relay
                                   heater_state = "Off"
                                   if (log_status == "On"):
                                        log_off = log_off + 1
                                   debug_log("Relay off")

                    for thermocouple in thermocouples:
                         thermocouple.cleanup()
                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

class AirHeaterThread(threading.Thread):

     def run(self):
          global control_interval

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting air heating thread")

          # Add 1 wire sensor

          try:
               while 1: # Control the air heating forever while powered
                    debug_log("")
                    debug_log("Measuring air temperature...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    #debug_log("Air temperature: " +
                    #      str(light_sensor.get_light_mode()))

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

class LightingThread(threading.Thread):

     def run(self):
          global control_interval

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting lighting thread")

          for relay_pin in lighting_relay_pins:
               GPIO.setup(relay_pin, GPIO.OUT)
               GPIO.output(relay_pin, GPIO.LOW)

          light_sensor = bh1750.BH1750()

          try:
               while 1: # Control the lighting forever while powered
                    current_lux = light_sensor.get_light_mode()

                    debug_log("")
                    debug_log("Measuring light...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    debug_log("Light level: " +
                          str(current_lux))

                    for relay_pin, on_lux, hysteresis, status in zip(
                                                        lighting_relay_pins,
                                                        lighting_on_lux,
                                                        lighting_hysteresis,
                                                        lighting_status):
                         if (current_lux < on_lux):
                              status = "On"
                              # Turn on relay
                              GPIO.output(relay_pin, GPIO.HIGH)
                              debug_log("Relay on")
                         elif (current_lux > (on_lux + hysteresis)):
                              status = "Off"
                              # Turn off relay
                              GPIO.output(relay_pin, GPIO.LOW)
                              debug_log("Relay off")
                         else:
                              debug_log("Light level within state change hysteresis")

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

class HumidityThread(threading.Thread):

     def run(self):
          global control_interval

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting humidity control thread")

          airtemp_humidity_sensor = am2320.AM2320()


          try:
               while 1: # Control the humidity forever while powered
                    debug_log("")
                    debug_log("Measuring humidity...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    airtemp_humidity_sensor.get_data()
                    debug_log("Air temp: " +
                          str(airtemp_humidity_sensor.temperature) +
                          "\u00B0C")
                    debug_log("Humidity: " +
                          str(airtemp_humidity_sensor.humidity) + "%RH")

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

app = Flask(__name__)

# Initialisation

heater_state = "Off"
debug_logging = "Off"

# Read any command line parameters

total = len(sys.argv)
cmdargs = str(sys.argv)
for i in range(total):
     if (str(sys.argv[i]) == "--debug"):
          debug_logging = "Enabled"

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
display = root.find("DISPLAY")
logging = root.find("LOGGING")
schedule = root.find("TEMPERATURES")

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
for child in propagator_sensors:
     propagator_cs_pins.append(int(child.find("CSPIN").text))
     propagator_relay_pins.append(int(child.find("RELAY").text))
     propagator_calibrate.append(int(child.find("CALIBRATE").text))
     propagator_measured.append(int(child.find("MEASURED").text))
     propagator_channel_names.append(child.find("NAME").text)

# Lighting monitor and control
lighting_relay_pins = []
lighting_on_lux = []
lighting_hysteresis = []
lighting_channel_names = []
lighting_status = []
for child in lighting_sensors:
     lighting_relay_pins.append(int(child.find("RELAY").text))
     lighting_on_lux.append(int(child.find("ON-LUX").text))
     lighting_hysteresis.append(int(child.find("HYSTERESIS").text))
     lighting_channel_names.append(child.find("NAME").text)
     lighting_status.append("Off")

# Read display settings configuration
units = display.find("UNITS").text.lower()
title = display.find("TITLE").text

# Create a dictionary called temps to store the temperatures and names:
temps = {}
channel = 1
for child in propagator_sensors:
     temps[channel] = {"name": child.find("NAME").text, "temp": ""}
     channel = channel + 1

# Read temperature/time schedules
temperature_schedule = {}
count = 1
for child in schedule:
     temp = datetime.datetime.strptime(child.find("TIME").text, "%H:%M")
     schedule_time = temp.time()
     temperature_schedule[count] = {"time": schedule_time,
                                    "temp": int(child.find("TEMPERATURE").text)
                                    }
     count = count + 1

# Read logging
logging = root.find("LOGGING")
log_interval = int(logging.find("INTERVAL").text)*60
# Interval in minutes from config file
log_status = "Off"  # Values: Off -> On -> Stop -> Off
log_on = 0 # Number of measurement intervals when heater is on
log_off = 0 # Number of measurement intervals when heater is off

# Control
control_interval = 10 # seconds. Interval between control measurements

set_temperature = 0 # Default value pending reading of correct value

PropagatorHeaterThread().start()
LightingThread().start()
HumidityThread().start()

# Flask web page code

@app.route("/")
def index():
     global title
     global log_status
     global pending_note
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
     global set_temperature
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
                "set": set_temperature,
                "temps": temps,
                "heater": heater_state,
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
          global dir
          global log_interval
          global propagator_cs_pins
          global spi_clock_pin
          global spi_data_pin
          global units
          global log_on
          global log_off
          global set_temperature
          
          now = datetime.datetime.now()
          filetime = now.strftime("%Y-%m-%d-%H-%M")
          filename=dir+"/logging/"+filetime+"_temperature_log.csv"
          with open(filename, "at") as csvfile:
               logfile = csv.writer(csvfile, delimiter=",", quotechar='"')
               row = ["Date-Time"]
               row.append("Set Temp")
               for channels in temps:
                    row.append(temps[channels]["name"])
               row.append("Heating Active (%)")
               row.append("Air Temp")
               row.append("Light Level")
               row.append("Air Temp 2")
               row.append("Humidity")
               logfile.writerow(row)

          light_sensor = bh1750.BH1750()
          airtemp_humidity_sensor = am2320.AM2320()

          while log_status == "On":
               with open(filename, "at") as csvfile:
                    logfile = csv.writer(csvfile, delimiter=",", quotechar='"')
                    now = datetime.datetime.now()
                    row = [now.strftime("%d/%m/%Y %H:%M")]
                    row.append(set_temperature)
                    for channels in temps:
                         row.append(temps[channels]["temp"])
                    if (log_off == 0):
                         if (log_on > 1):
                              row.append("100%") # Heater was always on
                         else:
                              row.append("No measurements")
                              # No measurement of heater on or off!
                    else:
                         row.append(int(100*log_on/(log_on+log_off)))
                         # Calculate the percentage of time the heater was on

                    log_on = 0 # Restart heater proportion measurement
                    log_off = 0

                    row.append(air_temp)

                    row.append(light_sensor.get_light_mode())

                    airtemp_humidity_sensor.get_data()
                    row.append(airtemp_humidity_sensor.temperature)
                    row.append(airtemp_humidity_sensor.humidity)
                    
                    logfile.writerow(row)
               time.sleep(log_interval)
          log_status = "Off"

if __name__ == "__main__":
     app.run(debug=False, host="0.0.0.0")
