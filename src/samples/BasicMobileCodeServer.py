'''
Created on Dec 5, 2017

@author: seth_
'''
import sys
sys.path.append("..")
from MobileCodeService import MobileCodeClient, MobileCodeServerTracker
from MobileCodeService import MobileCodeServer, DiscoveryResponder
from MobileCodeService.Auth import NullClientAuth, NullServerAuth
from MobileCodeService.Engine import DefaultMobileCodeEngine
from MobileCodeService.Wallet import NullClientWallet, NullServerWallet
import playground, os, subprocess, time, sys
from asyncio.events import get_event_loop

if __name__=="__main__":
    from playground.common.logging import EnablePresetLogging, PRESET_DEBUG
    EnablePresetLogging(PRESET_DEBUG)
    
    serverWallet = NullServerWallet()
    serverAuth = NullServerAuth()
    serverEngine = DefaultMobileCodeEngine()
    serverFactory = lambda: MobileCodeServer(serverWallet, serverAuth, serverEngine)

    coro = playground.getConnector().create_playground_server(serverFactory, 1)
    loop = get_event_loop()
    server = loop.run_until_complete(coro)
    print("Mobile Code Server started", server)
    serverAddress, serverPort = server.sockets[0].gethostname()
    responder = DiscoveryResponder(serverAddress, serverPort, serverAuth)
    loop.call_soon(responder.start)
    print("Start loop")
    loop.run_forever()