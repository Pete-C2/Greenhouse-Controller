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
import smtplib

import RPi.GPIO as GPIO
from flask import Flask, render_template, request
from w1thermsensor import W1ThermSensor
from influxdb import InfluxDBClient

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

     print("  Logging " + log_status + " at " + log_interval + " second interval")
     print("  Units = " + units)
     print("  Title = " + title)

def send_email(body):
     debug_log("Email: " + body)
     smtpserver = smtplib.SMTP("smtp.gmail.com", 587)
     smtpserver.ehlo()
     smtpserver.starttls()
     smtpserver.ehlo()
     smtpserver.login(email_address, email_password)
     from_address = email_address
     subject = "Alert from Greenhouse Controller"
     header = "To:" + email_to_address + "\n"
     header = header + "From: Greenhouse Controller <" + from_address + ">\n"
     header = header + "Subject:" + subject + "\n"
     message = header + body + "\n"
     smtpserver.sendmail(from_address, email_to_address, message)
     smtpserver.quit()

# Propagator heater control code: if the temperature is too cold then turn the
# heater on (typically using a relay), else turn it off.


class PropagatorHeaterThread(threading.Thread):

     def run(self):
          global propagators
          global controller_temp
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
                                   controller_temp = thermocouple.get_rj()
                              try:
                                   tc = thermocouple.get() + cal - meas
                                   propagators[channel]["temp"] = tc
                                   if (tc
                                         < propagators[channel]["min_temperature"]):
                                        propagators[channel]["min_temperature"] = tc
                                   if (tc
                                         > propagators[channel]["max_temperature"]):
                                        propagators[channel]["max_temperature"] = tc
                                   propagators[channel]["error_count"] = 0
                                   propagators[channel]["sensor_error"] = False
                                   propagators[channel]["sensor_alert"] = False
                              except MAX31855Error as e:
                                   tc = "Error"
                                   propagators[channel]["temp"] = "Error: " + e.value
                                   propagators[channel]["sensor_error"] = True
                                   if (propagators[channel]["error_count"] \
                                            < alert_sensor):
                                        propagators[channel]["error_count"] = \
                                            propagators[channel]["error_count"]+1
                                   if ((propagators[channel]["error_count"]
                                            >= alert_sensor)
                                            and
                                           ((propagators[channel]["sensor_alert"] == False))):
                                        send_email("Propagator sensor failed "
                                                   + propagators[channel]["name"] + ".")
                                        propagators[channel]["sensor_alert"] = True

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
                                   if (propagators[channel]["temp"]
                                            >= alert_propagator_temp):
                                        if (propagators[channel]["alert_state"] == "None"):
                                             send_email("Greenhouse high propagator temperature alert - "
                                                        + propagators[channel]["name"]
                                                        + ". Temperature = "
                                                        + str(propagators[channel]["temp"])
                                                        + "degC.")
                                             debug_log("High temperature alert e-mail sent")
                                             propagators[channel]["alert_state"] = "Alerted"
                                   if (propagators[channel]["temp"]
                                             < (alert_propagator_temp - alert_hysteresis)):
                                        propagators[channel]["alert_state"] = "None"
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

# Air heater control code: if the temperature is too cold then turn the
# heater on (typically using a relay), else turn it off.


class AirHeaterThread(threading.Thread):

     def run(self):
          global air_heater_state
          global air_log_on
          global air_log_off
          global air_set_temperature
          global heating_air_temp

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
                         # Add code to detect sensor failure
                         heating_air_temp = air_temperature

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
                         air_heater_state = "Disabled - Off"
                         heating_air_temp = "Not measured"
                         if (log_status == "On"):
                              air_log_off = air_log_off + 1
                         debug_log("Air heating disabled - relay off")

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

# Lighting control code: on a schedule, if the light level is low then turn the
# lighting on (typically using a relay), else turn it off.


