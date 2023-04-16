#!/usr/bin/env python3

import time
import os
import subprocess
from subprocess import DEVNULL
import re
from kodijson import Kodi
import RPi.GPIO as GPIO
import logging
import colorsys
import webcolors

# create logger
logger = logging.getLogger(__name__)

run_path =  os.path.dirname(os.path.abspath(__file__))

class Hypctrl():
    def __init__(self, oled=None):
        self.oled = oled
        self.cList = ["Off", "Kodi", "BluRay", "Schrank", "FF8600", "red" , "green"]
        self.color = 0
        self.al_color = "#000000"
        self.al_brightness = 100
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

    def set_al_power(self, val=False):
        '''Sets the state of the ambilight power and returns the current state  (True/false)
        '''
        if(val):
            GPIO.output(self.OutAlPower, GPIO.HIGH) # Ambilicht an
        else:
            GPIO.output(self.OutAlPower, GPIO.LOW) # Ambilicht aus
        return self.get_al_power()

    def get_al_power(self):
        '''Return the state of the ambilight power (True/false)
        '''
        return GPIO.input(self.OutAlPower) # nachschauen, ob Ambilicht Strom hat oder aa net

    def set_schrank_light(self, val=None):
        '''Toggles the Schrank licht and returns the current state (True/False)
        '''
        if(val is None):
            GPIO.output(self.Out_ext0, not GPIO.input(self.Out_ext0))
        return self.get_schrank_light()

    def get_schrank_light(self):
        '''Returns if the Schrank Licht is on or off (True/False)
        '''
        return GPIO.input(self.Out_ext0)

    def set_al_color(self, color):
        '''Set ambligith color.
        If color is black, #000000, off or similar, Ambilight power is turned off an color is set to black.
        Color parameter can be a color name (https://wiki.selfhtml.org/wiki/Grafik/Farbe/Farbpaletten) or a hex color code with or without leading # symbol
        hyperion-remote is used to set color.
        '''
        if(color is None):
            return("Ambilight: Doing nothing")
        elif(color in ["000000", "#000000", "off", "Off", "OFF", "black"]):
            msg = "off"
            color = "black"
            args = ['-a', 'localhost', '-c', 'black']
            pwr = False
        elif(re.search(r'^(?:[0-9a-fA-F]{3}){1,2}$', color)):
            #Check, if color is in hex format without leading "#"
            color = "#" + color
            msg = color
            args = ['-a', 'localhost', '-c',  color]
            pwr = True
        elif(re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color)):
            #Check, if color is in hex format with leading "#"
            msg = color
            args = ['-a', 'localhost', '-c',  color]
            pwr = True
        else:
            msg = color
            args = ['-a', 'localhost', '-c',  color]
            pwr = True
        cmd = '/usr/bin/hyperion-remote'
        try:
            #Call hyperion.remote with parameters and wait for exit code
            hyp = subprocess.Popen([cmd, *args], stdout=DEVNULL, stderr=DEVNULL)
            while hyp.poll() is None:
                # Process hasn't exited yet, let's wait some
                time.sleep(0.1)
            # Get return code from process
            return_code = hyp.returncode
            if(return_code == 0): #Everything went fine
                logger.info("Ambilight: " + color)
                self.set_al_power(pwr)
                self.al_color = color
            else: # Shit happend during execution of hyperion-remote
                logger.info("Ambilight: color not valid or other error")
        except Exception as e:
            logger.error(e)
            logger.error("hyperion-remote ist kaputt!")
        return self.get_al_color()

    def get_al_color(self):
        '''Returns current stored amibilight color
        '''
        return self.al_color

    def get_al_rgb(self):
        '''Returns RGB color representation string
        '''
        color = webcolors.html5_parse_legacy_color(self.al_color)
        (r,g,b)=[x/255 for x in color]
        r = int(r * 255)
        g = int(g * 255)
        b = int(b * 255)
        return str(r) + "," + str(g) + "," + str(b)

    def set_al_rgb(self, rgb):
        '''Accepts RGB values as csv string. Float values will be truncated. RGB value is transformed to HEX, ambilight color will be set accordingly.

        '''
        if(type(rgb)==tuple):
            ret = "Tuple not implemented yet"
            pass
        elif(type(rgb)==str):
            try:
                rgb = rgb.split(",")
                rgb = [int(x) for x in rgb]
                rgb = webcolors.rgb_to_hex(rgb)
                ret = self.set_al_color(rgb)
            except Exception as e:
                logging.warning(e)
                logging.warning("Ups")
                ret = "RGB value not a valid string"
        else:
            logging.warning("Not of type tuple nore string")
            ret = "RGB value not of type tuple nore string"
        return ret

    def get_al_hsv(self):
        '''Returns Ambilight color as HSV string
        '''
        color = webcolors.html5_parse_legacy_color(self.al_color)
        (r,g,b)=[x/255 for x in color]
        h,s,v = colorsys.rgb_to_hsv(r,g,b)
        h = int(h * 360)
        s = int(s * 100)
        v = int(v * 100)
        return str(h) + "," + str(s) + "," + str(v)

    def set_al_brightness(self, brightness):
        '''Sets Ambilight brightness
        Accepts values between 0 and 100.
        hyperion-remote is used to set brightness.
        '''
        try:
            brightness = int(brightness)
        except:
            ret = "Brightness value must be an integer between 0 and 100"
        if(brightness in range(0,101)):
            cmd = '/usr/bin/hyperion-remote'
            try:
                args = ['-a', 'localhost', '-L',  str(brightness)]
                hyp = subprocess.Popen([cmd, *args], stdout=DEVNULL, stderr=DEVNULL)
                while hyp.poll() is None:
                    # Process hasn't exited yet, let's wait some
                    time.sleep(0.1)
                # Get return code from process
                return_code = hyp.returncode
                if(return_code == 0):
                    logger.info("Ambilight Brightness: " + str(brightness))
                    self.al_brightness = brightness
                    ret = self.get_al_brightness()
                else:
                    logger.warning("Ambilight: something strange happened")
                    ret = "Something strange happened"
            except Exception as e:
                logger.error(e)
                logger.error("hyperion-remote ist kaputt!")
                ret = "Hyperion-remote is broken or so"
        else:
            ret = "Brightness value must be between 0 and 100"
        return ret

    def get_al_brightness(self):
        return str(self.al_brightness)

    def set_scene(self, scene, par=None):
        #if Off:

        #elif Kodi:

        #elif BlueRay:


        #str = '#ffffff' # Your Hex

        pass


    def toggle_scene(self, col=None):
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
            args = ['-a', 'localhost', '-c', 'black']
            GPIO.output(self.Out_ext0, GPIO.LOW)
            self.set_al_power(False)
        elif self.color == 1:
            # Selecting Kodi as input for hyperion
            args = ['-a', 'localhost', '--clearall']
            GPIO.output(self.Out_ext0, GPIO.LOW)
            self.set_al_power(True)
        elif self.color == 2:
            args = ['-a', 'localhost', '--clearall']
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
            self.set_al_power(True)
            self.v4l_running = True
        elif self.color == 3:
            #v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
            args = ['-a', 'localhost', '-c',  self.cList[self.color+1]]
            msg = "Farbe: "+ self.cList[self.color+1]+" und Schrank"
            GPIO.output(self.Out_ext0, GPIO.HIGH)
            self.set_al_power(True)
            #self.color += 1
        elif self.color > 3:
            args = ['-a', 'localhost', '-c',  self.cList[self.color]]
            msg = "Farbe: " + self.cList[self.color]
            GPIO.output(self.Out_ext0, GPIO.LOW)
            self.set_al_power(True)
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
    #hyp.toggle_scene(color=3)
    for i in range(7):
        hyp.toggle_scene()
        print(hyp.getScene())
        time.sleep(2)


if(__name__ == "__main__"):
    main()


