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
import subprocess
import json
from libby.logger import logger
from kodijson import Kodi
from ampiOled import AmpiOled


logging = True


run_path =  os.path.dirname(os.path.abspath(__file__))

mute = False # Als global zu benutzen
volume = 35 # Als global zu benutzen
reboot_count = 0

#Listen der erlaubten Kommandos
valid_sources = ['CD', 'Schneitzlberger', 'Portable', 'Hilfssherriffeingang', 'Bladdnspiela', 'Himbeer314']
valid_vol_cmd = ['up', 'down', 'mute']
source = "Schneitzlberger"
msg = "Schneitzlberger"
#clear_display = 0


# Liste der Hyperion-Farben
hyperion_color_list = ["Off", "Kodi", "BluRay", "Schrank", "FF8600", "red" , "green"]
hyperion_color = 1 # Als global zu benutzen



eth_addr='osmd.fritz.box'
udp_port=5005 #An diesen Port wird der UDP-Server gebunden
tcp_port=5015

logger("Starting UDP-Server at " + eth_addr + ":" + str(udp_port),logging)
e_udp_sock = socket.socket( socket.AF_INET,  socket.SOCK_DGRAM )
e_udp_sock.bind( (eth_addr,udp_port) )

def signal_term_handler(signal, frame):
    global e_udp_sock
    global t_stop
    global lcd
    global conn
    logger("Got " + str(signal), logging)
    logger("Closing UDP Socket", logging)
    e_udp_sock.close() #UDP-Server abschiessen
    amp_power("off") #Preamp schlafen legen

    t_stop.set() #Threads ordnungsgemäss beenden

    GPIO.cleanup()   #GPIOs aufräumen
    so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    so.connect((eth_addr, tcp_port))
    so.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    so.send("foo".encode())
    so.close()
    logger("              So long sucker!", logging) #Fein auf Wiedersehen sagen
    sys.exit(0) #Und raus hier




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
    oled.setVolScreen(pot_value)
    set_volume_pot(pot_value)
    return()


def set_volume_pot(pot_value):
    i2c_iso(1) # Enable Volume I2C-Bus-Isolator
    try:
        bus.write_byte(poti_device,pot_value)
        bus.write_byte(poti_device,pot_value+64)
    except:
        logger("Couldn't set volume. Amp switched off?", logging)
    i2c_iso(0) # Disable Volume I2C-Bus-Isolator
    return()



def set_hyperion():
    global hyperion_color
    global msg
    if hyperion_color == 0:
        args = ['-c', 'black']
        msg = "Off"
        GPIO.output(Out_ext1, GPIO.LOW)
        logger("   Off", logging)
        hyperion_color += 1
    elif hyperion_color == 1:
        args = ['-x']
        msg = "Kodi"
        GPIO.output(Out_ext1, GPIO.LOW)
        logger("   Kodi", logging)
        hyperion_color +=1
    elif hyperion_color == 2:
        args = ['-x']
        v4l_ret = subprocess.Popen([run_path+'/hyp-v4l.sh', '&'])
        msg = "BluRay"
        logger("    BluRay", logging)
        GPIO.output(Out_ext1, GPIO.LOW)
        hyperion_color += 1
    elif hyperion_color == 3:
        v4l_ret = subprocess.call(['/usr/bin/killall',  'hyperion-v4l2'])
        args = ['-c',  hyperion_color_list[hyperion_color+1]]
        msg = "Farbe: "+hyperion_color_list[hyperion_color+1]+" und Schrank"
        logger("   " + hyperion_color_list[hyperion_color+1]+" und Schrank", logging)
        GPIO.output(Out_ext1, GPIO.HIGH)
        hyperion_color += 1
    elif hyperion_color > 3:
        args = ['-c',  hyperion_color_list[hyperion_color]]
        msg = "Farbe: "+hyperion_color_list[hyperion_color]
        logger("   " + hyperion_color_list[hyperion_color], logging)
        GPIO.output(Out_ext1, GPIO.LOW)
        if hyperion_color == len(hyperion_color_list)-1:
           hyperion_color = 0
        else:
           hyperion_color += 1
    else:
        hyperion_color = 0
        return()
    cmd = ['/usr/bin/hyperion-remote']
    cmd = cmd+args
    hyp = subprocess.call(cmd)
    return()






