#!/usr/bin/env python3

import socketserver
import threading
import time

class MyTCPSocketHandler(socketserver.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(1024).strip()
        print("{} wrote:".format(self.client_address[0]))
        print(self.data.decode())
        self.request.sendall("Nix")


class app():
    def __init__(self):
        self.tcpServerThread()
        pass

    def tcpServerThread(self):
        sT = threading.Thread(target = self._serverThread)
        sT.setDaemon(True)
        sT.start()

    def _tcpServerThread(self):
        # instantiate the server, and bind to localhost on port 9999
        HOST,PORT = "osmd.fritz.box", 9999
        # activate the server
        server = socketserver.TCPServer((HOST, PORT), MyTCPSocketHandler)
        # this will keep running until Ctrl-C
        server.serve_forever()


if __name__ == "__main__":
    a = app()

    while True:
        print("ping")
        time.sleep(1)


