'''
Created on Nov 30, 2017

@author: seth_
'''
import sys
sys.path.append("..")
from MobileCodeService import MobileCodeClient
from MobileCodeService import MobileCodeServer
from MobileCodeService.Auth import NullClientAuth, NullServerAuth, SimplePayingClientAuth,SimplePayingServerAuth
from MobileCodeService.Engine import DefaultMobileCodeEngine
from MobileCodeService.Wallet import NullClientWallet, NullServerWallet, PayingClientWallet, PayingServerWallet
import playground, os, subprocess, time, sys, getpass
from asyncio.events import get_event_loop


# TODO: Fix this once the bank is installed
sys.path.insert(0, '../../../BitPoints-Bank-Playground3-/')
from CipherUtil import loadCertFromFile
from OnlineBank import BankClientProtocol
    
def RunCodeAndPrintResult(client):
    future = client.run()
    future.add_done_callback(lambda f: print(f.result()))

def debugPrint(*s):
    print("\033[93m[%s]" % round(time.time() % 1e4, 4), *s, "\033[0m")

def main():
    from playground.common.logging import EnablePresetLogging, PRESET_DEBUG
    EnablePresetLogging(PRESET_DEBUG)

    args = sys.argv[1:]
    if len(args) != 4:
        print("Incorrect number of arguments (got %s, expected 4)" % len(args))
        print("USAGE:\n\tpython3 bank_functional1.py [Bank Cert Path] [User Login Name]\n\t\t[Client/Requester Bank Account Name] [Server/Merchant Bank Account Name]")
        return

    bankcert = loadCertFromFile(args[0])
    username = args[1]
    pw = getpass.getpass("Enter client/requester's bank password: ")
    payeraccount, merchantaccount = args[2:4]

    bankstackfactory = lambda: BankClientProtocol(bankcert, username, pw)
    
    samplecode = "print('this is a test')"
    fee = 1
    #debugPrint("Creating NullServerWallet")
    #serverWallet = NullServerWallet()
    debugPrint("Creating PayingServerWallet")
    serverWallet = PayingServerWallet(bankcert, merchantaccount)
    debugPrint("Creating SimplePayingServerAuth")
    serverAuth = SimplePayingServerAuth(merchantaccount, fee)
    debugPrint("Creating DefaultMobileCodeEngine")
    serverEngine = DefaultMobileCodeEngine()

    # debugPrint("Creating NullClientWallet")
    # clientWallet = NullClientWallet()
    debugPrint("Creating PayingClientWallet")
    clientWallet = PayingClientWallet("default", bankstackfactory, username, pw, payeraccount, "localhost")

    def serverFactory():
        debugPrint("Factory creating MobileCodeServer")
        return MobileCodeServer(serverWallet, serverAuth, serverEngine)

    debugPrint("Creating MobileCodeClient")
    client = MobileCodeClient("default", "localhost", 1, samplecode, SimplePayingClientAuth(), clientWallet)
    coro = playground.getConnector().create_playground_server(serverFactory, 1)
    loop = get_event_loop()
    server = loop.run_until_complete(coro)
    print("Server started")
    loop.call_later(0, RunCodeAndPrintResult, client)
    loop.run_forever()

if __name__=="__main__":
    main()
