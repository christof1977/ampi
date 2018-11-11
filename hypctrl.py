#!/usr/bin/env python3

import time
import os
import subprocess
from subprocess import DEVNULL
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


    def setScene(self, color=None):
        if(color is not None):
            self.color=int(color)
        else:
            if(self.color == len(self.cList)-1):
                self.color = 0
            else:
                self.color += 1
        logger("Scene: " + self.cList[self.color])
        cmd = '/usr/bin/hyperion-remote'
        if self.color == 0:
            args = ['-c', 'black']
            GPIO.output(self.Out_ext1, GPIO.LOW)
        elif self.color == 1:
            args = ['-x']
            GPIO.output(self.Out_ext1, GPIO.LOW)
        elif self.color == 2:
            args = ['-x']
            cmd = '/usr/bin/hyperion-v4l2'
            args = ['-d', '/dev/video0',
                    '--input', '0',
                    '-v', 'PAL',
                    '--width', '240',
                    '--height', '192',
                    '--frame-decimator', '2',
                    '--size-decimator', '4',
                    '--red-threshold', '0.1',
                    '--green-threshold', '0.1',
                    '--blue-threshold', '0.1'
                    ]
            GPIO.output(self.Out_ext1, GPIO.LOW)
        elif self.color == 3:
            v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
            args = ['-c',  self.cList[self.color+1]]
            msg = "Farbe: "+ self.cList[self.color+1]+" und Schrank"
            GPIO.output(self.Out_ext1, GPIO.HIGH)
            #self.color += 1
        elif self.color > 3:
            args = ['-c',  self.cList[self.color]]
            msg = "Farbe: " + self.cList[self.color]
            GPIO.output(self.Out_ext1, GPIO.LOW)
        hyp = subprocess.Popen([cmd, *args], stdout=DEVNULL, stderr=DEVNULL)
        #hyp = subprocess.Popen([cmd, *args])
        return()

    def getScene(self):
        return(self.cList[self.color])

def main():
    hyp = Hypctrl()
    #hyp.setScene(color=3)
    for i in range(7):
        hyp.setScene()
        print(hyp.getScene())
        time.sleep(2)


if(__name__ == "__main__"):
    main()


