#!/usr/bin/env python2.7

import socket
import sys
import syslog

#global s_udp_sock 

def hilf():
    print ''
    print '*******************************'
    print 'amp_ctrl.py console remote tool'    
    #print 'Connection::'
    #print 'Address=' + addr
    #print 'Port=' + port
    print ''
    print 'Commands:'
    print 'c  -> Input CD'
    print 's  -> Input Schneitzlberger'
    print 'b  -> Input Bladdnspiela'
    print 'p  -> Input Portable'
    print 'h  -> Input Hilfssherriff'
    print '3  -> Input Himbeer314'
    print ''
    print 'u  -> Volume up'
    print 'd  -> Volume down'
    print 'm  -> Mute/Unmute'
    print 'o  -> OLED on/off'
    print ''
    print 'k  -> Change Background Color'
    print '?  -> This Text'
    print 'q  -> Quit'


def getch():
        import sys, tty, termios
        fd = sys.stdin.fileno( )
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def sende(udp_socket,addr,port,msg):
    #global s_udp_sock
    #global Ziel
    #global Port 
    print "Gewaehlter Eingang:", msg 
    udp_socket.sendto( msg, (addr,port) )
 
def main():
    #addr = '127.0.0.1'
    addr = 'osmd.fritz.box'
    #addr = '192.168.178.37'
    port = 5005

    #win = curses.initscr()
    #curses.cbreak()
    #win.nodelay(True)

 
    #global s_udp_sock
    s_udp_sock = socket.socket( socket.AF_INET,  socket.SOCK_DGRAM )
    
    valid_cmds = ['CD', 'Schneitzlberger', 'Portable', 'Hilfssherriffeingang', 'Bladdnspiela', 'Himbeer314', 'hyperion', 'vol_up', 'vol_down', 'mute' ] 
   
    if len(sys.argv) == 1:
       hilf()
       while True:
           try:
               cmd = getch()
               if cmd == "c":
                   sende(s_udp_sock, addr, port, "CD")
               elif cmd == "s":
                   sende(s_udp_sock, addr, port, "Schneitzlberger")
               elif cmd == "p":
                   sende(s_udp_sock, addr, port, "Portable")
               elif cmd == "h":
                   sende(s_udp_sock, addr, port, "Hilfssherriffeingang")
               elif cmd == "b":
                   sende(s_udp_sock, addr, port, "Bladdnspiela")
               elif cmd == "3":
                   sende(s_udp_sock, addr, port, "Himbeer314")
               elif cmd == "k":
                   sende(s_udp_sock, addr, port, "hyperion")
               elif cmd == "u":
                   sende(s_udp_sock, addr, port, "vol_up")
               elif cmd == "d":
                   sende(s_udp_sock, addr, port, "vol_down")
               elif cmd == "m":
                   sende(s_udp_sock, addr, port, "mute")
               elif cmd == "o":
                  sende(s_udp_sock, addr, port, "dim_sw")
               elif cmd == "f":
                  sende(s_udp_sock, addr, port, "krampf")
               elif cmd == "?":
                  hilf()
               elif cmd == "q":
                  print("Bye")
                  break
           except KeyboardInterrupt:
               print("Bye")
               break
    elif len(sys.argv) == 2:
        if sys.argv[1] in valid_cmds:
            log = "Die Fernbedienung sagt: " + sys.argv[1]
            print(log)
            syslog.syslog(log)
            sende(s_udp_sock, addr, port, sys.argv[1])
            return()
        else:
            log = "Not a valid command"
            print(log)
            syslog.syslog(log)
            return()
    else:
        log = "Not a valid command"
        print(log)
        syslog.syslog(log)
        return()



if __name__ == "__main__":
   main() 
                                          


