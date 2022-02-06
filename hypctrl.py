#!/usr/bin/env python3

import time
import os
import subprocess
from subprocess import DEVNULL
from kodijson import Kodi
import RPi.GPIO as GPIO
import logging

# create logger
logger = logging.getLogger(__name__)

run_path =  os.path.dirname(os.path.abspath(__file__))

class Hypctrl():
    def __init__(self, oled=None):
        self.oled = oled
        self.cList = ["Off", "Kodi", "BluRay", "Schrank", "FF8600", "red" , "green"]
        self.color = 0
        self.Out_ext0 = 8 # Relais fuer Schranklicht (benutzt Pin TXD)
        self.OutAlPower = 22 # Relais fuer Ampilight-Power
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.Out_ext0, GPIO.OUT)
        GPIO.output(self.Out_ext0, GPIO.LOW) # Schranklicht aus
        GPIO.setup(self.OutAlPower, GPIO.OUT)
        GPIO.output(self.OutAlPower, GPIO.LOW) # Ambilicht aus
        self.v4l_running = False

    def setKodiNotification(self, title, msg):
        try:
            kodi = Kodi("http://localhost/jsonrpc")
            kodi.GUI.ShowNotification({"title":title, "message":msg})
        except Exception as e:
            logger.warning("Beim der Kodianzeigerei is wos passiert: {}".format(str(e)))

    def setAlPower(self, val=False):
        if(val):
            GPIO.output(self.OutAlPower, GPIO.HIGH) # Ambilicht an
        else:
            GPIO.output(self.OutAlPower, GPIO.LOW) # Ambilicht aus
        return self.getAlPower()

    def getAlPower(self):
        return GPIO.input(self.OutAlPower) # nachschauen, ob Ambilicht Strom hat oder aa net


    def setScene(self, col=None):
        if(self.v4l_running):
            v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
            self.v4l_running = False
        if(col is not None):
            if(type(col) is int):
                self.color=int(col)
            else:
                colInd = self.cList.index(col)
                self.color = colInd
        else:
            if(self.color == len(self.cList)-1):
                self.color = 0
            else:
                self.color += 1
        logger.info("Setting light scene: {}".format(self.cList[self.color]))
        cmd = '/usr/bin/hyperion-remote'
        if self.color == 0:
            args = ['-c', 'black']
            GPIO.output(self.Out_ext0, GPIO.LOW)
            self.setAlPower(False)
        elif self.color == 1:
            args = ['-x']
            GPIO.output(self.Out_ext0, GPIO.LOW)
            self.setAlPower(True)
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
            self.setAlPower(True)
            self.v4l_running = True
        elif self.color == 3:
            #v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
            args = ['-c',  self.cList[self.color+1]]
            msg = "Farbe: "+ self.cList[self.color+1]+" und Schrank"
            GPIO.output(self.Out_ext0, GPIO.HIGH)
            self.setAlPower(True)
            #self.color += 1
        elif self.color > 3:
            args = ['-c',  self.cList[self.color]]
            msg = "Farbe: " + self.cList[self.color]
            GPIO.output(self.Out_ext0, GPIO.LOW)
            self.setAlPower(True)
        try:
            hyp = subprocess.Popen([cmd, *args], stdout=DEVNULL, stderr=DEVNULL)
        except:
            logger.warning("hyperion-remote ist kaputt!")
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


