#!/usr/bin/env python3

import time
import os
import subprocess
from libby.logger import logger

import RPi.GPIO as GPIO


logging = True

run_path =  os.path.dirname(os.path.abspath(__file__))

class Hypctrl():
    def __init__(self):
        self.cList = ["Off", "Kodi", "BluRay", "Schrank", "FF8600", "red" , "green"]
        self.color = 0
        self.Out_ext1 = 16
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.Out_ext1, GPIO.OUT) # EXT1 -> for control of external Relais etc.
        GPIO.output(self.Out_ext1, GPIO.LOW) # Switch amp power supply off


    def setScene(self):
        cmd = '/usr/bin/hyperion-remote'
        if self.color == 0:
            args = ['-c', 'black']
            msg = "Off"
            GPIO.output(self.Out_ext1, GPIO.LOW)
            logger("   Off", logging)
            self.color += 1
        elif self.color == 1:
            args = ['-x']
            msg = "Kodi"
            GPIO.output(self.Out_ext1, GPIO.LOW)
            logger("   Kodi", logging)
            self.color +=1
        elif self.color == 2:
            args = ['-x']
            v4l_ret = subprocess.Popen([run_path+'/hyp-v4l.sh', '&'])
            msg = "BluRay"
            logger("    BluRay", logging)
            GPIO.output(self.Out_ext1, GPIO.LOW)
            self.color += 1
        elif self.color == 3:
            v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
            args = ['-c',  self.cList[self.color+1]]
            msg = "Farbe: "+ self.cList[self.color+1]+" und Schrank"
            logger("   " + self.cList[self.color+1]+" und Schrank", logging)
            GPIO.output(self.Out_ext1, GPIO.HIGH)
            self.color += 1
        elif self.color > 3:
            args = ['-c',  self.cList[self.color]]
            msg = "Farbe: " + self.cList[self.color]
            logger("   " + self.cList[self.color], logging)
            GPIO.output(self.Out_ext1, GPIO.LOW)
            if self.color == len(self.cList)-1:
               self.color = 0
            else:
               self.color += 1
        else:
            self.color = 0
            return()
        #cmd = cmd+args
        #hyp = subprocess.call(cmd)
        #print(cmd, *args)
        #for arg in args:
        #            print("another arg through *argv :", arg)
        hyp = subprocess.Popen([cmd, *args])
        return()

def main():
    hyp = Hypctrl()
    for i in range(7):
        hyp.setScene()
        time.sleep(1)


if(__name__ == "__main__"):
    main()


