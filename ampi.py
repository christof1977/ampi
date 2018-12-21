#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import datetime
import RPi.GPIO as GPIO
import smbus
import syslog
import socket
import time
import threading
from threading import Thread
import signal
import fcntl
import struct
import math
import select
import json
from libby.logger import logger
from kodijson import Kodi
from oledctrl import AmpiOled
from volume import Volume
from mcpctrl import Sources
from hypctrl import Hypctrl
from tcpServer import MyTCPSocketHandler
import socketserver

logging = True

reboot_count = 0

eth_addr='osmd.fritz.box'
udp_port=5005 #An diesen Port wird der UDP-Server gebunden
tcp_port=5015

class Hardware():
    def __init__(self, oled, hyp):
        logger("init class hardware",logging)
        import RPi.GPIO as GPIO
        import smbus
        self.bus = smbus.SMBus(1) # Rev 2 Pi

        self.outPa = 16 #Relais für PA2200
        self.outTv = 18 #Relais für TV und Sony-Verstärker
        self.Out_pwr_rel = 29 #Relais für Ampi-Ringkerntrafo
        self.In_mcp_int = 37
        self.In_vol_down = 7
        self.In_vol_up = 36
        self.In_mute = 15
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
        pass

    def initGpios(self):
        #set up GPIOs
        logger("init GPIOs", logging)
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.outPa, GPIO.OUT) # EXT1 -> for control of external Relais etc.
        GPIO.setup(self.outTv, GPIO.OUT) # EXT2 -> for control of external Relais etc.
        GPIO.setup(self.Out_pwr_rel, GPIO.OUT) # PWR_REL -> for control of amp power supply (vol_ctrl, riaa_amp)
        GPIO.output(self.Out_pwr_rel, GPIO.LOW) # Switch amp power supply off

        GPIO.setup(self.In_mcp_int, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Interrupt input from MCP (GPIO26)
        GPIO.setup(self.In_vol_down, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # vol_down key
        GPIO.setup(self.In_mute, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # mute key
        GPIO.setup(self.In_vol_up, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # vol_up key

        #Set interrupts
        GPIO.add_event_detect(self.In_mcp_int, GPIO.FALLING, callback = self.gpioInt)  # Set Interrupt for MCP (GPIO26)
        GPIO.add_event_detect(self.In_mute, GPIO.RISING, callback = self.gpioInt, bouncetime = 250)  # Set Interrupt for mute key
        GPIO.add_event_detect(self.In_vol_up, GPIO.RISING, callback = self.gpioInt)  # Set Interrupt for vol_up key


    def gpioInt(self, channel): #Interrupt Service Routine
        #This function is called, if an interrupt (GPIO) occurs; input parameter is the pin, where the interrupt occured; not needed here
        if channel == 37: #Interrupt from MCP
            src = self.sources.getMcpInt()
            if src == "Nixtun":
                return()
            elif src == "Error":
                logger("An error occured", logging)
                return()
            elif src == "DimOled":
                self.oled.toggleBlankScreen()
                logger("Dim switch toggled", logging)
                return()
            elif src in self.validSources:
                logger("Switching input to " + src, logging)
                self.setSource(src)
                return()
            elif src == "Hyperion":
                logger("Switching hyperion to ", logging)
                self.hyp.setScene()
                return()
        elif channel == 36: # Drehn am Rädle
            if GPIO.input(7): # Rechtsrum drehn
                logger("Lauter", logging)
                self.volume.incVolumePot()
            else: # Linksrum drehn
                logger("Leiser", logging)
                self.volume.decVolumePot()
            time.sleep(0.1)
            return()
        elif channel == 15: # mute key pressed
            logger("Ton aus", logging)
            mute = self.volume.toggleMute()
            return()
        else:
            logger("An error orccured during GpioInt("+str(channel)+")", logging)
            return()

    def setAmpPwr(self, *args):
        # Hier wird später der Leistungsverstärker an und ausgeschaltet
        if(len(args) == 0):
            self.ampPwr = not self.ampPwr
        elif(len(args) == 1 and type(args[0]) is bool):
            self.ampPwr = args[0]
        else:
            logger("ampPwr: Fehler")
        if(self.ampPwr):
            GPIO.output(self.outPa, GPIO.HIGH)
        else:
            GPIO.output(self.outPa, GPIO.LOW)
        logger("PA2200: " + str(self.ampPwr))
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
            logger("tvPwr: Fehler")
        if(self.tvPwr):
            GPIO.output(self.outTv, GPIO.HIGH)
        else:
            GPIO.output(self.outTv, GPIO.LOW)
        logger("TV: "+str(self.tvPwr))
        return(self.tvPwr)

    def getTvPwr(self):
        return(self.tvPwr)

    def ampiPwr(self, val):
        try:
            if(val == True):
                amp_stat = GPIO.input(self.Out_pwr_rel) # nachschauen, ob der Preamp nicht evtl. schon läuft
                if amp_stat == False:
                    self.sources.setMcpOut("Aus") # source Schneitzlberger, damit Preamp von Endstufe getrennt wird
                    GPIO.output(self.Out_pwr_rel, GPIO.HIGH) # Switch amp power supply on
                    logger("Ampi anmachen", logging)
                    time.sleep(1)
                    self.volume.setPotWiper()
                    time.sleep(1)
                    vol = self.volume.getVolumePot()
                    self.volume.setVolumePot(vol, display=False) #Aktuellen Lautstärke setzen
                else:
                    #Der Preamp läuft wohl schon, also muss nur noch der Eingang gesetzt werden
                    logger("Ampi laaft scho!", logging)
            else:
                self.sources.setMcpOut("Aus") # source Schneitzlberger, damit Preamp von Endstufe getrennt wird
                GPIO.output(self.Out_pwr_rel, GPIO.LOW) # Switch amp power supply off
                logger("Ampi ausmachen", logging)
        except Exception as e:
            logger("Da hat beim Ampi schalten wos ned bassd")
            logger(str(e))

    def ampPower(self, inp):
        if inp == "off" or inp == "Schneitzlberger":
            self.setSource(inp) #Wird eigentlich nur noch einmal aufgerufen, damit im Display der source angezeigt wird
            if inp == "off":
                reboot_count = reboot_count + 1
                if reboot_count > 5:
                     logger("Rebooting Pi!", logging)
                     subprocess.Popen("reboot")
        elif inp in valid_sources:
            #Hier geht's rein, wenn nicht mit "off" oder "Schneitzlberger" aufgerufen wurde
            # Wenn der Preamp noch nicht läuft, werden die entsprechenden Meldungen ausgegeben,
            # der Eingang zur Trennung der Endstufe auf Schneitzlberger gesetzt, der Preamp
            # angeschaltet und dann (nach 2 Sekunden Wartezeit) die Option des DS1882 konfiguriert
            # sowie die letzte Lautstärke gesetzt und schlussendlich der entsprechende Eingang
            # ausgewählt.
            #Hier geht's rein, wenn der source-Wert nicht gültig ist
            logger("Ampswitch else ... nothing happened.", logging)
        return()

    def setKodiAudio(self, val):
        if(val == "analog"):
            device = "ALSA:@"
        else:
            device = "PI:HDMI"
        try:
            kodi = Kodi("http://"+eth_addr+"/jsonrpc")
            kodi.Settings.SetSettingValue({"setting":"audiooutput.audiodevice","value":device})
            kodi.GUI.ShowNotification({"title":"Tonausgang is etz:", "message":val})
            logger("Kodi laaft etz auf " + device, logging)
        except Exception as e:
            logger("Beim Kodiausgang umschalten is wos passiert: " + str(e), logging)

    def setKodiNotification(self, title, msg):
        try:
            kodi = Kodi("http://"+eth_addr+"/jsonrpc")
            kodi.GUI.ShowNotification({"title":title, "message":msg})
        except Exception as e:
            logger("Beim der Kodianzeigerei is wos passiert: " + str(e), logging)



    def setSource(self, src):
        if src == "00000000":
            return()
        elif src == "Schneitzlberger":
            self.setKodiAudio("digital")
            self.setTvPwr(True)
            self.setAmpPwr(True)
            self.ampiPwr(False)
            self.sources.setMcpOut(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "CD":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Portable":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Hilfssherriff":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Bladdnspiela":
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Himbeer314":
            self.setKodiAudio("analog")
            self.setTvPwr(False)
            self.setAmpPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.setKodiNotification("Ampi-Eingang", src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Aus":
            self.setKodiAudio("digital")
            self.oled.setMsgScreen(l1="Servusla.", l3="Alles aus etz!")
            self.setKodiNotification("Ampi-Eingang", src)
            self.sources.setMcpOut("Schneitzlberger")
            self.ampiPwr(False)
            self.setAmpPwr(False)
            time.sleep(0.5)
            self.setTvPwr(False)
            self.hyp.setScene("Kodi")
        else:
            logger('Komischer Elisenzustand', logging)
        self.source = src
        return()

    def getSource(self):
        return(self.source)


class Ampi():
    def __init__(self):

        logger("Starting amplifier control service", logging)

        self.validVolCmd = ['Up', 'Down', 'Mute']
        self.oled = AmpiOled()
        self.hyp = Hypctrl(self.oled)
        #Starte handler für SIGTERM (kill -15), also normales beenden
        #Handler wird aufgerufen, wenn das Programm beendet wird, z.B. durch systemctl
        signal.signal(signal.SIGTERM, self.signal_term_handler)

        self.hw = Hardware(self.oled, self.hyp)

        time.sleep(1.1) #Short break to make sure the display is cleaned

        self.hw.setSource("Aus")  #Set initial source to Aus

        self.udpServer()
        self.tcpServer()

        #tcpServer_t = Thread(target=tcpServer, args=(1, t_stop))
        #tcpServer_t.start()



        logger("Amplifier control service running", logging)


    def __del__(self):
        pass

    def signal_term_handler(self, signal, frame):
        logger("Got " + str(signal), logging)
        logger("Closing UDP Socket", logging)
        self.udpSock.close() #UDP-Server abschiessen
        self.hw.setSource("Aus") #Preamp schlafen legen

        GPIO.cleanup()   #GPIOs aufräumen
        #so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #so.connect((eth_addr, tcp_port))
        #so.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #so.send("foo".encode())
        #so.close()
        logger("              So long sucker!", logging) #Fein auf Wiedersehen sagen
        sys.exit(0) #Und raus hier

    def tcpServer(self):
        sT = threading.Thread(target = self._tcpServer)
        sT.setDaemon(True)
        sT.start()

    def _tcpServer(self):
        server = socketserver.TCPServer((eth_addr, tcp_port), MyTCPSocketHandler)
        server.serve_forever()


    def udpServer(self):
        logger("Starting UDP-Server at " + eth_addr + ":" + str(udp_port),logging)
        self.udpSock = socket.socket( socket.AF_INET,  socket.SOCK_DGRAM )
        self.udpSock.bind( (eth_addr,udp_port) )

        self.t_stop = threading.Event()
        udpT = threading.Thread(target=self._udpServer)
        udpT.setDaemon(True)
        udpT.start()

    def _udpServer(self):
        while(not self.t_stop.is_set()):
            try:
                data, addr = self.udpSock.recvfrom( 1024 )# Puffer-Groesse ist 1024 Bytes.
                ret = self.parseCmd(data) # Abfrage der Fernbedienung (UDP-Server), der Rest passiert per Interrupt/Event
                self.udpSock.sendto(str(ret).encode('utf-8'), addr)
            except Exception as e:
                logger("Uiui, beim UDP senden/empfangen hat's kracht!" + str(e))


    def stopKodiPlayer(self):
        try:
            kodi = Kodi("http://"+eth_addr+"/jsonrpc")
            playerid = kodi.Player.GetActivePlayers()["result"][0]["playerid"]
            result = kodi.Player.Stop({"playerid": playerid})
            logger("Kodi aus!", logging)
        except Exception as e:
            logger("Beim Kodi stoppen is wos passiert: " + str(e), logging)

    def selectSource(self, jcmd):
        logger("Input: " + jcmd['Parameter'], logging)
        logger("Source set remotely to " + jcmd['Parameter'], logging)
        self.hw.setSource(jcmd['Parameter'])
        ret = self.hw.getSource()
        if(ret == -1):
            ret = {"Antwort":"bassd net","Input":ret}
        else:
            ret = {"Antwort":"bassd","Input":ret}
        return(json.dumps(ret))

    def ampiZustand(self):
        zustand  = json.dumps({"Antwort" : "Zustand",
                               "Input" : self.hw.getSource(),
                               "Hyperion" : self.hyp.getScene(),
                               "Volume" : self.hw.volume.getVolume(),
                               "OledBlank" : self.hw.oled.getBlankScreen(),
                               "TV" : self.hw.getTvPwr(),
                               "PA2200" : self.hw.getAmpPwr()
                               })
        return(zustand)

    def parseCmd(self, data):
        data = data.decode()
        try:
            jcmd = json.loads(data)
        except:
            logger("Das ist mal kein JSON, pff!", logging)
            ret = json.dumps({"Antwort": "Kaa JSON Dings!"})
        if(jcmd['Aktion'] == "Input"):
            ret = self.selectSource(jcmd)
        elif(jcmd['Aktion'] == "Hyperion"):
            logger("Remote hyperion control", logging)
            ret = json.dumps({"Antwort": "Hyperion", "Szene": self.hyp.setScene()})
        elif(jcmd['Aktion'] == "Volume"):
            if jcmd['Parameter'] in self.validVolCmd:
                ret = self.setVolume(jcmd['Parameter'])
            else:
                ret = json.dumps({"Antwort": "Kein echtes Volumen-Kommando"})
        elif(jcmd['Aktion'] == "Switch"):
            if jcmd['Parameter'] == "DimOled":
                ret = self.hw.oled.toggleBlankScreen()
                logger("Dim remote command toggled", logging)
                if(ret):
                    ret = json.dumps({"Antwort":"Oled","Wert":"Aus"})
                else:
                    ret = json.dumps({"Antwort":"Oled","Wert":"An"})
            elif jcmd['Parameter'] == "Power":
                self.hw.setSource("Aus")
                self.hyp.setScene("Kodi")
                self.stopKodiPlayer()
                logger("Aus is fuer heit!", logging)
                ret = json.dumps({"Antwort":"Betrieb","Wert":"Aus"})
            else:
                logger("Des bassd net.", logging)
                ret = json.dumps({"Antwort":"Schalter","Wert":"Kein gültiges Schalter-Kommando"})
        elif(jcmd['Aktion'] == "Zustand"):
            logger("Wos für a Zustand?")
            ret = self.ampiZustand()
            #TODO: Alle Zustände lesen und ausgeben
        else:
            logger(data, logging)
            logger("Invalid remote command!", logging)
            ret = json.dumps({"Antwort":"Fehler","Wert":"Kein gültiges Kommando"})
        return(ret)



    def setVolume(self, val):
        if(val == "Up"):
            ret = self.hw.volume.incVolumePot()
        elif(val == "Down"):
            ret = self.hw.volume.decVolumePot()
        else:
            ret = self.hw.volume.toggleMute()
        if(ret == -1):
            ret = {"Antwort":"bassd net","Input":ret}
        else:
            ret = {"Antwort":"bassd","Input":ret}
        return(json.dumps(ret))




def main():
    ampi = Ampi()
    while True:
        try:
            time.sleep(1)
            pass
        except KeyboardInterrupt: # CTRL+C exit
            ampi.signal_term_handler(99, "") #Aufrufen des Signal-Handlers, in der Funktion wird das Programm sauber beendet
            break




if __name__ == "__main__":
    main()

