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

logging = True



reboot_count = 0

#Listen der erlaubten Kommandos
valid_sources = ['CD', 'Schneitzlberger', 'Portable', 'Hilfssherriff', 'Bladdnspiela', 'Himbeer314']
valid_vol_cmd = ['up', 'down', 'mute']
source = "Schneitzlberger"


# Liste der Hyperion-Farben
#hyperion_color = 1 # Als global zu benutzen



eth_addr='osmd.fritz.box'
udp_port=5005 #An diesen Port wird der UDP-Server gebunden
tcp_port=5015




def stop_kodi():
    try:
        kodi = Kodi("http://"+eth_addr+"/jsonrpc")
        playerid = kodi.Player.GetActivePlayers()["result"][0]["playerid"]
        result = kodi.Player.Stop({"playerid": playerid})
        logger("Kodi aus!", logging)
    except Exception as e:
        logger("Beim Kodi stoppen is wos passiert: " + str(e), logging)



def remote(data):
    data = data.decode()
    try:
        jcmd = json.loads(data)
        print(jcmd)
    except:
        logger("Das ist mal kein JSON, pff!", logging)
        valid = "nee"
        return(valid)
    global source
    if(jcmd['Aktion'] == "Input"):
        logger("Input: " + jcmd['Parameter'], logging)
        if jcmd['Parameter'] in valid_sources:
            logger("Source set remotely to " + data, logging)
            amp_power(jcmd['Parameter'])
            source = jcmd['Parameter']
            valid = "ja"
    elif(jcmd['Aktion'] == "hyperion"):
        logger("Remote hyperion control", logging)
        set_hyperion()
        valid = "ja"
    elif(jcmd['Aktion'] == "Volume"):
        if jcmd['Parameter'] in valid_vol_cmd:
            set_volume(jcmd['Parameter'])
            valid = "ja"
    elif data[:7] == "set_vol": # Ich habe keine Ahnung, was es mit dem Zweig auf sich hat!
        #logger("Set_vol to " + data[9:], logging)
        set_volume(data)
        valid = "ja"
    elif(jcmd['Aktion'] == "Switch"):
        if jcmd['Parameter'] == "dim_sw":
            global clear_display
            clear_display = not clear_display
            logger("Dim remote command toggled", logging)
            #source = "Schneitzlberger"
            valid = "ja"
        elif jcmd['Parameter'] == "power":
            amp_power("off")
            global hyperion_color
            hyperion_color = 1
            set_hyperion()
            stop_kodi()
            logger("Aus is fuer heit!", logging)
            valid = "ja"
        else:
            logger("Des bassd net.", logging)
            valid = "nee"
    elif data == "zustand":
        valid = "zustand"
    else:
        logger(data, logging)
        logger("Invalid remote command!", logging)
        valid = "nee"
    return(valid)