class LightingThread(threading.Thread):

     def run(self):
          global lighting
          global light_level

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting lighting thread")

          for relay_pin in lighting_relay_pins:
               GPIO.setup(relay_pin, GPIO.OUT)
               GPIO.output(relay_pin, GPIO.LOW)

          light_sensor = bh1750.BH1750()
          sensor_error = False
          error_count = 0
          sensor_alert = False

          try:
               while 1: # Control the lighting forever while powered
                    debug_log("")
                    debug_log("Measuring light...    %s" %
                          (time.ctime(time.time())))
                    channel = 1

                    try:
                         current_lux = light_sensor.get_light_mode()
                         light_level = current_lux
                         error_count = 0
                         sensor_error = False
                         sensor_alert = False
                    except:
                         debug_log("Light sensor error")
                         light_level = "Error"
                         
                         current_lux = 0 # Define illumination as pitch black.
                         # If the light sensor fails then the lights will be
                         # turned on for the defined timer duration irrespective
                         # of actual illumination.
                         sensor_error = True
                         if (error_count < alert_sensor):
                              error_count = error_count + 1
                         if ((error_count >= alert_sensor)
                                  and (sensor_alert == False)):
                              send_email("Light sensor failed.")
                              sensor_alert = True

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
                                        lighting[channel]["light_state"] = "On"
                                        debug_log("Light relay on")
                                   elif (current_lux > (on_lux + hysteresis)):
                                        status = "Off"
                                        # Turn off relay
                                        GPIO.output(relay_pin, GPIO.LOW)
                                        lighting[channel]["light_state"] = "Off"
                                        debug_log("Light relay off")
                                   else:
                                        debug_log("Light level within state change hysteresis")
                              else:
                                   # set_status should be Off (but not checked)
                                   GPIO.output(relay_pin, GPIO.LOW)
                                   lighting[channel]["light_state"] = "Timer Off"
                                   debug_log("Light relay off by time schedule")
                         else:
                              # Lighting is disabled
                              GPIO.output(relay_pin, GPIO.LOW)
                              lighting[channel]["light_state"] = "Disabled - Off"
                              debug_log("Light disabled - relay off")
                         channel = channel + 1

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

# Humidity code: record the humidity and air temperature


class HumidityThread(threading.Thread):

     def run(self):
          global air_temp
          global humidity_level

          GPIO.setmode(GPIO.BOARD)
          debug_log("Starting humidity control thread")

          airtemp_humidity_sensor = am2320.AM2320()

          alert_state = "None"
          sensor_error = False
          error_count = 0
          sensor_alert = False

          try:
               while 1: # Control the humidity forever while powered
                    debug_log("")
                    debug_log("Measuring humidity...    %s" %
                          (time.ctime(time.time())))

                    now = datetime.datetime.now().time()

                    try:
                         airtemp_humidity_sensor.get_data()
                         error_count = 0
                         sensor_error = False
                         sensor_alert = False
                    except am2320.AM2320Error as e:
                         debug_log("Humidity sensor error: " + e.value)
                         sensor_error = True
                         if (error_count < alert_sensor):
                              error_count = error_count + 1
                         if ((error_count >= alert_sensor)
                                  and (sensor_alert == False)):
                              send_email("Humidity sensor failed.")
                              sensor_alert = True

                    if (sensor_error == False):
                         debug_log("Air temp: " +
                               str(airtemp_humidity_sensor.temperature) +
                               "\u00B0C")
                         debug_log("Humidity: " +
                               str(airtemp_humidity_sensor.humidity) + "%RH")
                         air_temp = airtemp_humidity_sensor.temperature
                         humidity_level = airtemp_humidity_sensor.humidity
                         if (airtemp_humidity_sensor.temperature
                                  >= alert_air_temp):
                              if (alert_state == "None"):
                                   send_email("Greenhouse high air temperature alert. Temperature = "
                                              + str(airtemp_humidity_sensor.temperature)
                                              + "degC.")
                                   debug_log("High temperature alert e-mail sent")
                                   alert_state = "Alerted"
                         if (airtemp_humidity_sensor.temperature
                                   < (alert_air_temp - alert_hysteresis)):
                              alert_state = "None"
                    else:
                         humidity_level = "Humidity sensor error"
                         air_temp = "Humidity sensor error"

                         pass # Add code to monitor errors and send e-mail alert

                    time.sleep(control_interval)

          except KeyboardInterrupt:
               GPIO.cleanup()

