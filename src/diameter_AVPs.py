#!/usr/bin/env python
##################################################################
# Copyright (c)     
##################################################################

import sys
import time
import SGMB
import threading
#sys.path.append("..")
# Remove them normally

# Testing handling basic AVP types
from libDiameter import *
#from loadConfig import gw_host
mylock = threading.RLock()
ports = []                   # port list
d_ports = {}                 # port dictionary
#gw_host = "vm1sim1"
#gw_realm = "ericsson.com"
#sgimb_address = "192.168.1.77"
#mdfcp_ip = "192.168.2.79"

def init_ports():
    for port in range(51000, 51601):
        ports.append(port)

def AssignUDPPort(sessionId):
    # if the port has not assigned, then assign a port from ports list.
    if d_ports.has_key(sessionId) is False:
        if len(ports) > 0 :
            port = ports.pop(0)
        else:
            print "No port to assign! Use the temporary port."
            port = 40000
        d_ports[sessionId] = port
    else:
        # if the session is exist, then reuse the assigned port. this scenario is used for multiple CP
        print "session", sessionId, " is exist."
        port = d_ports.get(sessionId)
    #print "session:", sessionId, port   
    #return hex(port)
    return port

# When session finish, release udp port
def ReleasePort(sessionId):
    # if a port is used by a seesion.
    flag = d_ports.has_key(sessionId)
    if flag is False:
        print "No port assign to session", sessionId            
    else:
        # delete session from port dictionary, and port list recycle the port
        port = d_ports.pop(sessionId)
        ports.append(port)
        
        print "session:", sessionId, "has been removed.", port, "is released."
    
def do_conn(t_mdfcp, retry=2):
    try:
        host = t_mdfcp
        port = 3868
        # Connect to server
        Conn = Connect(host, port)        
    except socket.error, cer:        
        Conn = None
        if retry > 0:
            retry = retry - 1
            Conn = do_conn(host, retry)
            # continue
            # break

    if Conn is None:
        print 'could not open socket'
        sys.exit(1)

    return Conn

def message_recv(t_host, t_realm, t_address, t_mdfcp, Conn):
    # receive message
    data = Conn.recv(4096)

    if not data:
        Conn.close
        message_handle(t_host, t_realm, t_address, t_mdfcp)

    msg = data.encode("hex")

    return msg

def message_send(Conn, msg, retry=2):
    # send message
    try:
        Conn.send(msg)

    except socket.error, cer:
        if retry > 0:
            message_send(Conn, msg)
        Conn.close
        message_handle()


def message_handle(t_host, t_realm, t_address, t_mdfcp):

    # connect with mdfcp
    Conn = do_conn(t_mdfcp)
    # send cer
    cer = CreateCER(t_host, t_realm, t_address) 
    
    mylock.acquire()
    Conn.send(cer.decode("hex"))
    H, avps = DecodeMSG(cer)
    print time.strftime('%Y-%m-%d %Z %X', time.localtime(time.time())), ":", 'Send CER to ', t_mdfcp
    mylock.release()
        
    while True:
        # receive message
        mylock.acquire()
        msg = message_recv(t_host, t_realm, t_address, t_mdfcp, Conn)
        H, avps = DecodeMSG(msg)
        
        result_Code = findAVP("Result-Code", avps)
        flag = (H.cmd == 257) & (H.flags == 0x40) & (result_Code == 2001)
        
        if flag is True:
            print time.strftime('%Y-%m-%d %Z %X', time.localtime(time.time())), ":", 'CEA received from ', t_mdfcp
            # Exit loop after receive CEA.
            break
        else:
            print "CMD=", H.cmd, "Flags=", H.flags, "Result-Code=", result_Code  
            
        mylock.release()    
    
    while True:
        mylock.acquire()
        
        # receive message
        msg = message_recv(t_host, t_realm, t_address, t_mdfcp, Conn)
        H, avps = DecodeMSG(msg)
        
        if H.cmd == 280:
            HandleDWAR(Conn, H, avps, t_host, t_realm)
        elif H.cmd == 258:
            HandleRAA(Conn, H, avps, t_host, t_realm, t_address)
        
        mylock.release()  

