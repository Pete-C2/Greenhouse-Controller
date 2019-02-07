#!/usr/bin/python
import smbus
import time

class BH1750:
    """Python driver for [BH1750 Digital 16-bit ambient light sensor](http://www.mouser.com/ds/2/348/bh1750fvi-e-186247.pdf)
    Methods:
     - set_mode  : Set the mode defined in initialisation
     - get_light : Read the latest light measurement in lux; most useful in
                   continuous modes
     - get_light_mode : Set the mode and read the light measurement in lux; most
                        useful in one time modes
    Requires:
     - The smbus library
    """
    # Define device parameters

    I2C_ADDRESS_L = 0x23 # Device I2C address for ADDR low
    I2C_ADDRESS_H = 0x5C # Device I2C address for ADDR high

    POWER_DOWN = 0x00 # No active state
    POWER_ON   = 0x01 # Waiting for measurment command
    RESET      = 0x07 # Reset data register value

    #Modes
    CONTINUOUSLY_H_RES_MODE = 0x10 # Start measurement at 1 lx resolution.
                                   # Measurement time is typically 120ms
                                   
    CONTINUOUSLY_H_RES_MODE_2 = 0x11 # Start measurement at 0.5 lx resolution.
                                     # Measurement time is typically 120ms
                                     
    CONTINUOUSLY_L_RES_MODE = 0x13 # Start measurement at 4 lx resolution.
                                   # Measurement time is typically 16ms.
                                   
    ONE_TIME_H_RES_MODE = 0x20 # Start measurement at 1 lx resolution.
                               # Measurement time is typically 120ms
                               # Device is automatically set to Power Down
                               # after measurement.

    ONE_TIME_H_RES_MODE_2 = 0x21 # Start measurement at 0.5 lx resolution.
                                 # Measurement time is typically 120ms
                                 # Device is automatically set to Power Down
                                 # after measurement.

    ONE_TIME_L_RES_MODE = 0x23 # Start measurement at 4 lx resolution.
                               # Measurement time is typically 16ms
                               # Device is automatically set to Power Down
                               # after measurement.

    def __init__(self, addr = 0, bus = 1, mode = 3):
        """ Define connection
        Parameters:
        - addr: 0 = address pin is low; 1 = address pin is high.
        - bus:  The SMBus used. Rev 1 Pi uses 0; Rev 2 Pi uses 1.
        - mode: 0 to 5 = the mode as defined in the order above
        """
        self.bus = bus
        self.i2cbus = smbus.SMBus(self.bus)
        if (addr == 0):
            self.addr = self.I2C_ADDRESS_L
        else:
            self.addr = self.I2C_ADDRESS_H
        if (mode == 0):
            self.mode = self.CONTINUOUSLY_H_RES_MODE
            self.wait = 0.18 # Wait 180ms for result
            self.resolution_div = 1
        elif (mode == 1):
            self.mode = self.CONTINUOUSLY_H_RES_MODE_2
            self.wait = 0.18 # Wait 180ms for result
            self.resolution_div = 2
        elif (mode == 2):
            self.mode = self.CONTINUOUSLY_L_RES_MODE
            self.wait = 0.024 # Wait 24ms for result
            self.resolution_div = 1
        elif (mode == 3):
            self.mode = self.ONE_TIME_H_RES_MODE
            self.wait = 0.18 # Wait 180ms for result
            self.resolution_div = 1
        elif (mode == 4):
            self.mode = self.ONE_TIME_H_RES_MODE_2
            self.wait = 0.18 # Wait 180ms for result
            self.resolution_div = 2
        else:
            self.mode = self.ONE_TIME_L_RES_MODE
            self.wait = 0.024 # Wait 24ms for result
            self.resolution_div = 1

    def get_light(self):
        # Read light level from I2C interface
        # Must only be called after an appropriate wait for the next measurement
        # to be ready. Calling this directly in one time modes will result in
        # every measurement being out of date
        self.data = self.i2cbus.read_i2c_block_data(self.addr,
                                                    self.mode)
                                                    # Should not need to specify
                                                    # command, but smbus lacks a
                                                    # multi-byte read only command
        lux=(self.data[1] + 256*self.data[0]) / 1.2 / self.resolution_div
        return lux

    def set_mode(self):
        # Set mode on I2C interface
        self.i2cbus.write_byte(self.addr, self.mode)
        return

    def get_light_mode(self):
        # Set mode and read light level from I2C interface
        self.set_mode()
        time.sleep(self.wait) # Wait for result
        return self.get_light()