# Logging code: write a CSV file with header and then one set of sensor
# measurements per interval to the CSV file and database

def PercentOn(on, off):
     if (off == 0):
          if (on > 1):
               result = 100 # Heater was always on
          else:
               result = 0 # No measurement of heater on or off!
     else:
          # Calculate the percentage of time heater was on
          result = 100 * (on / (on + off))
     return (result)


class LogThread(threading.Thread):

     def run(self):
          global log_status
          global propagators
          global log_off
          
          now = datetime.datetime.now()

          # CSV logging initialisation
          filetime = now.strftime("%Y-%m-%d-%H-%M")
          filename=dir+"/logging/"+filetime+"_temperature_log.csv"
          debug_log("Logging started: " + filename)
          with open(filename, "at") as csvfile:
               logfile = csv.writer(csvfile, delimiter=",", quotechar='"')
               row = ["Date-Time"]
               row.append("Set Temp")
               row.append("Air Temp")
               for channels in propagators:
                    row.append(propagators[channels]["name"])
                    row.append("Heating Active (%)")
                    row.append("Min Temp")
                    row.append("Max Temp")
               row.append("Light level")
               for channels in lighting:
                    row.append(lighting[channels]["name"] + " Light State")
               row.append("Air Temp 2")
               row.append("Humidity")
               row.append("Air Temp 3")
               logfile.writerow(row)

          # InfluxDB logging initialisation
          host = "localhost"
          port = 8086
          user = "root"
          password = "root"
           
          # The database we created
          dbname = "greenhouse"

          # Create the InfluxDB object
          database = InfluxDBClient(host, port, user, password, dbname)

          while log_status == "On":
               # CSV logging
               with open(filename, "at") as csvfile:
                    logfile = csv.writer(csvfile, delimiter=",", quotechar='"')
                    now = datetime.datetime.now()
                    row = [now.strftime("%d/%m/%Y %H:%M")]
                    row.append(propagator_set_temperature)
                    row.append(controller_temp)
                    for channels in propagators:
                         row.append(propagators[channels]["temp"])
                         row.append(PercentOn(propagators[channels]["log_on"],
                                              propagators[channels]["log_off"]))
                         row.append(propagators[channels]["min_temperature"])
                         row.append(propagators[channels]["max_temperature"])
                         propagators[channels]["min_temperature"] = \
                              propagators[channels]["temp"]
                         propagators[channels]["max_temperature"] = \
                              propagators[channels]["temp"]

                    row.append(light_level)
                    for channels in lighting:
                         row.append(lighting[channels]["light_state"])

                    row.append(air_temp)
                    row.append(humidity_level)
                    row.append(heating_air_temp)
                    
                    logfile.writerow(row)

               # Database logging
               
               iso = time.ctime() # temporary resolving database writing
               session = "greenhouse"
               measurements = {}
               measurements.update({"Set Temp": float(propagator_set_temperature)})
               measurements.update({"Air Temp": controller_temp})
               for channels in propagators:
                    measurements.update({propagators[channels]["name"] + " temp": \
                                         propagators[channels]["temp"]})
                    measurements.update({propagators[channels]["name"] + \
                                         " Heating Active (%)": \
                                              float(PercentOn(
                                              propagators[channels]["log_on"],
                                              propagators[channels]["log_off"]))})
                    measurements.update({propagators[channels]["name"] + \
                                         " Min Temp": \
                                         propagators[channels]["min_temperature"]})
                    measurements.update({propagators[channels]["name"] + \
                                         " Max Temp": \
                                         propagators[channels]["max_temperature"]})
               measurements.update({"Light level": light_level})
               for channels in lighting:
                    measurements.update({lighting[channels]["name"] + \
                              " Light State": lighting[channels]["light_state"]})
               measurements.update({"Air Temp 2": air_temp})
               measurements.update({"Humidity": humidity_level})
               measurements.update({"Air Temp 3": float(heating_air_temp)})
               

               json_body = [
               {
                   "measurement": session,
                   "time": now.strftime("%Y%m%d%H%M"),
                   "fields": measurements
               }
               ]

               # Write JSON to InfluxDB
               database.write_points(json_body)

               for channels in propagators:
                    propagators[channels]["log_on"] = 0 # Reset measurements
                    propagators[channels]["log_off"] = 0


               time.sleep(log_interval)
          log_status = "Off"

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

