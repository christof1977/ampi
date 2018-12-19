#!/usr/bin/env python3

import time
import os
import subprocess
from subprocess import DEVNULL
from libby.logger import logger

from kodijson import Kodi
import RPi.GPIO as GPIO


logging = True

run_path =  os.path.dirname(os.path.abspath(__file__))
eth_addr = 'osmd.fritz.box'

class Hypctrl():
    def __init__(self, oled=None):
        self.oled = oled
        self.cList = ["Off", "Kodi", "BluRay", "Schrank", "FF8600", "red" , "green"]
        self.color = 0
        self.Out_ext0 = 8
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.Out_ext0, GPIO.OUT) # EXT0 -> for control of external Relais etc.
        GPIO.output(self.Out_ext0, GPIO.LOW) # Switch amp power supply off
        self.v4l_running = False

    def setKodiNotification(self, title, msg):
        try:
            kodi = Kodi("http://"+eth_addr+"/jsonrpc")
            kodi.GUI.ShowNotification({"title":title, "message":msg})
        except Exception as e:
            logger("Beim der Kodianzeigerei is wos passiert: " + str(e), logging)



    def setScene(self, col=None):
        if(self.v4l_running):
            v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
            self.v4l_running = False
        if(col is not None):
            if(type(col) is int):
                self.color=int(col)
            else:
                colInd = self.cList.index(col)
                print(self.cList[colInd])
                self.color = colInd
        else:
            if(self.color == len(self.cList)-1):
                self.color = 0
            else:
                self.color += 1
        logger("Scene: " + self.cList[self.color])
        cmd = '/usr/bin/hyperion-remote'
        if self.color == 0:
            args = ['-c', 'black']
            GPIO.output(self.Out_ext0, GPIO.LOW)
        elif self.color == 1:
            args = ['-x']
            GPIO.output(self.Out_ext0, GPIO.LOW)
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
            GPIO.output(self.Out_ext0, GPIO.LOW)
            self.v4l_running = True
        elif self.color == 3:
            #v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
            args = ['-c',  self.cList[self.color+1]]
            msg = "Farbe: "+ self.cList[self.color+1]+" und Schrank"
            GPIO.output(self.Out_ext0, GPIO.HIGH)
            #self.color += 1
        elif self.color > 3:
            args = ['-c',  self.cList[self.color]]
            msg = "Farbe: " + self.cList[self.color]
            GPIO.output(self.Out_ext0, GPIO.LOW)
        hyp = subprocess.Popen([cmd, *args], stdout=DEVNULL, stderr=DEVNULL)
        if(self.oled is not None):
            self.oled.setMsgScreen(l1="Es werde Licht:", l3=self.cList[self.color])
        self.setKodiNotification("Es werde Licht", self.cList[self.color])
        #hyp = subprocess.Popen([cmd, *args])
        return(self.cList[self.color])

    def getScene(self):
        return(self.cList[self.color])

def main():

    from oledctrl import AmpiOled
    oled = AmpiOled()
    hyp = Hypctrl(oled=oled)
    #hyp.setScene(color=3)
    for i in range(7):
        hyp.setScene()
        print(hyp.getScene())
        time.sleep(2)


if(__name__ == "__main__"):
    main()


