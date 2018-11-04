#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from lcdproc.server import Server
from libby.logger import logger
import threading
import time

logging = True


class AmpiOled:
    def __init__(self):
        self.oledLines = 4
        self.oledCols = 20
        self.timeoutVolScreen = 0
        self.timeoutMsgScreen = 0
        self.visibletime = 3
        self.blank = False
        self.lcd = Server("127.0.0.1", debug=False)
        self.lcd.start_session()
        self.screenVol = self.lcd.add_screen("Screen_vol")
        self.screenVol.set_heartbeat("off")
        self.screenVol.set_priority("background")

        self.screenMsg = self.lcd.add_screen("Screen_msg")
        self.screenMsg.set_heartbeat("off")
        self.screenMsg.set_priority("background")

        self.screenClear = self.lcd.add_screen("Screen_clear")
        self.screenClear.set_heartbeat("off")
        self.screenClear.set_priority("background")


        self.tStop = threading.Event()

        self.initVolScreen()
        self.initMsgScreen()

        #self.msgScreenT = threading.Thread(target=self.setMsgScreen, args=(1, self.tStop))
        #self.msgScreenT.start()

        self.clearScreenT = threading.Thread(target=self.clearScreen, args=(1, self.tStop))
        self.clearScreenT.setDaemon(True)
        self.clearScreenT.start()

        logger("Leaving set_lcd",logging)

    def __del__(self):
        self.tStop.set() #Threads ordnungsgemäss beenden

    def clearScreen(self, dummy, stop_event):
        while(not stop_event.is_set()):
            if self.blank == 1:
                self.screenClear.set_priority("input")
            else:
                self.screenClear.set_priority("hidden")

            if(self.timeoutVolScreen > self.visibletime - 1):
                self.screenVol.set_priority("background")
                self.timeoutVolScreen = 0
            else:
                self.timeoutVolScreen = self.timeoutVolScreen + 1

            if(self.timeoutMsgScreen > self.visibletime - 1):
                self.screenMsg.set_priority("background")
                self.timeoutMsgScreen = 0
            else:
                self.timeoutMsgScreen = self.timeoutMsgScreen + 1

            #print(self.timeoutVolScreen)
            stop_event.wait(1)

    def toggleBlankScreen(self): # Toggle screen blanking, takes effect with next run of clearScreen thread loop
        self.blank = not self.blank

    def findX(self, s):
        l = self.oledCols - len(s)
        return(l//2)


    def initVolScreen(self):
        self.screenVolNum1 = self.screenVol.add_number_widget("Num1Wid", x=8, value=4)
        self.screenVolNum2 = self.screenVol.add_number_widget("Num2Wid", x=11, value=2)
        self.screenVol.set_priority("input")


    def initMsgScreen(self):
        self.screenMsg.set_priority("alert")
        line1 = "Los geht's"
        line2 = "schon wieder"
        line3 = "Du"
        line4 = "Aff"
        self.screenMsgL1 = self.screenMsg.add_string_widget("string_widget_l1", line1, x=self.findX(line1), y=1)
        self.screenMsgL2 = self.screenMsg.add_string_widget("string_widget_l2", line2, x=self.findX(line2), y=2)
        self.screenMsgL3 = self.screenMsg.add_string_widget("string_widget_l3", line3, x=self.findX(line3), y=3)
        self.screenMsgL4 = self.screenMsg.add_string_widget("string_widget_l4", line4, x=self.findX(line4), y=4)


    def setVolScreen(self, value):
        self.timeoutVolScreen = 0
        if(value == "mute"):
            zehner = 6
            einer = 3
        else:
            try:
                zehner = value // 10
                einer = value % 10
            except:
                return
        self.screenVol.set_priority("input")
        self.screenVolNum1.set_value(zehner)
        self.screenVolNum2.set_value(einer)

    def setMsgScreen(self, l1="", l2="", l3="", l4=""):
        self.timeoutMsgScreen = 0
        self.screenMsg.set_priority("alert")
        self.screenMsgL1.set_x(self.findX(l1))
        self.screenMsgL2.set_x(self.findX(l2))
        self.screenMsgL3.set_x(self.findX(l3))
        self.screenMsgL4.set_x(self.findX(l4))
        self.screenMsgL1.set_text(l1)
        self.screenMsgL2.set_text(l2)
        self.screenMsgL3.set_text(l3)
        self.screenMsgL4.set_text(l4)


def main():
    oled = AmpiOled()
    #time.sleep(1)
    #oled.setVolScreen(17)
    #oled.toggleBlankScreen()
    #time.sleep(3)
    #oled.toggleBlankScreen()
    time.sleep(2)
    oled.setMsgScreen(l2="Zwo", l4="Fünf")
    time.sleep(5)

    oled.setMsgScreen(l1="Eins", l2="Nix", l3="Drei", l4="Auch nix")
    time.sleep(5)



if ( __name__ == "__main__" ):
    main()
