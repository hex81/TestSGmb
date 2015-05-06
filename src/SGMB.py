'''
Created on Jun 30, 2014

@author: exihexi
'''
import xml.dom.minidom as minidom
import thread
import sys
import time
from libDiameter import *
from diameter_AVPs import *
import threading
import signal

mylock = threading.RLock()

def loadConfig(file):    
    
    global mdfcp_list
    global gw_host
    global gw_realm
    global sgimb_address
    mdfcp_list = []
    
    doc = minidom.parse(file)
    #node = doc.documentElement
    hosts = doc.getElementsByTagName("host")[0]
    realms = doc.getElementsByTagName("realm")[0]
    sgimbs = doc.getElementsByTagName("sgimb")[0]
    mdfcp = doc.getElementsByTagName("mdfcp_address")
    
    gw_host = (hosts.childNodes[0].data).encode('utf8')
    gw_realm = (realms.childNodes[0].data).encode('utf8')    
    sgimb_address = (sgimbs.childNodes[0].data).encode('utf8')
    
    for item in mdfcp:        
        if len(item.childNodes) != 0:
            mdfcp_list.append((item.childNodes[0].data).encode('utf8'))
        
    print "sgmb host is: ", gw_host
    print "sgmb_realm is:", gw_realm
    print "sgimb_address is: ", sgimb_address
    #print mdfcp_list

def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)


class diameterHandle(threading.Thread):
    
    def __init__(self, gw_host,gw_realm,sgimb_address,mdfcp):
        threading.Thread.__init__(self)
        self.t_host = gw_host
        self.t_realm = gw_realm
        self.t_address = sgimb_address
        self.t_mdfcp = mdfcp 
        #self.t_sid = sessionId        

    def run(self):
        
        message_handle(self.t_host, self.t_realm, self.t_address,self.t_mdfcp)

'''            
class test(threading.Thread):
    def __init__(self, gw_host,gw_realm,sgimb_address,mdfcp,sessionId):
        threading.Thread.__init__(self)
        self.t_host = gw_host
        self.t_realm = gw_realm
        self.t_address = sgimb_address
        self.t_mdfcp = mdfcp
        self.t_sid = sessionId
        
    def run(self):
        cer=CreateCER(self.t_host, self.t_realm, self.t_address) 
        H, avps = DecodeMSG(cer)
        
        dwa=CreateDWA(H, self.t_host, self.t_realm)
        H, avps = DecodeMSG(dwa)
        dwr=CreateDWR(H, self.t_host, self.t_realm)
        H, avps = DecodeMSG(dwr)
    
        mylock.acquire()
        gw_udp_port = AssignUDPPort(self.t_sid)
        mylock.release()
        raa=CreateRAA_Start(H, self.t_sid, gw_udp_port, self.t_host, self.t_realm, self.t_address)
        H, avps = DecodeMSG(raa)
    
        raa=CreateRAA_Stop(H, self.t_sid, self.t_host, self.t_realm)
        H, avps = DecodeMSG(raa)
        
        mylock.acquire()
        ReleasePort(self.t_sid)
        mylock.release() 
'''
if __name__ == "__main__":
    
    signal.signal(signal.SIGINT, signal_handler)
    #print('Press Ctrl+C')
    #signal.pause()		

    loadConfig("../sgmb.xml")
    LoadDictionary("../dictDiameter.xml")
    init_ports()
  
    #session = 10
    for mdfcp in mdfcp_list:                
        #thread = test(gw_host,gw_realm,sgimb_address,mdfcp,str(session))       
        thread = diameterHandle(gw_host,gw_realm,sgimb_address,mdfcp)
        thread.start()
        #session += 1
    time.sleep(10)