#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from volume import Volume
from mcpctrl import Sources
from kodijson import Kodi
import RPi.GPIO as GPIO
import logging

# create logger
logger = logging.getLogger(__name__)

class Hardware():
    def __init__(self, oled, hyp):
        logger.info("Initializing hardware")
        import RPi.GPIO as GPIO
        import smbus
        self.bus = smbus.SMBus(1) # Rev 2 Pi

        self.outPa = 18 #Relais für PA2200
        self.outTv = 16 #Relais für TV und Sony-Verstärker
        self.outPhono = 33 #Relais für Phono-Preamp Power
        self.Out_pwr_rel = 29 #Relais für Ampi-Ringkerntrafo
        self.inMcpInt = 37
        self.inVolDir = 36
        self.inVolClk  = 7
        self.inVolMute = 15
        self.validSources = ['Aus', 'CD', 'Schneitzlberger', 'Portable', 'Hilfssherriff', 'Bladdnspiela', 'Himbeer314']
        self.source = "Aus"
        self.ampPwr = False
        self.tvPwr = False
        self.oled = oled #OLED-Objekt erzeugen
        self.hyp = hyp #Hyperion-Objekt erzeugen
        self.initGpios() #GPIOs initialisieren
        self.volume = Volume(self.oled, self.bus) #Volumen-Objekt erzeugen
        self.sources = Sources(self.oled, self.bus) #Quellen-Objekt erzeugen

    def __del__(self):
        self.stop()

    def stop(self):
        GPIO.cleanup()   #GPIOs aufräumen
        logger.info("iCleanup GPIOs")
        pass

    def initGpios(self):
        #set up GPIOs
        logger.info("init GPIOs")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.outPa, GPIO.OUT) # EXT1 -> for control of external Relais etc.
        GPIO.setup(self.outTv, GPIO.OUT) # EXT2 -> for control of external Relais etc.
        GPIO.setup(self.outPhono, GPIO.OUT) # Relais for Phono Preamp
        GPIO.setup(self.Out_pwr_rel, GPIO.OUT) # PWR_REL -> for control of amp power supply (vol_ctrl, riaa_amp)
        GPIO.output(self.Out_pwr_rel, GPIO.LOW) # Switch amp power supply off

        GPIO.setup(self.inMcpInt, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Interrupt input from MCP (GPIO26)
        GPIO.setup(self.inVolMute, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # mute key
        GPIO.setup(self.inVolClk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # vol_up key
        GPIO.setup(self.inVolDir, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # vol_up key

        #Set interrupts
        GPIO.add_event_detect(self.inMcpInt, GPIO.FALLING, callback = self.gpioInt)  # Set Interrupt for MCP (GPIO26)
        GPIO.add_event_detect(self.inVolMute, GPIO.RISING, callback = self.gpioInt, bouncetime = 250)  # Set Interrupt for mute key
        GPIO.add_event_detect(self.inVolClk, GPIO.RISING, callback = self.gpioInt)  # Set Interrupt for vol_up key

    def gpioInt(self, channel): #Interrupt Service Routine
        #This function is called, if an interrupt (GPIO) occurs; input parameter is the pin, where the interrupt occured; not needed here
        if channel == self.inMcpInt: #Interrupt from MCP
            src = self.sources.getMcpInt()
            if src == "Nixtun":
                return()
            elif src == "Error":
                logger.warning("An error occured")
                return()
            elif src == "DimOled":
                self.oled.toggleBlankScreen()
                logger.debug("Dim switch toggled")
                return()
            elif src in self.validSources:
                logger.debug("Switching input to {}".format(src))
                self.setSource(src)
                return()
            elif src == "Hyperion":
                logger.debug("Switching hyperion to ")
                self.hyp.setScene()
                return()
        elif channel == self.inVolClk: # Drehn am Rädle
            if GPIO.input(self.inVolDir): # Linksrum drehn
                logger.debug("Leiser")
                self.volume.decVolumePot()
            else: # Linksrum drehn
                logger.debug("Lauter")
                self.volume.incVolumePot()
            time.sleep(0.1)
            return()
        elif channel == self.inVolMute: # mute key pressed
            logger.debug("Ton aus")
            mute = self.volume.toggleMute()
            return()
        else:
            logger.warning("An error orccured during GpioInt({})".format(str(channel)))
            return()

    def setAmpPwr(self, *args):
        # Hier wird später der Leistungsverstärker an und ausgeschaltet
        if(len(args) == 0):
            self.ampPwr = not self.ampPwr
        elif(len(args) == 1 and type(args[0]) is bool):
            self.ampPwr = args[0]
        else:
            logger.warning("ampPwr: Fehler")
        if(self.ampPwr):
            GPIO.output(self.outPa, GPIO.HIGH)
        else:
            GPIO.output(self.outPa, GPIO.LOW)
        logger.debug("PA2200: {}".format(self.ampPwr))
        return(self.ampPwr)

    def getAmpPwr(self):
        return(self.ampPwr)

    def setTvPwr(self, *args):
        # Hier wird später der Fernseher an- und ausgeschaltet
        if(len(args) == 0):
            self.tvPwr = not self.tvPwr
        elif(len(args) == 1 and type(args[0]) is bool):
            self.tvPwr = args[0]
        else:
            logger.warning("tvPwr: Fehler")
        if(self.tvPwr):
            GPIO.output(self.outTv, GPIO.HIGH)
        else:
            GPIO.output(self.outTv, GPIO.LOW)
        logger.debug("TV: {}".format(self.tvPwr))
        return(self.tvPwr)

    def getTvPwr(self):
        return(self.tvPwr)

    def ampiPwr(self, val):
        try:
            if(val == True):
                amp_stat = GPIO.input(self.Out_pwr_rel) # nachschauen, ob der Preamp nicht evtl. schon läuft
                if amp_stat == False:
                    self.sources.setInput("Aus") # source Schneitzlberger, damit Preamp von Endstufe getrennt wird
                    GPIO.output(self.Out_pwr_rel, GPIO.HIGH) # Switch amp power supply on
                    logger.debug("Ampi anmachen")
                    time.sleep(1)
                    self.volume.setPotWiper()
                    time.sleep(1)
                    vol = self.volume.getVolumePot()
                    self.volume.setVolumePot(vol, display=False) #Aktuellen Lautstärke setzen
                else:
                    #Der Preamp läuft wohl schon, also muss nur noch der Eingang gesetzt werden
                    logger.debug("Ampi laaft scho!")
            else:
                self.sources.setInput("Aus") # source Schneitzlberger, damit Preamp von Endstufe getrennt wird
                GPIO.output(self.Out_pwr_rel, GPIO.LOW) # Switch amp power supply off
                logger.debug("Ampi ausmachen")
        except Exception as e:
            logger.warning("Da hat beim Ampi schalten wos ned bassd: {}".format(str(e)))

    def ampPower(self, inp):
        if inp == "off" or inp == "Schneitzlberger":
            self.setSource(inp) #Wird eigentlich nur noch einmal aufgerufen, damit im Display der source angezeigt wird
            if inp == "off":
                reboot_count = reboot_count + 1
                if reboot_count > 5:
                     logger.warning("Rebooting Pi!")
                     subprocess.Popen("reboot")
        elif inp in valid_sources:
            #Hier geht's rein, wenn nicht mit "off" oder "Schneitzlberger" aufgerufen wurde
            # Wenn der Preamp noch nicht läuft, werden die entsprechenden Meldungen ausgegeben,
            # der Eingang zur Trennung der Endstufe auf Schneitzlberger gesetzt, der Preamp
            # angeschaltet und dann (nach 2 Sekunden Wartezeit) die Option des DS1882 konfiguriert
            # sowie die letzte Lautstärke gesetzt und schlussendlich der entsprechende Eingang
            # ausgewählt.
            #Hier geht's rein, wenn der source-Wert nicht gültig ist
            logger.debug("Ampswitch else ... nothing happened.")
        return()

    def phonoPwr(self, val):
        if val == True:
            GPIO.output(self.outPhono, GPIO.HIGH)
        else:
            GPIO.output(self.outPhono, GPIO.LOW)
        return()

    def getAmpOut(self):
        return self.sources.getAmpOut()

    def getHeadOut(self):
        return self.sources.getHeadOut()

    def selectOutput(self, output):
        if(output == "AmpOut"):
            ret = self.sources.setAmpOut()
            logger.debug("Amp Output set remotely to {}".format(str(ret)))
        elif(output == "HeadOut"):
            ret = self.sources.setHeadOut()
            logger.debug("Headphone Output set remotely to {}".format(str(ret)))
        else:
            ret = -1
            logger.debug("Error: not a valid output")
        return ret

    def setKodiAudio(self, val):
        if(val == "analog"):
            #device = "ALSA:@"
            device = "ALSA:sysdefault:CARD=sndrpihifiberry"
        else:
            #device = "PI:HDMI"
            device = "ALSA:sysdefault:CARD=vc4hdmi"
        try:
            kodi = Kodi("http://localhost/jsonrpc")
            kodi.Settings.SetSettingValue({"setting":"audiooutput.audiodevice","value":device})
            kodi.GUI.ShowNotification({"title":"Tonausgang is etz:", "message":val})
            logger.debug("Kodi laaft etz auf {}".format(device))
        except Exception as e:
            logger.warning("Beim Kodiausgang umschalten is wos passiert: {}".format(str(e)))

    def setKodiNotification(self, title, msg):
        try:
            kodi = Kodi("http://localhost/jsonrpc")
            kodi.GUI.ShowNotification({"title":title, "message":msg})
        except Exception as e:
            logger.warning("Beim der Kodianzeigerei is wos passiert: {}".format(str(e)))

    def setSource(self, src):
        if src == "00000000":
            return()
        elif src == self.source:
            logger.debug("Da ist nix neues dabei, ich mach mal nix")
        elif src == "Schneitzlberger":
            self.setKodiAudio("digital")
            self.setTvPwr(True)
            self.setAmpPwr(True)
            self.ampiPwr(False)
            self.sources.setInput(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
            time.sleep(0.2)
            self.phonoPwr(False)
            self.hyp.setScene("Kodi")
        elif src == "CD":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setInput(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
            time.sleep(.2)
            self.phonoPwr(False)
        elif src == "Portable":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setInput(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
            time.sleep(.2)
            self.phonoPwr(False)
        elif src == "Hilfssherriff":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setInput(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
            time.sleep(.2)
            self.phonoPwr(False)
        elif src == "Bladdnspiela":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.phonoPwr(True)
            self.ampiPwr(True)
            time.sleep(1)
            self.sources.setInput(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Himbeer314":
            self.setKodiAudio("analog")
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setInput(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
            time.sleep(.2)
            self.phonoPwr(False)
        elif src == "Aus":
            self.setKodiAudio("digital")
            time.sleep(0.2)
            self.oled.setMsgScreen(l1="Servusla.", l3="Alles aus etz!")
            self.setKodiNotification("Ampi-Eingang", src)
            self.sources.setInput(src)
            time.sleep(0.1)
            self.ampiPwr(False)
            self.phonoPwr(False)
            time.sleep(0.2)
            self.setAmpPwr(False)
            time.sleep(0.5)
            self.setTvPwr(False)
            time.sleep(0.2)
            self.hyp.setScene("Off")
            time.sleep(0.1)
        else:
            logger.idebug('Komischer Elisenzustand')
        self.source = src
        return()

    def getSource(self):
        return(self.source)