class Hardware():
    def __init__(self, oled, hyp):
        logger("init class hardware",logging)
        import RPi.GPIO as GPIO
        import smbus
        #import threading
        self.bus = smbus.SMBus(1) # Rev 2 Pi


        self.Out_ext2 = 18
        self.Out_pwr_rel = 29
        self.In_mcp_int = 37
        self.In_vol_down = 7
        self.In_vol_up = 36
        self.In_mute = 15

        self.oled = oled
        self.hyp = hyp

        self.initGpios()

        self.volume = Volume(self.oled, self.bus)

        #self.t_stop = threading.Event()
        # call thread to clear mcp interrupt from time to time (in case of error)
        self.sources = Sources(self.oled, self.bus)
        #sources..clearMcpInt()

    def __del__(self):
        pass

    def initGpios(self):
        #set up GPIOs
        logger("init GPIOs", logging)
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.Out_ext2, GPIO.OUT) # EXT2 -> for control of external Relais etc.
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
            elif src in valid_sources:
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
                volume.incVolumePot()
            else: # Linksrum drehn
                logger("Leiser", logging)
                volume.decVolumePot()
            time.sleep(0.1)
            return()
        elif channel == 15: # mute key pressed
            logger("Ton aus", logging)
            volume.setVolumePot(self.minVol)
            return()
        else:
            logger("An error orccured during GpioInt("+str(channel)+")", logging)
            return()

    def ampPwr(self, val):
        # Hier wird später der Leistungsverstärker an und ausgeschaltet
        logger("PA2200: "+str(val))
        pass

    def tvPwr(self, val):
        # Hier wird später der Fernseher an- und ausgeschaltet
        logger("TV: "+str(val))
        pass

    def ampiPwr(self, val):
        try:
            if(val == True):
                amp_stat = GPIO.input(self.Out_pwr_rel) # nachschauen, ob der Preamp nicht evtl. schon läuft
                if amp_stat == False:
                    self.sources.setMcpOut("Aus") # source Schneitzlberger, damit Preamp von Endstufe getrennt wird
                    GPIO.output(self.Out_pwr_rel, GPIO.HIGH) # Switch amp power supply on
                    logger("Ampi anmachen", logging)
                    time.sleep(1)
                    self.setPotWiper()
                    time.sleep(1)
                    volume.setVolumePot(self.volPotVal) #Aktuellen Lautstärke setzen
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


    def setSource(self, src):
        if src == "00000000":
            return()
        elif src == "Schneitzlberger":
            self.tvPwr(True)
            self.ampPwr(True)
            self.ampiPwr(False)
            self.sources.setMcpOut(src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "CD":
            self.tvPwr(False)
            self.ampPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Portable":
            self.tvPwr(False)
            self.ampPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Hilfssherriff":
            self.tvPwr(False)
            self.ampPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Bladdnspiela":
            self.tvPwr(False)
            self.ampPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Himbeer314":
            self.tvPwr(False)
            self.ampPwr(True)
            self.ampiPwr(True)
            self.sources.setMcpOut(src)
            self.oled.setMsgScreen(l1="Eingang", l3=src)
        elif src == "Aus":
            self.oled.setMsgScreen(l1="Eingang", l3="Alles aus etz!")
            self.sources.setMcpOut("Schneitzlberger")
            self.tvPwr(False)
            self.ampPwr(False)
            self.ampiPwr(False)
            #Todo: hyperion auschalten
        else:
            logger('Komischer Elisenzustand', logging)
        return()



class Ampi():
    def __init__(self):

        logger("Starting amplifier control service", logging)

        self.oled = AmpiOled()
        self.hyp = Hypctrl(self.oled)
        #Starte handler für SIGTERM (kill -15), also normales beenden
        #Handler wird aufgerufen, wenn das Programm beendet wird, z.B. durch systemctl
        signal.signal(signal.SIGTERM, self.signal_term_handler)

        self.hw = Hardware(self.oled, self.hyp)

        time.sleep(1.1) #Short break to make sure the display is cleaned

        self.hw.setSource("Aus")  #Set initial source to Aus

        logger("Starting UDP-Server at " + eth_addr + ":" + str(udp_port),logging)
        self.e_udp_sock = socket.socket( socket.AF_INET,  socket.SOCK_DGRAM )
        self.e_udp_sock.bind( (eth_addr,udp_port) )



        #tcpServer_t = Thread(target=tcpServer, args=(1, t_stop))
        #tcpServer_t.start()



        logger("Amplifier control service running", logging)


    def __del__(self):
        pass

    def signal_term_handler(self, signal, frame):
        logger("Got " + str(signal), logging)
        logger("Closing UDP Socket", logging)
        self.e_udp_sock.close() #UDP-Server abschiessen
        self.hw.setSource("off") #Preamp schlafen legen

        GPIO.cleanup()   #GPIOs aufräumen
        #so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #so.connect((eth_addr, tcp_port))
        #so.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #so.send("foo".encode())
        #so.close()
        logger("              So long sucker!", logging) #Fein auf Wiedersehen sagen
        sys.exit(0) #Und raus hier


    def setVolume(self):
        pass

    def setInput(self):
        pass

def set_volume(cmd):
    global mute
    global volume
    global oled
    if cmd == "mute":
        mute = not mute
        if mute == True:
            pot_value = min_vol
        else:
            pot_value = volume
    elif cmd == "up":
        mute = False
        if volume > 0:
            volume -= 1
        pot_value = volume
    elif cmd == "down":
        mute = False
        if volume < min_vol:
            volume +=1
        pot_value = volume
    elif cmd[:7] == "set_vol":
        mute = False
        try:
            pot_value = abs(int(cmd[8:]))
            volume = pot_value
        except:
            pot_value = volume
    else:
        pot_value = volume
    logger("Setting Volume: -" + str(pot_value) + "dB", logging)
    #hw.setVolumePot(pot_value)
    return()



def main():
    ampi = Ampi()
    while True:
        try:
            data, addr = ampi.e_udp_sock.recvfrom( 1024 )# Puffer-Groesse ist 1024 Bytes.
            remote(data) # Abfrage der Fernbedienung (UDP-Server), der Rest passiert per Interrupt/Event
        except KeyboardInterrupt: # CTRL+C exit
            ampi.signal_term_handler(99, "") #Aufrufen des Signal-Handlers, in der Funktion wird das Programm sauber beendet
            break




if __name__ == "__main__":
    main()

