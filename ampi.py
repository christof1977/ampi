#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import datetime
import smbus
import socket
import threading
from threading import Thread
import signal
import fcntl
import struct
import math
import select
import json
import logging
import logging.handlers
from kodijson import Kodi
from oledctrl import AmpiOled
from hardware import Hardware
from hypctrl import Hypctrl
from tcpServer import MyTCPSocketHandler
import socketserver


reboot_count = 0

eth_addr=''
udp_port=5005 #An diesen Port wird der UDP-Server gebunden
tcp_port=5015

# create logger
if(__name__ == "__main__"):
    logging.basicConfig(level=logging.INFO)
    #logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger()
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    formatter = logging.Formatter('Ampi: %(module)s: %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    #logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("Ampi")
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    formatter = logging.Formatter('Ampi: %(module)s: %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class Ampi():
    def __init__(self):

        logger.info("Starting amplifier control service")

        self.validVolCmd = ['Up', 'Down', 'Mute']
        self.toggleinputs = ['Himbeer314', 'CD', 'Bladdnspiela' , 'Portable', 'Hilfssherriff']
        self.oled = AmpiOled()
        self.hyp = Hypctrl(self.oled)
        #Starte handler für SIGTERM (kill -15), also normales beenden
        #Handler wird aufgerufen, wenn das Programm beendet wird, z.B. durch systemctl
        signal.signal(signal.SIGTERM, self.signal_term_handler)

        self.hw = Hardware(self.oled, self.hyp)

        time.sleep(1.1) #Short break to make sure the display is cleaned

        self.hw.set_source("Aus")  #Set initial source to Aus
        self.mc_restart_cnt = 0
        self.t_stop = threading.Event()
        self.clearTimer()

        self.udpServer()
        self.tcpServer()

        #tcpServer_t = Thread(target=tcpServer, args=(1, t_stop))
        #tcpServer_t.start()



        logger.info("Amplifier control service running")


    def __del__(self):
        pass

    def signal_term_handler(self, signal, frame):
        logger.info("Got " + str(signal))
        logger.info("Closing UDP Socket")
        self.udpSock.close() #UDP-Server abschiessen
        self.hw.set_source("Aus") #Preamp schlafen legen
        self.hw.stop()

        logger.info("So long sucker!") #Fein auf Wiedersehen sagen
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
        logger.info("Starting UDP-Server at {}:{}".format(eth_addr, udp_port))
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
                logger.info(ret)
                self.udpSock.sendto(str(ret).encode('utf-8'), addr)
            except Exception as e:
                logger.warning("Uiui, beim UDP senden/empfangen hat's kracht: {}".format(str(e)))

    def stopKodiPlayer(self):
        try:
            kodi = Kodi("http://localhost/jsonrpc")
            playerid = kodi.Player.GetActivePlayers()["result"][0]["playerid"]
            result = kodi.Player.Stop({"playerid": playerid})
            logger.info("Kodi aus!")
        except Exception as e:
            logger.warning("Beim Kodi stoppen is wos passiert: {}".format(str(e)))
            logger.warning(e)

    def get_sources(self):
        '''Returns list of available sources
        '''
        return json.dumps({"Available Sources":self.hw.valid_sources})

    def get_source(self):
        '''Returns list of valid sources
        '''
        return json.dumps({"Source":self.hw.getSource()})

    def set_source(self, source):
        logger.info("Input: {}".format(source))
        logger.info("Source set remotely to {}".format(source))
        ret = self.hw.set_source(source)
        #ret = self.hw.getSource()
        logging.info(ret)
        if(ret == -1):
            ret = {"Answer":"Error"}
        else:
            ret["Answer"] = "Success"
        return(json.dumps(ret))

    def get_output(self):
        ret = self.hw.get_output()
        return(json.dumps(ret))

    def set_output(self, output):
        logger.info("Output: {}".format(output))
        ret = self.hw.set_output(output)
        if ret == -1:
            ret = {"Answer":"Error"}
        else:
            ret = {"Answer":"Success", "Output":ret}
        return(json.dumps(ret))

    def status(self):
        zustand  = json.dumps({"Answer" : "Zustand",
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
            logger.warning("Das ist mal kein JSON, pff!")
            ret = json.dumps({"Answer": "Not a valid JSON String"})
        if(jcmd['Aktion'] == "Input"):
            ret = self.set_source(jcmd["Parameter"])
        elif(jcmd['Aktion'] == "Output"):
            ret = self.set_output(jcmd["Parameter"])
            ret = json.dumps({"Answer": jcmd, "Value": ret})
        elif(jcmd['Aktion'] == "Hyperion"):
            logger.info("Remote hyperion control")
            ret = json.dumps({"Answer": "Hyperion", "Scene": self.hyp.setScene()})
        elif(jcmd['Aktion'] == "Volume"):
            if jcmd['Parameter'] in self.validVolCmd:
                ret = self.set_volume(jcmd['Parameter'])
            else:
                ret = json.dumps({"Answer": "Kein echtes Volumen-Kommando"})
        elif(jcmd['Aktion'] == "Switch"):
            if jcmd['Parameter'] == "DimOled":
                ret = self.hw.oled.toggleBlankScreen()
                logger.info("Dim remote command toggled")
                if(ret):
                    ret = json.dumps({"Answer":"Oled","Value":"Aus"})
                else:
                    ret = json.dumps({"Answer":"Oled","Value":"An"})
            elif jcmd['Parameter'] == "Power":
                self.stopKodiPlayer()
                time.sleep(0.2)
                self.hw.set_source("Aus")
                #self.hyp.setScene("Kodi")
                logger.info("Aus is fuer heit!")
                ret = json.dumps({"Answer":"Betrieb","Value":"Off"})
            elif jcmd['Parameter'] == "Mediacenter":
                self.mc_restart_cnt += 1
                ret = json.dumps({"Answer":"Mediacenter","Value":"BaldRestart"})
                if self.mc_restart_cnt >= 2:
                    os.system('sudo systemctl restart mediacenter')
                    logger.info("Mediaceenter wird neu gestart")
                    ret = json.dumps({"Answer":"Mediacenter","Value":"Restart"})
            elif jcmd['Parameter'] == "Input":
                src = self.hw.getSource()
                try:
                    idx = self.toggleinputs.index(src)
                    idx += 1
                    if(idx >= len(self.toggleinputs)):
                        idx = 0
                except ValueError:
                    idx = 0
                self.hw.set_source(self.toggleinputs[idx])
                ret = json.dumps({"Answer":"Input","Value":self.toggleinputs[idx]})
            else:
                logger.warning("Des bassd net.")
                ret = json.dumps({"Answer":"Schalter","Value":"Kein gültiges Schalter-Kommando"})
        elif(jcmd['Aktion'] == "Zustand"):
            logger.info("Wos für a Zustand?")
            ret = self.status()
            #TODO: Alle Zustände lesen und ausgeben
        else:
            logger.warning("Invalid remote command: {}".format(data))
            ret = json.dumps({"Answer":"Fehler","Wert":"Kein gültiges Kommando"})
        return(ret)

    def get_alive(self):
        '''Returns alive signal
        '''
        dt = datetime.datetime.now()
        dts = "{:02d}:{:02d}:{:02d}".format(dt.hour, dt.minute, dt.second)
        return(json.dumps({"name":"ampi","answer":"Freilich", "time" : dts}))

    def get_volume(self):
        ret = {"Answer":"Volume","Volume" : self.hw.volume.getVolume()}
        return(json.dumps(ret))

    def set_volume(self, val):
        logger.info(val)
        if(val in ["Up", "up", "UP"]):
            ret = self.hw.volume.incVolumePot()
        elif(val in ["Down", "down", "DOWN"]):
            ret = self.hw.volume.decVolumePot()
        else:
            ret = self.hw.volume.toggleMute()
        if(ret == -1):
            ret = {"Answer":"bassd net","Input":ret}
        else:
            ret = {"Answer":"bassd","Input":ret}
        return(json.dumps(ret))

    def run(self):
        while True:
            try:
                time.sleep(1)
                pass
            except KeyboardInterrupt: # CTRL+C exit
                self.signal_term_handler(99, "") #Aufrufen des Signal-Handlers, in der Funktion wird das Programm sauber beendet
                break





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

