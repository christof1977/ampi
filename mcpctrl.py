#!/usr/bin/env python3

from libby.logger import logger
import threading

logging = True

class Sources():
    def __init__(self, oled, bus):
        logger("Sourcenklasse laaft an", logging)
        self.oled = oled
        self.bus = bus


        self.mcp_device = 0x20 # Device Adresse (A0-A2)
        self.mcp_iodira = 0x00 # Pin Register fuer die Richtung Port A
        self.mcp_iodirb = 0x01 # Pin Register fuer die Richtung Port B
        self.mcp_olatb = 0x15 # Register fuer Ausgabe (GPB)
        self.mcp_gpioa = 0x12 # Register fuer Eingabe (GPA)
        self.mcp_gpintena = 0x04 # Interrupt Enable Reigster (GPA)
        self.mcp_defvala = 0x06 # Default Comparison Value for Interrupt (GPA)
        self.mcp_intcona = 0x08 # Intertupt on change control register (GPA)
        self.mcp_intcapa = 0x10 # Register INTCAPA

        # Initial clear of MCP-Interrupt
        self.bus.read_byte_data(self.mcp_device, self.mcp_gpioa)
        #self.mcpOutputs = {"Aus":0x00,"Schneitzlberger":0x00, "CD":0x28, "Portable":0x24,"Hilfssherriff":0x22,"Bladdnspiela":0x21,"Himbeer314":0x30}
        self.mcpOutputs = {"Aus":0x00,"Schneitzlberger":0x01, "CD":0x20, "Portable":0x08,"Hilfssherriff":0x10,"Bladdnspiela":0x04,"Himbeer314":0x02}

        # Definiere GPA als Input
        # Binaer: 0 bedeutet Output, 1 bedeutet Input
        self.bus.write_byte_data(self.mcp_device, self.mcp_iodira,0xFF)

        # Definiere alle GPB Pins als Output
        self.bus.write_byte_data(self.mcp_device, self.mcp_iodirb,0x00)
        self.t_stop = threading.Event()
        self.clearMcpInt()


    def setAmpOut(self, *args):
        # Amp-Bit: 0x40
        state = self.getMcpOut()
        if self.getAmpOut():
            newState = state & 0b10111111
        else:
            newState = state | 0b01000000
        self.setMcpOut(newState)
        return self.getAmpOut()


    def getAmpOut(self):
        # Amp-Bit: 0x40
        mcpState = self.getMcpOut()
        if mcpState & 0x40:
            #logger("Amp-Ausgang aktiv")
            ampState = True
        else:
            #logger("Amp-Ausgang inaktiv")
            ampState = False
        return ampState

    def setHeadOut(self, *args):
        # Amp-Bit: 0x80
        state = self.getMcpOut()
        if self.getHeadOut():
            newState = state & 0b01111111
        else:
            newState = state | 0b10000000
        self.setMcpOut(newState)
        return self.getHeadOut()



    def getHeadOut(self):
        # Head-Bit: 0x80
        mcpState = self.getMcpOut()
        if mcpState & 0x80:
            logger("Headphhone-Ausgang aktiv")
            headState = True
        else:
            logger("Headphone-Ausgang inaktiv")
            headState = False
        return headState


    def setInput(self, val):
        self.setMcpOut(self.mcpOutputs[val])

    def setMcpOut(self, val):
        self.bus.write_byte_data(self.mcp_device, self.mcp_olatb, val)
        #logger("Setz den MCP auf: "+str(self.mcpOutputs[val]),logging)

    def getMcpOut(self):
        olatte = self.bus.read_byte_data(self.mcp_device, self.mcp_olatb)
        return(olatte)


    def getMcpInt(self):
        #Diese Funktion wird aufgerufen, wenn ein Interrupt vom MCP eintrudelt. Als erstes
        #wird das intcap-Register ausgelesen, um festzustellen, welcher Taster gedrückt wurde:
        intcap = self.bus.read_byte_data(self.mcp_device,self.mcp_intcapa)  # Read Intcap-Register from MCP23017
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
           ret = "Hilfssherriff"
        elif intcap == 0x01:
           ret = "Bladdnspiela"
        elif intcap == 0x02:
           ret = "Himbeer314"
        elif intcap == 0x20:
           ret = "Hyperion"
        elif intcap == 0x10:
           ret = "DimOled"
        else:
           ret = "Error"
        return(ret)




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



