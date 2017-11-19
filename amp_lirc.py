#!/usr/bin/env python2.7

#coding: utf8
import pylirc
import remoteUdp
import socket
import signal
import sys
import syslog

def signal_term_handler(signal, frame):
    global s_udp_sock
    log = "Got " + str(signal)
    print(log)
    syslog.syslog(log)
    log = "Closing UDP Socket"
    print(log)
    syslog.syslog(log)
    s_udp_sock.close()
    
    log = "Closing lirc connection"
    print(log)
    syslog.syslog(log)
    pylirc.exit()

    log = "Bye"
    print(log)
    syslog.syslog(log)

    sys.exit(0)
 

def main():
    log = "Starting amplifier lirc remote control service"
    print(log)
    syslog.syslog(log)

    global s_udp_sock
    signal.signal(signal.SIGTERM, signal_term_handler)
    #addr = '127.0.0.1'
    addr = 'osmd.fritz.box'
    port = 5005
    s_udp_sock = socket.socket( socket.AF_INET,  socket.SOCK_DGRAM )
    sockid = pylirc.init("lircsock")
    allow = pylirc.blocking(1)
    
    while True:
        try:
            codeIR_list = pylirc.nextcode()
            if codeIR_list != [] and codeIR_list != None:
                remoteUdp.sende(s_udp_sock, addr, port, codeIR_list[0])
                log = "Sending command " + codeIR_list[0]
                print(log)
                syslog.syslog(log)
                codeIR_list = []
        except KeyboardInterrupt:
            signal_term_handler(99, "")
            break

if __name__ == "__main__":
    main()
