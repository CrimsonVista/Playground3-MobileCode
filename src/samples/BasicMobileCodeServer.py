'''
Created on Dec 5, 2017

@author: seth_
'''
import sys
sys.path.append("..")
from MobileCodeService import MobileCodeClient, MobileCodeServerTracker
from MobileCodeService import MobileCodeServer, DiscoveryResponder
from MobileCodeService.Auth import NullServerAuth, SimplePayingServerAuth
from MobileCodeService.Engine import DefaultMobileCodeEngine
from MobileCodeService.Wallet import NullServerWallet, PayingServerWallet
from CipherUtil import loadCertFromFile
import playground, os
from asyncio.events import get_event_loop

if __name__=="__main__":
    from playground.common.logging import EnablePresetLogging, PRESET_DEBUG
    EnablePresetLogging(PRESET_DEBUG)
    
    serverArgs = {}
    args= sys.argv[1:]
    i = 0
    for arg in args:
        if arg.startswith("-"):
                k,v = arg.split("=")
                serverArgs[k]=v
        else:
                serverArgs[i] = arg
                i+=1
                
    bankcertPath = serverArgs[0]
    paytoAccount = serverArgs[1]
    
    stack = serverArgs.get("-stack","default")
    port = int(serverArgs.get("-port","1"))
    
    bankcert = loadCertFromFile(bankcertPath)
    
    #serverWallet = NullServerWallet()
    #serverAuth = NullServerAuth()
    serverWallet = PayingServerWallet(bankcert, paytoAccount)
    serverEngine = DefaultMobileCodeEngine()
    serverAuth = SimplePayingServerAuth(paytoAccount, 5) # hardcoded 5 bitpoints per job
    serverAuth.traits[serverAuth.CONNECTOR_ATTRIBUTE]=stack
    serverFactory = lambda: MobileCodeServer(serverWallet, serverAuth, serverEngine)

    coro = playground.getConnector(stack).create_playground_server(serverFactory, port)
    loop = get_event_loop()
    server = loop.run_until_complete(coro)
    print("Mobile Code Server started", server)
    serverAddress, serverPort = server.sockets[0].gethostname()
    responder = DiscoveryResponder(serverAddress, serverPort, serverAuth)
    loop.call_soon(responder.start)
    print("Start loop")
    loop.run_forever()
