#!/usr/bin/env python3
#coding: utf8

import lirc
from libby import remoteAmpi
import socket
import signal
import sys
import json
import logging
from systemd.journal import JournaldLogHandler

log = logging.getLogger('LIRCAMPI')
log.addHandler(JournaldLogHandler())
log.setLevel(logging.INFO)




def signal_term_handler(signal, frame=""):
    log.info("Got " + str(signal))
    log.info("Closing lirc connection")
    lirc.deinit()
    log.info("So long, sucker!")
    sys.exit(0)


def lirc2json(cmd):
    cmd = cmd.split("_")
    cmd = { "Aktion": cmd[0], "Parameter": cmd[1]}
    json_cmd = json.dumps(cmd)
    return json_cmd


def main():
    log.info("Starting amplifier lirc remote control service")

    signal.signal(signal.SIGTERM, signal_term_handler)
    addr = 'osmd.fritz.box'
    port = 5005
    sockid = lirc.init("lircsock")
    allow = lirc.set_blocking(False, sockid)

    while True:
        try:
            codeIR_list = lirc.nextcode()
            if(codeIR_list != [] and codeIR_list != None):
                json_cmd = lirc2json(codeIR_list[0])
                remoteAmpi.udpRemote(json_cmd, addr=addr, port=port)
                log.info("Sending command %s", json_cmd)
                codeIR_list = []
        except KeyboardInterrupt:
            signal_term_handler(99)
            break
        except Exception as e:
            log.info(str(e))


if __name__ == "__main__":
    main()
