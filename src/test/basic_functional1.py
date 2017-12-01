'''
Created on Nov 30, 2017

@author: seth_
'''
import sys
sys.path.append("..")
from MobileCodeService import MobileCodeClient
from MobileCodeService import MobileCodeServer
from MobileCodeService.Auth import NullClientAuth, NullServerAuth
from MobileCodeService.Engine import DefaultMobileCodeEngine
from MobileCodeService.Wallet import NullClientWallet, NullServerWallet
import playground, os, subprocess, time, sys
from asyncio.events import get_event_loop
    
def RunCodeAndPrintResult(client):
    future = client.run()
    future.add_done_callback(lambda f: print(f.result()))

if __name__=="__main__":
    from playground.common.logging import EnablePresetLogging, PRESET_DEBUG
    EnablePresetLogging(PRESET_DEBUG)
    
    samplecode = "print('this is a test')"
    serverWallet = NullServerWallet()
    serverAuth = NullServerAuth()
    serverEngine = DefaultMobileCodeEngine()
    serverFactory = lambda: MobileCodeServer(serverWallet, serverAuth, serverEngine)
    client = MobileCodeClient("default", "localhost", 1, samplecode, NullClientAuth(), NullClientWallet())
    coro = playground.getConnector().create_playground_server(serverFactory, 1)
    loop = get_event_loop()
    server = loop.run_until_complete(coro)
    print("Server started")
    loop.call_later(0, RunCodeAndPrintResult, client)
    loop.run_forever()