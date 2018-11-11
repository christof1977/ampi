#!/usr/bin/env ptthon3

import RPi.GPIO as GPIO
from libby.logger import logger
logging = True

class Volume():
    def __init__(self, oled, bus):
        logger("Starte mal die Volumenklasse")
        self.poti_device = 0x2f  #I2C-Adresse DS1882
        self.Out_i2c_iso = 32
        self.minVol = 63  #63 für 63 Wiper Positionen, 33 für 33 Wiper Positionen
        self.volPotVal = 40
        self.bus = bus
        self.oled = oled
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.Out_i2c_iso, GPIO.OUT) # Enable/Disable Volume I2C-Bus-Isolator
        GPIO.output(self.Out_i2c_iso, GPIO.LOW) # Disable Volume I2C-Bus-Isolator

    def setPotWiper(self):
    # Setzt das Poti auf 33 oder 63 Wiper-Stellungen, wie in self.minVol festgelegt
        self.volIsolator(1) # Enable Volume I2C-Bus-Isolator
        if self.minVol == 33:
            self.bus.write_byte(self.poti_device, 0x87) #DS1882 auf 33 Wiper Positionen konfigurieren
            logger("33 wiper", logging)
        else:
            self.bus.write_byte(self.poti_device,0x86) #DS1882 auf 63 Wiper Positionen konfigurieren
            logger("63 wiper", logging)
        self.volIsolator(0) # Disable Volume I2C-Bus-Isolator



    def volIsolator(self, status):
        # Mit dieser Funktion wird der DS1882 auf den I2C-Bus geschaltet (1) oder vom Bus getrennt (0)
        if status == 1:
            GPIO.output(self.Out_i2c_iso, GPIO.HIGH) #DS1882 auf den Bus schalten
        else:
            GPIO.output(self.Out_i2c_iso, GPIO.LOW) #DS1182 vom Bus trennen
        return()

    def setVolumePot(self, value):
        if(value >= self.minVol):
            return(-1)
        elif(self.volPotVal <= 0):
            return(-1)
        self.volIsolator(1) # Enable Volume I2C-Bus-Isolator
        try:
            self.volPotVal = value
            self.bus.write_byte(self.poti_device,self.volPotVal)
            self.bus.write_byte(self.poti_device,self.volPotVal+64)
            self.oled.setVolScreen(self.volPotVal)
            logger("Mach mal die Lautstärke auf -"+ str(self.volPotVal) +"dB")
            ret = 0
        except:
            logger("Kann ich etz so net machn. Is der Ampi aus?", logging)
            self.oled.setVolScreen(99)
            ret = -1
        self.volIsolator(0) # Disable Volume I2C-Bus-Isolator
        return(ret)

    def incVolumePot(self):
        if(self.volPotVal > 0):
            self.volPotVal -= 1
            self.setVolumePot(self.volPotVal)
            return(0)
        else:
            return(-1)

    def decVolumePot(self):
        if(self.volPotVal < self.minVol):
            self.volPotVal += 1
            self.setVolumePot(self.volPotVal)
            return(0)
        else:
            return(-1)



    def getVolumePot(self):
        return(self.volPotVal)




def main():

    import smbus
    import time

    from oledctrl import AmpiOled
    logging = True

    bus = smbus.SMBus(1) # Rev 2 Pi

    oled = AmpiOled()
    volume = Volume(oled, bus)
    time.sleep(1)
    print(volume.getVolumePot())
    time.sleep(1)
    volume.incVolumePot()
    print(volume.getVolumePot())
    time.sleep(4)
    volume.decVolumePot()

    print(volume.getVolumePot())


if(__name__ == "__main__"):
    main()
