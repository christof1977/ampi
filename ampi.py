#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import datetime
import smbus
import syslog
import socket
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
from hardware import Hardware
from hypctrl import Hypctrl
from tcpServer import MyTCPSocketHandler
import socketserver

logging = True

reboot_count = 0

eth_addr=''
udp_port=5005 #An diesen Port wird der UDP-Server gebunden
tcp_port=5015



class Ampi():
    def __init__(self):

        logger("Starting amplifier control service", logging)

        self.validVolCmd = ['Up', 'Down', 'Mute']
        self.toggleinputs = ['Himbeer314', 'CD', 'Bladdnspiela' , 'Portable', 'Hilfssherriff']
        self.oled = AmpiOled()
        self.hyp = Hypctrl(self.oled)
        #Starte handler für SIGTERM (kill -15), also normales beenden
        #Handler wird aufgerufen, wenn das Programm beendet wird, z.B. durch systemctl
        signal.signal(signal.SIGTERM, self.signal_term_handler)

        self.hw = Hardware(self.oled, self.hyp)

        time.sleep(1.1) #Short break to make sure the display is cleaned

        self.hw.setSource("Aus")  #Set initial source to Aus
        self.mc_restart_cnt = 0
        self.t_stop = threading.Event()
        self.clearTimer()

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
        logger("              So long sucker!", logging) #Fein auf Wiedersehen sagen
        sys.exit(0) #Und raus hier

    def clearTimer(self):
        ciT = threading.Thread(target=self._clearTimer)
        ciT.setDaemon(True)
        ciT.start()

    def _clearTimer(self):
        while(not self.t_stop.is_set()):
            self.mc_restart_cnt = 0 # Clear mediacenter reboot counter
            self.t_stop.wait(3)

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
                logger(ret, logging)
                self.udpSock.sendto(str(ret).encode('utf-8'), addr)
            except Exception as e:
                logger("Uiui, beim UDP senden/empfangen hat's kracht!" + str(e))


    def stopKodiPlayer(self):
        try:
            kodi = Kodi("http://localhost/jsonrpc")
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

    def selectOutput(self, jcmd):
        logger("Output: " + jcmd['Parameter'], logging)
        ret = self.hw.selectOutput(jcmd['Parameter'])
        return ret

    def ampiZustand(self):
        zustand  = json.dumps({"Antwort" : "Zustand",
                               "Input" : self.hw.getSource(),
                               "Hyperion" : self.hyp.getScene(),
                               "Volume" : self.hw.volume.getVolume(),
                               "OledBlank" : self.hw.oled.getBlankScreen(),
                               "TV" : self.hw.getTvPwr(),
                               "PA2200" : self.hw.getAmpPwr(),
                               "Amp-Ausgang" : self.hw.getAmpOut(),
                               "Headphone-Ausgang" : self.hw.getHeadOut()
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
        elif(jcmd['Aktion'] == "Output"):
            ret = self.selectOutput(jcmd)
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
                self.stopKodiPlayer()
                time.sleep(0.2)
                self.hw.setSource("Aus")
                #self.hyp.setScene("Kodi")
                logger("Aus is fuer heit!", logging)
                ret = json.dumps({"Antwort":"Betrieb","Wert":"Aus"})
            elif jcmd['Parameter'] == "Mediacenter":
                self.mc_restart_cnt += 1
                ret = json.dumps({"Antwort":"Mediacenter","Wert":"BaldRestart"})
                if self.mc_restart_cnt >= 2:
                    os.system('sudo systemctl restart mediacenter')
                    logger("Mediaceenter wird neu gestart", logging)
                    ret = json.dumps({"Antwort":"Mediacenter","Wert":"Restart"})
            elif jcmd['Parameter'] == "Input":
                src = self.hw.getSource()
                try:
                    idx = self.toggleinputs.index(src)
                    idx += 1
                    if(idx >= len(self.toggleinputs)):
                        idx = 0
                except ValueError:
                    idx = 0
                self.hw.setSource(self.toggleinputs[idx])
                ret = json.dumps({"Antwort":"Input","Wert":self.toggleinputs[idx]})
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