def CreateCER(gw_host,gw_realm,sgimb_address):
    AVP=[]
    
    AVP.append(encodeAVP("Origin-Host", gw_host))    
    AVP.append(encodeAVP("Origin-Realm",gw_realm))    
    AVP.append(encodeAVP("Host-IP-Address", sgimb_address))    
    AVP.append(encodeAVP("Vendor-Id",10415))
    AVP.append(encodeAVP("Product-Name","Ericsson BMSC"))
    AVP.append(encodeAVP("Auth-Application-Id",16777292))

    # Create message header (empty)
    CER = HDRItem()
    
    CER.flags = 0xC0
    CER.appId = 16777292    
    # Set command code
    CER.cmd = dictCOMMANDname2code("Capabilities-Exchange")
    # Set Hop-by-Hop and End-to-End
    initializeHops(CER)
    # Add AVPs to header and calculate remaining fields
    cer=createReq(CER,AVP)
    # cer now contains CER Request as hex string
    return cer

# Create DWR message
def CreateDWR(H, gw_host, gw_realm):
    AVP=[]    
    AVP.append(encodeAVP("Origin-Host", gw_host))    
    AVP.append(encodeAVP("Origin-Realm",gw_realm))    
    AVP.append(encodeAVP("Origin-State-Id",1414808398)) 
    
    DWR=HDRItem()
    
    DWR.flags = 0xC0  
    DWR.cmd = H.cmd
    DWR.HopByHop = H.HopByHop
    DWR.EndToEnd = H.EndToEnd
    
    # Add AVPs to header and calculate remaining fields
    dwr=createReq(DWR,AVP)
    # cer now contains DWR Request as hex string
    return dwr

# Create DWA message
def CreateDWA(H, gw_host, gw_realm):
    AVP=[]
    AVP.append(encodeAVP("Result-Code", 2001))  
    AVP.append(encodeAVP("Origin-Host", gw_host))    
    AVP.append(encodeAVP("Origin-Realm",gw_realm))
    
    DWA=HDRItem()
    
    DWA.cmd = H.cmd
    DWA.HopByHop = H.HopByHop
    DWA.EndToEnd = H.EndToEnd
    # Add AVPs to header and calculate remaining fields
    dwa=createReq(DWA,AVP)
    # cer now contains DWR Request as hex string
    return dwa

# Create RAA Start message
def CreateRAA_Start(H, sessionId, gw_udp_port, gw_host, gw_realm, sgimb_address):
    AVP=[]
    AVP.append(encodeAVP("Result-Code",2001))  
    AVP.append(encodeAVP("Origin-Host",gw_host))    
    AVP.append(encodeAVP("Origin-Realm",gw_realm))
    AVP.append(encodeAVP("Session-Id",sessionId))
    AVP.append(encodeAVP("MBMS-StartStop-Indication", 0))
    
    if sgimb_address.find('.')!=ERROR:
        AVP.append(encodeAVP("MBMS-GGSN-Address",sgimb_address))
    elif sgimb_address.find(':')!=ERROR:
        AVP.append(encodeAVP("MBMS-GGSN-IPv6-Address",sgimb_address))

    AVP.append(encodeAVP("MBMS-User-Data-Mode-Indication", 0))
    AVP.append(encodeAVP("MBMS-GW-UDP-Port",gw_udp_port))
    
    RAA=HDRItem()
    
    RAA.appId = 16777292 
    # Set command code
    RAA.cmd = H.cmd
    # Set Hop-by-Hop and End-to-End
    RAA.HopByHop = H.HopByHop
    RAA.EndToEnd = H.EndToEnd
    # Add AVPs to header and calculate remaining fields
    raa_start=createReq(RAA,AVP)
    
    return raa_start