# Create dictionaries and variables to store measurements
propagators = {}
channel = 1
for child in propagator_sensors:
     propagators[channel] = {"name": child.find("NAME").text,
                             "temp": "",
                             "log_on": 0, # No. of measurements heater is on
                             "log_off": 0, # No. of measurements heater is off
                             "min_temperature": 100, # greater than min will be
                             "max_temperature": -100, # less than max will be
                             "heater_state": "Undefined",
                             "alert_state": "None", # Alert for high temperature
                             "sensor_error": False,
                             "error_count": 0,
                             "sensor_alert": False} # Alert for sensor failure
                             # Default values pending measurements
     channel = channel + 1

light_level = 0
channel = 1
lighting = {}
for child in lighting_sensors:
     lighting[channel] = {"name": child.find("NAME").text,
                         "light_state": "Undefined"}
     channel = channel + 1

humidity_level = 0
air_temp = 0

heating_air_temp = 0
air_heater_state = "Undefined"


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

if (logging.find("ENABLED").text == "Enabled"):
     log_status = "On"  # Values: Off -> On -> Stop -> Off
else:
     log_status = "Off"

air_log_on = 0 # Number of measurement intervals when air heater is on
air_log_off = 0 # Number of measurement intervals when air heater is off

# Control
control_interval = 10 # seconds. Interval between control measurements

propagator_set_temperature = 0 # Default value pending reading of correct value
air_set_temperature = 0 # Default value pending reading of correct value

# Get e-mail details
email = ET.parse(dir+"/email.xml")
emailroot = email.getroot()
user_details = emailroot.find("USER")
email_address = user_details.find("EMAIL").text
email_password = user_details.find("PASSWORD").text

email_alerts = emailroot.find("ALERTS")
email_to_address = email_alerts.find("TO").text
alert_restart = email_alerts.find("RESTART").text
alert_sensor = int(email_alerts.find("SENSOR-FAIL").text)
alert_propagator_temp = int(email_alerts.find("PROPAGATOR-TEMP").text)
alert_air_temp = int(email_alerts.find("AIR-TEMP").text)
alert_hysteresis = int(email_alerts.find("HYSTERESIS").text) # How much
                         # temperature must fall before a new alert is generated

if (alert_restart == "Enabled"):
     send_email("Greenhouse controller restart")

if (display_config == "Enabled"):
     print_config()

PropagatorHeaterThread().start()
AirHeaterThread().start()
LightingThread().start()
HumidityThread().start()
if (log_status == "On"):
     time.sleep(control_interval) # Wait to acquire the first set of measurements
     LogThread().start()

# Flask web page code

app = Flask(__name__)

@app.route("/")
def index():
     now = datetime.datetime.now()
     timeString = now.strftime("%H:%M on %d-%m-%Y")
     if log_status == "On":
          logging = "Active"
     elif log_status == "Stop":
          logging = "Stopping..."
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
                    LogThread().start()

          if submitted_value =="Log_Stop":
               if (log_status == "On"):
                    log_status = "Stop"
     return index()
 
@app.route("/temp")
def temp():
     now = datetime.datetime.now()
     timeString = now.strftime("%H:%M on %d-%m-%Y")
     try:
          light = "{:.1f}".format(light_level)
     except:
          light = light_level

     try:
          humidity = "{:.1f}".format(humidity_level)
     except:
          humidity = humidity_level

     try:
          air = "{:.1f}".format(air_temp)
     except:
          air = air_temp

     try:
          heating_air = "{:.1f}".format(heating_air_temp)
     except:
          heating_air = heating_air_temp
          

     templatedata = {
                "title": title,
                "time": timeString,
                "controller": controller_temp,
                "set": propagator_set_temperature,
                "propagators": propagators,
                "units": units.upper(),
                "light": light,
                "lights": lighting,
                "air": air,
                "humidity": humidity,
                "heatingair": heating_air,
                "heater": air_heater_state,
                "heaterset": air_set_temperature
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

if __name__ == "__main__":
     app.run(debug=False, host="0.0.0.0")
