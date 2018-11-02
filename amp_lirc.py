#!/usr/bin/env python3
#coding: utf8

import lirc
from libby import remoteAmpiUdp
import socket
import signal
import sys
from libby.logger import logger

logging = True


def signal_term_handler(signal, frame):
    global s_udp_sock
    logger("Got " + str(signal), logging)
    logger("Closing UDP Socket", logging)
    s_udp_sock.close()
    
    logger("Closing lirc connection", logging)
    lirc.exit()

    logger("So long, sucker!", logging)

    sys.exit(0)
 

def main():
    logger("Starting amplifier lirc remote control service", logging)

    global s_udp_sock
    signal.signal(signal.SIGTERM, signal_term_handler)
    addr = 'osmd.fritz.box'
    port = 5005
    s_udp_sock = socket.socket( socket.AF_INET,  socket.SOCK_DGRAM )
    sockid = lirc.init("lircsock")
    allow = lirc.set_blocking(True, sockid)
    
    while True:
        try:
            codeIR_list = lirc.nextcode()
            if codeIR_list != [] and codeIR_list != None:
                remoteAmpiUdp.sende(s_udp_sock, addr, port, codeIR_list[0])
                logger("Sending command " + codeIR_list[0], logging)
                codeIR_list = []
        except KeyboardInterrupt:
            signal_term_handler(99, "")
            break

if __name__ == "__main__":
    main()