# Create RAA Stop message
def CreateRAA_Stop(H, sessionId, gw_host, gw_realm):
    AVP=[]    
    AVP.append(encodeAVP("Result-Code",2001))
    AVP.append(encodeAVP("Origin-Host",gw_host))    
    AVP.append(encodeAVP("Origin-Realm",gw_realm))
    AVP.append(encodeAVP("Session-Id",sessionId))    
    AVP.append(encodeAVP("MBMS-StartStop-Indication", 1))
        
    RAA=HDRItem()
    
    RAA.appId = 16777292 
    # Set command code
    RAA.cmd = H.cmd
    # Set Hop-by-Hop and End-to-End
    RAA.HopByHop = H.HopByHop
    RAA.EndToEnd = H.EndToEnd
    # Add AVPs to header and calculate remaining fields
    raa_stop=createReq(RAA,AVP)
    
    return raa_stop

# Decode diameter messages
def DecodeMSG(msg):
    H = HDRItem()
    stripHdr(H, msg)
    avps = splitMsgAVPs(H.msg)
    cmd = dictCOMMANDcode2name(H.flags, H.cmd)
    print "-" * 100
    if cmd == ERROR:
        print 'Unknown command', H.cmd
#    else:
#        print "cmdCode=", H.cmd, "Flags=", hex(H.flags), "Hop-by-Hop=", H.HopByHop, "End-to-End=", H.EndToEnd, "ApplicationId=", H.appId
#    
#    for avp in avps:
#        print "RAW AVP", avp
#        print "Decoded AVP", decodeAVP(avp)       
    
    return H, avps             

# Handle DWA & DWR messages
def HandleDWAR(Conn, H, avps, gw_host, gw_realm):
    
    if H.flags == 0x80 :
        print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "DWR Received."    
        
        dwa=CreateDWA(H, gw_host, gw_realm)
        dwr=CreateDWR(H, gw_host, gw_realm)
        
        Conn.send(dwa.decode("hex"))
        print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "DWA Send." 
        Conn.send(dwr.decode("hex"))
        print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "DWR Send." 
        
        H, avps = DecodeMSG(dwr)
        H, avps = DecodeMSG(dwa)
        
    elif (H.flags == 0x40) and (findAVP("Result-Code",avps) == 2001):
        print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "DWA Received."
    
# Handle RAA start & stop messages
def HandleRAA(Conn, H, avps, gw_host, gw_realm, sgimb_address):
    
    if H.flags == 0xc0 :
        
        sessionId = findAVP("Session-Id",avps)  
        start_stop_indication = findAVP("MBMS-StartStop-Indication",avps)      
        
        #print "sessionid=", sessionId, "indication=", start_stop_indication
        
        if start_stop_indication == 0:
            print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "RAR Start Received.", "session = ", sessionId
            # Assign a UDP port for session
            mylock.acquire()
            gw_udp_port = AssignUDPPort(sessionId)            
            mylock.release()
            
            raa=CreateRAA_Start(H, sessionId, gw_udp_port, gw_host, gw_realm, sgimb_address)
            H, avps = DecodeMSG(raa)
            Conn.send(raa.decode("hex"))
            print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "RAA START Send." , "session = ", sessionId, "UDPPort = ", gw_udp_port
        elif start_stop_indication == 1:
            print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "RAR Stop Received.", "session = ", sessionId
            raa=CreateRAA_Stop(H, sessionId, gw_host, gw_realm)
            H, avps = DecodeMSG(raa)
            Conn.send(raa.decode("hex"))
            print time.strftime('%Y-%m-%d %Z %X',time.localtime(time.time())),":", gw_host, "RAA Stop Send.", "session = ", sessionId
            mylock.acquire()
            ReleasePort(sessionId)
            mylock.release()
    
#if __name__ == "__main__":
#    #logging.basicConfig(level=logging.DEBUG)
#    #logging.basicConfig(level=logging.INFO)
#    LoadDictionary("../dictDiameter.xml")