def get_mcp_int():
    #Diese Funktion wird aufgerufen, wenn ein Interrupt vom MCP eintrudelt. Als erstes
    #wird das intcap-Register ausgelesen, um festzustellen, welcher Taster gedrückt wurde:
    intcap = bus.read_byte_data(mcp_device,mcp_intcapa)  # Read Intcap-Register from MCP23017
    #Damit wird der Interrupt im MCP auch gelöscht.
    if intcap == 0x00:
       #Dieser Interrupt-Wert kommt vor, wenn ein Taster wieder losgelassen wird. Hier wird einfach nix getan
       ret = "Nixtun"
    elif intcap == 0x08:
       ret = "Schneitzlberger"
    elif intcap == 0x40:
       ret = "CD"
    elif intcap == 0x80:
       ret = "Portable"
    elif intcap == 0x04:
       ret = "Hilfssherriffeingang"
    elif intcap == 0x01:
       ret = "Bladdnspiela"
    elif intcap == 0x02:
       ret = "Himbeer314"
    elif intcap == 0x20:
       ret = "hyperion"
    elif intcap == 0x10:
       ret = "dim_sw"
    else:
       ret = "Error"
    return(ret)


class Hardware():
    def __init__(self, oled):
        logger("init class hardware",logging)
        import RPi.GPIO as GPIO
        import smbus
        #import threading
        self.mcp_device = 0x20 # Device Adresse (A0-A2)
        self.mcp_iodira = 0x00 # Pin Register fuer die Richtung Port A
        self.mcp_iodirb = 0x01 # Pin Register fuer die Richtung Port B
        self.mcp_olatb = 0x15 # Register fuer Ausgabe (GPB)
        self.mcp_gpioa = 0x12 # Register fuer Eingabe (GPA)
        self.mcp_gpintena = 0x04 # Interrupt Enable Reigster (GPA)
        self.mcp_defvala = 0x06 # Default Comparison Value for Interrupt (GPA)
        self.mcp_intcona = 0x08 # Intertupt on change control register (GPA)
        self.mcp_intcapa = 0x10 # Register INTCAPA

        self.bus = smbus.SMBus(1) # Rev 2 Pi

        self.poti_device = 0x2f  #I2C-Adresse DS1882

        self.Out_ext1 = 16
        self.Out_ext2 = 18
        self.Out_pwr_rel = 29
        self.Out_i2c_iso = 32
        self.In_mcp_int = 37
        self.In_vol_down = 7
        self.In_vol_up = 36
        self.In_mute = 15
        self.min_vol = 63  #63 für 63 Wiper Positionen, 33 für 33 Wiper Positionen

        self.oled = oled

        self.initGpios()

        self.t_stop = threading.Event()
        # call thread to clear mcp interrupt from time to time (in case of error)
        self.clearMcpInt()

        pass
    def __del__(self):
        pass

    def initGpios(self):
        #set up GPIOs
        logger("init GPIOs", logging)
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) # Nutzung der Pin-Nummerierung, nicht GPIO-Nummegn
        GPIO.setup(self.Out_ext1, GPIO.OUT) # EXT1 -> for control of external Relais etc.
        GPIO.setup(self.Out_ext2, GPIO.OUT) # EXT2 -> for control of external Relais etc.
        GPIO.setup(self.Out_pwr_rel, GPIO.OUT) # PWR_REL -> for control of amp power supply (vol_ctrl, riaa_amp)
        GPIO.setup(self.Out_i2c_iso, GPIO.OUT) # Enable/Disable Volume I2C-Bus-Isolator
        GPIO.output(self.Out_ext1, GPIO.LOW) # Switch amp power supply off
        GPIO.output(self.Out_pwr_rel, GPIO.LOW) # Switch amp power supply off
        GPIO.output(self.Out_i2c_iso, GPIO.LOW) # Disable Volume I2C-Bus-Isolator


        # Setze Port A Interrupt
        self.bus.write_byte_data(self.mcp_device, self.mcp_gpintena, 0xFF)
        self.bus.write_byte_data(self.mcp_device, self.mcp_defvala, 0x00)
        self.bus.write_byte_data(self.mcp_device, self.mcp_intcona, 0x00)

        GPIO.setup(self.In_mcp_int, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Interrupt input from MCP (GPIO26)
        GPIO.setup(self.In_vol_down, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # vol_down key
        GPIO.setup(self.In_mute, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # mute key
        GPIO.setup(self.In_vol_up, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # vol_up key

        #Set interrupts
        GPIO.add_event_detect(self.In_mcp_int, GPIO.FALLING, callback = self.gpioInt)  # Set Interrupt for MCP (GPIO26)
        GPIO.add_event_detect(self.In_mute, GPIO.RISING, callback = self.gpioInt, bouncetime = 250)  # Set Interrupt for mute key
        GPIO.add_event_detect(self.In_vol_up, GPIO.RISING, callback = self.gpioInt)  # Set Interrupt for vol_up key

        # Initial clear of MCP-Interrupt
        self.bus.read_byte_data(self.mcp_device, self.mcp_gpioa)

        # Definiere GPA als Input
        # Binaer: 0 bedeutet Output, 1 bedeutet Input
        self.bus.write_byte_data(self.mcp_device, self.mcp_iodira,0xFF)

        # Definiere alle GPB Pins als Output
        self.bus.write_byte_data(self.mcp_device, self.mcp_iodirb,0x00)


    def initMcp(self):
        pass
    def sethyperion(self):
        pass
    def setVolPot(self):
        pass

    def gpioInt(self, channel): #Interrupt Service Routine
        #This function is called, if an interrupt (GPIO) occurs; input parameter is the pin, where the interrupt occured; not needed here
        if channel == 37: #Interrupt from MCP
            src = get_mcp_int()
            if src == "Nixtun":
                return()
            elif src == "Error":
                logger("An error occured", logging)
                return()
            elif src == "dim_sw":
                global clear_display
                clear_display = not clear_display
                logger("Dim switch toggled", logging)
                return()
            elif src in valid_sources:
                logger("Switching input to " + src, logging)
                amp_power(src)
                return()
            elif src == "hyperion":
                logger("Switching hyperion to ", logging)
                set_hyperion()
                return()
        #elif channel == 7: # vol_down key pressed
        #    logger("Key volume down", logging)
        #    set_volume("vol_down")
        #    time.sleep(0.2)
        #    while GPIO.input(7) == True:
        #        set_volume("vol_down")
        #        time.sleep(0.05)
        #    return()
        elif channel == 36: # vol_up key pressed
            logger("Key volume up", logging)
            if GPIO.input(7):
                 set_volume("up")
            else:
                 set_volume("down")
            time.sleep(0.1)
            return()
        elif channel == 15: # mute key pressed
            logger("Key mute", logging)
            set_volume("mute")
            return()
        else:
            logger("An error orccured during GpioInt("+str(channel)+")", logging)
            return()

    def amp_power(self, inp):
        global msg
        global reboot_count
        if inp == "off" or inp == "Schneitzlberger":
            #Wenn die Funktion mit "off" oder "Schneitzlberger" aufgerufen wird, dann wird der
            #source auf Schneitzlberger gesetzt (Trennung von Endstufe) und der Verstärker ausgeschaltet
            #set_screen("Preamp off")
            self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x00)  # source Schneitzlberger, damit Preamp von Endstufe getrennt wird
            GPIO.output(self.Out_pwr_rel, GPIO.LOW) # Switch amp power supply off
            logger("Switch amp off", logging)
            self.setSource(inp) #Wird eigentlich nur noch einmal aufgerufen, damit im Display der source angezeigt wird
            if inp == "off":
                reboot_count = reboot_count + 1
                if reboot_count > 5:
                     logger("Rebooting Pi!", logging)
                     subprocess.Popen("reboot")
        elif inp in valid_sources:
            #Hier geht's rein, wenn nicht mit "off" oder "Schneitzlberger" aufgerufen wurde
            amp_stat = GPIO.input(self.Out_pwr_rel) # nachschauen, ob der Preamp nicht evtl. schon läuft
            if amp_stat == False:
                # Wenn der Preamp noch nicht läuft, werden die entsprechenden Meldungen ausgegeben,
                # der Eingang zur Trennung der Endstufe auf Schneitzlberger gesetzt, der Preamp
                # angeschaltet und dann (nach 2 Sekunden Wartezeit) die Option des DS1882 konfiguriert
                # sowie die letzte Lautstärke gesetzt und schlussendlich der entsprechende Eingang
                # ausgewählt.
                msg = "Switching preamp on"
                #set_screen("Switching preamp on")
                self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x00)  # source Schneitzlberger, damit Preamp von Endstufe getrennt wird
                GPIO.output(self.Out_pwr_rel, GPIO.HIGH) # Switch amp power supply on
                logger("Switching amp on", logging)
                time.sleep(2)
                self.volIsolate(1) # Enable Volume I2C-Bus-Isolator
                if self.min_vol == 33:
                    self.bus.write_byte(self.poti_device, 0x87) #DS1882 auf 33 Wiper Positionen konfigurieren
                elif self.min_vol == 63:
                    self.bus.write_byte(poti_device,0x86) #DS1882 auf 63 Wiper Positionen konfigurieren
                self.volIsolator(0) # Disable Volume I2C-Bus-Isolator
                set_volume("sel_vol="+str(volume)) #Aktuellen Lautstärke setzen
                self.setSource(inp) #Eingang auswählen
            else:
                #Der Preamp läuft wohl schon, also muss nur noch der Eingang gesetzt werden
                logger("Amp is already running", logging)
                self.setSource(inp) #Eingang auswählen
        else:
            #Hier geht's rein, wenn der source-Wert nicht gültig ist
            logger("Ampswitch else ... nothing happened.", logging)
        return()

    def volIsolator(self, status):
        # Mit dieser Funktion wird der DS1882 auf den I2C-Bus geschaltet (1) oder vom Bus getrennt (0)
        if status == 1:
            GPIO.output(self.Out_i2c_iso, GPIO.HIGH) #DS1882 auf den Bus schalten
        else:
            GPIO.output(self.Out_i2c_iso, GPIO.LOW) #DS1182 vom Bus trennen
        return()

    def setSource(self, src):
        if src == "00000000":
            return()
        elif src == "Schneitzlberger":
            self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x00)
            self.oled.setMsgScreen(l1="Eingang", l3="Schneitzlberger")
        elif src == "CD":
            self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x28)
            self.oled.setMsgScreen(l1="Eingang", l3="CD")
        elif src == "Portable":
            self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x24)
            self.oled.setMsgScreen(l1="Eingang", l3="Portable")
        elif src == "Hilfssherriffeingang":
            self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x22)
            self.oled.setMsgScreen(l1="Eingang", l3="Hilfssherriff")
        elif src == "Bladdnspiela":
            self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x21)
            self.oled.setMsgScreen(l1="Eingang", l3="Bladdnspiela")
        elif src == "Himbeer314":
            self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, 0x30)
            self.oled.setMsgScreen(l1="Eingang", l3="Himbeeren")
        elif src == "off":
            self.oled.setMsgScreen(l1="Eingang", l3="Vorverstärker aus")
        else:
            logger('Komischer Elisenzustand', logging)
        return()

    def clearMcpInt(self):
        ciT = threading.Thread(target=self._clearMcpInt)
        ciT.setDaemon(True)
        ciT.start()


    def _clearMcpInt(self):
        # The function clear_int() should be called regularly to make sure,
        # that the MCP device interrupt remains not set accidently
        # In the meantime, some more things are done in this function.
        # It is called as a thread, the while loop runs every three seconds.
        global reboot_count
        while(not self.t_stop.is_set()):
            # Clear interrupts of MCP
            intcap = self.bus.read_byte_data(self.mcp_device, self.mcp_intcapa)  # Read Intcap-Register from MCP23017
            gpioa = self.bus.read_byte_data(self.mcp_device, self.mcp_gpioa)  # Read Intcap-Register from MCP23017
            self.bus.write_byte_data(self.mcp_device, self.mcp_gpintena,0x00)
            self.bus.write_byte_data(self.mcp_device, self.mcp_gpintena,0xFF)
            intcap = 0
            # Interrupt of MCP cleared
            reboot_count = 0 # Clear reboot counter
            self.t_stop.wait(3)
            pass




