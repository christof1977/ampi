#!/usr/bin/env python3


#def get_ip_address(ifname):
#    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#    ip = socket.inet_ntoa(fcntl.ioctl(
#        s.fileno(),
#        0x8915,  # SIOCGIFADDR
#        struct.pack('256s', ifname[:15])
#    )[20:24])
#    s.close()
#    return ip

def tcpServer(dummy, stop_event):
 global t_stop
 s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
 s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
 s.bind((eth_addr, tcp_port))
 s.listen(1)
 conn, addr = s.accept()
 #s.setblocking(0)
 logger("Verbindung zu "+addr[0]+":"+str(addr[1]), logging)
 while(not stop_event.is_set()):
   try:
     #data = conn.recv(BUFFER_SIZE)
     #ready_to_read, ready_to_write, in_error = select.select([s],[],[])
     #print(ready_to_read)
     logger("TCP auf Empfang", logging)
     #if ready_to_read[0]:
     data = conn.recv(1024)
     logger("Horch was kommt von TCP rein: "+data, logging)
     #if not data: break
     #print("received data:", data)
     valid = remote(data)
     #print("Versuche zu senden")
     if valid == "ja":
       conn.send("Des hob i kriegt: "+ data + "; bassd scho.")  # echo
     elif valid == "zustand":
       tmp = hyperion_color - 1
       if tmp < 0: tmp = len(hyperion_color_list) - 1
       antwort = "Source="+ source + ";Volume="+str(volume)+";Farbe="+str(hyperion_color_list[tmp])+";Mute="+str(mute)
       logger("TCP-Antwort: " + antwort, logging)
       conn.send(antwort)  # echo
     else:
       conn.send("Des hob i kriegt: "+ data + "; is net ganga!")  # echo
     #stop_event.wait(0.2)
   except socket.error as v:
     logger("Auswurf: " + str(v), logging)
     conn.close()
     stop_event.wait(0.2)
     conn, addr = s.accept()
     logger("Verbindung zu "+addr[0]+":"+str(addr[1]), logging)
 logger("Closing TCP Connection", logging)
 conn.close()
 logger("Closing TCP Socket", logging)
 s.close()
 return