class Ampi():
    def __init__(self):
        pass

    def __del__(self):
        pass

    def setVolume(self):
        pass

    def setInput(self):
        pass




def main():
    #global e_udp_sock
    global t_stop

    oled = AmpiOled()

    logger("Starting amplifier control service", logging)

    #Starte handler für SIGTERM (kill -15), also normales beenden
    #Handler wird aufgerufen, wenn das Programm beendet wird, z.B. durch systemctl
    signal.signal(signal.SIGTERM, signal_term_handler)


    #Init of GPIOs and MCP port expander
    hw = Hardware(oled)


    #amp_status = True
    hw.amp_power("off") #Be sure, that preamp is switched off
    time.sleep(1.1) #Short break to make sure the display is cleaned

    hw.setSource("Schneitzlberger")  #Set initial source to Schneitzlberger
    #set_hyperion()



    #tcpServer_t = Thread(target=tcpServer, args=(1, t_stop))
    #tcpServer_t.start()




    while True:
        try:
            data, addr = e_udp_sock.recvfrom( 1024 )# Puffer-Groesse ist 1024 Bytes.
            remote(data) # Abfrage der Fernbedienung (UDP-Server), der Rest passiert per Interrupt/Event
        except KeyboardInterrupt: # CTRL+C exit
            signal_term_handler(99, "") #Aufrufen des Signal-Handlers, in der Funktion wird das Programm sauber beendet
            break


if __name__ == "__main__":
    main()

