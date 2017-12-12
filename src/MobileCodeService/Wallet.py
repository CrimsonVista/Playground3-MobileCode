'''
Created on Dec 1, 2017

@author: seth_
'''
import sys

import time, asyncio, pickle, traceback

# TODO: Fix this once the bank is installed
sys.path.insert(0, '../../../BitPoints-Bank-Playground3-/')
from OnlineBank import BANK_FIXED_PLAYGROUND_ADDR, BANK_FIXED_PLAYGROUND_PORT
from CipherUtil import RSA_SIGNATURE_MAC
from BankCore import LedgerLine
from asyncio import Future

import playground

from BankMessages import Receipt

from functools import partial

#####
##  Wallet Interfaces
#####
class IMobileCodeServerWallet:
    def clearState(self, cookie): raise NotImplementedError()
    def getId(self): raise NotImplementedError() 
    def processPayment(self, cookie, charges, paymentData): raise NotImplementedError()

    
class IMobileCodeClientWallet:
    def getPayment(self, cookie, payToAccount, charges): raise NotImplementedError()

#####
##  Null Wallets
#####
class NullServerWallet(IMobileCodeServerWallet):
    def clearState(self, cookie):
        pass
    
    def getId(self):
        return "Null Wallet 1.0"  
    
    def processPayment(self, cookie, charges, paymentData):
        debugPrint("NullServerWallet called processPayment with: charges =", charges, "cookie=", cookie, "paymentData(size)=", len(paymentData))
        if charges == 0:
            return True, ""
        return False, "Null Wallet doesn't accept payments"  


class NullClientWallet(IMobileCodeClientWallet):
    def getPayment(self, cookie, payToAccount, charges):
        debugPrint("NullClientWallet called getPayment")
        return None, "Null wallet does not make payment"

#####
##  Paying Wallets
#####
class PayingServerWallet(IMobileCodeServerWallet):
    def __init__(self, bankcert, merchantaccount):
        self.__receivingAccount = merchantaccount
        self.__verifier = RSA_SIGNATURE_MAC(bankcert.public_key())

    def clearState(self, cookie):
        pass
    
    def getId(self):
        return "Paying Wallet 1.0"  
    
    def processPayment(self, cookie, charges, paymentData):
        debugPrint("PayingServerWallet called processPayment with: charges =", charges, "cookie=", cookie, "paymentData(size)=", len(paymentData))
        if charges == 0:
            return True, ""

        receiptpkt = Receipt.Deserialize(paymentData)
        # Check the validity of the signature
        check, reason = self.__receipt(receiptpkt)
        if check:
            receiptData = eval(receiptpkt.Receipt)
            # Since the receipt bytes have been signed by the bank that we trust, we assume it's safe to unpickle it
            ledgerline = pickle.loads(receiptData)

            # # Check the receipt's validity (correct amount and account and memo/cookie)
            # debugPrint("LedgerLine complete:", ledgerline.complete())
            # debugPrint("LedgerLine amount:", ledgerline.getTransactionAmount(self.__receivingAccount))
            # debugPrint("LedgerLine memo:", ledgerline.memo())
            valid = True
            valid &= ledgerline.complete()
            valid &= ledgerline.getTransactionAmount(self.__receivingAccount) == charges
            valid &= ledgerline.memo(self.__receivingAccount) == str(cookie)

            if valid:
                debugPrint("PayingServerWallet has validated the receipt!")
                return True, ""

        return False, "PayingServerWallet processPayment received receipt failed checks"  


    def __receipt(self, msgObj):
        try:
            receiptFile = "bank_receipt."+str(time.time())
            sigFile = receiptFile + ".signature"
            debugPrint("Paying Server Wallet: Receipt and signature received. Saving as %s and %s" % (receiptFile, sigFile))
            receiptBytes = eval(msgObj.Receipt)
            sigBytes = eval(msgObj.ReceiptSignature)
            with open(receiptFile, "wb") as f:
                f.write(receiptBytes)
            with open(sigFile, "wb") as f:
                f.write(sigBytes)
            if not self.__verifier.verify(receiptBytes, sigBytes):
                responseTxt = "Received a receipt with mismatching signature.\n"
                responseTxt += "\tPlease report this to the bank administrator.\n"
                debugPrint("Paying Server Wallet: ",responseTxt)
                return False, "Received a receipt with mismatching signature."
            else:
                debugPrint("Paying Server Wallet: Signature validated against the receipt.")
                return True, ""
        except Exception as e:
            print(traceback.format_exc())


class PayingClientWallet(IMobileCodeClientWallet):
    def __init__(self, connector, bankfactory, username, pw, myaccount, bankaddr=BANK_FIXED_PLAYGROUND_ADDR, bankport=BANK_FIXED_PLAYGROUND_PORT):
        self.__loginName = username
        self.__pw = pw
        self.__bankAddr = bankaddr
        self.__bankPort = bankport
        self.__srcPaymentAccount = myaccount
        self.__bankFactory = bankfactory
        self.__connector = connector
        self.__connectionFutures = {}

        self.__d = None
        
        self.__asyncLoop = asyncio.get_event_loop()

        self.__bankClients = dict()
        self.__connected = dict()

    def __connect(self, cookie):
        # Immediately connect to the bank (Should we wait for something instead?)
        debugPrint("In __connect")
        coro = playground.getConnector(self.__connector).create_playground_connection(self.__bankFactory, self.__bankAddr, self.__bankPort)
        fut = asyncio.run_coroutine_threadsafe(coro, self.__asyncLoop)
        fut.add_done_callback(partial(self.__handleClientConnection, cookie=cookie))
        debugPrint("PayingClientWallet initialized!")

    def __handleClientConnection(self, fut, cookie):
        debugPrint("PayingClientWallet __handleClientConnection")
        debugPrint("Future done?", fut.done())
        try:
            debugPrint("Future exception:", fut.exception() is not None)
            debugPrint("PayingClientWallet __handleClientConnection Future exception:", fut.exception())
            debugPrint("PayingClientWallet __handleClientConnection Future result:", fut.result())
            transport, protocol = fut.result()
        except Exception as e:
            debugPrint("PayingClientWallet exception:", e)
            debugPrint(traceback.format_exc())
        debugPrint("Bank connected. Running startup routines with protocol %s" % protocol)

        print("Client Connected. Starting UI t:{}. p:{}".format(transport, protocol))

        try:
            self.__bankClients[cookie] = protocol
            # self.__bankClient.setLocalErrorHandler(self)
            self.__d = self.__bankClients[cookie].waitForConnection() # self.__bankClient.loginToServer()
            self.__bankClients[cookie].waitForTermination().addCallback(lambda *args: self.quit())
            self.__d.addCallback(partial(self.__loginToServer,cookie=cookie))
            self.__d.addErrback(partial(self.__noLogin, cookie=cookie))
            debugPrint("Paying Client Wallet: Logging in to bank. Waiting for server\n")
        except:
            print(traceback.format_exc())

    def __loginToServer(self, success, cookie):
        if not success:
            return self.__noLogin(Exception("Failed to login"), cookie=cookie)
        self.__d = self.__bankClients[cookie].loginToServer()
        self.__d.addCallback(partial(self.__login, cookie=cookie))
        self.__d.addErrback(partial(self.__noLogin, cookie=cookie))
        return self.__d

    def __noLogin(self, e, cookie):
        debugPrint("Paying Wallet Client: Failed to login to bank with bankClient %s. Error:\n%s\n" % (self.__bankClients[cookie], str(e)))

    def __login(self, success, cookie):
        debugPrint("Paying Wallet Client: Logged in to bank. Switching to account: %s\n" % self.__srcPaymentAccount)
        self.__d = self.__bankClients[cookie].switchAccount(self.__srcPaymentAccount)
        self.__d.addCallback(partial(self.__switchAccount, cookie=cookie))
        self.__d.addErrback(partial(self.__failed, cookie=cookie))

    def __switchAccount(self, msgObj, cookie):
        debugPrint("PayingClientWallet: Successfully logged into account.")
        self.__connected[cookie] = True
        self.__connectionFutures[cookie].set_result(True)


    def __failed(self, e, cookie):
        debugPrint("PayingClientWallet \033[91m  Switching account failed on bankClient %s. Reason:\n%s\033[0m" % (self.__bankClients[cookie], str(e)))
        self.__bankClients[cookie].close()
        return Exception(e)

    async def getPayment(self, cookie, payToAccount, charges):
        debugPrint("PayingClientWallet called get payment with cookie=", cookie, "charges=", charges)

        self.__connectionFutures[cookie] = Future()
        debugPrint("Call connect")
        self.__connect(cookie)

        await self.__connectionFutures[cookie]
        # This check is now redundant
        if self.__connected[cookie]:

            result = await self.__getTransferProof(cookie, payToAccount, charges)
            if cookie in self.__bankClients:
                self.__bankClients[cookie].close()
                del self.__bankClients[cookie]
            if result:
                debugPrint("PayingClientWallet transfer receipt size:", len(result))
                return result, "Received receipt from Bank"
            else:
                debugPrint("PayingClientWallet did not get result")
                return None, "Error on trying to transfer money"
        else:
            debugPrint("PayingClientWallet is not connected to the bank?")
            return None, "Paying client wallet is not connected to the bank"
    
    async def __getTransferProof(self, cookie, payToAccount, charges):
        debugPrint("PayingClientWallet sending transfer to bank")
        fut = self.__bankClients[cookie].transfer(payToAccount, charges, str(cookie)).f
        try:
            debugPrint("PayingClientWallet waiting on bank transfer receipt")
            result = await fut
        except Exception as e:
            debugPrint("PayingClientWallet transfer got exception:\n", e)
            return None

        debugPrint("PayingClientWallet transfer receipt received. Checking it...", result)
        check, receipt = self.__receipt(result, cookie)
        if check:
            # Remove potentially private data from the packet
            receipt.ClientNonce = 0
            receipt.ServerNonce = 0
            receipt.RequestId = 0
            return receipt.__serialize__()
        else:
            return None

    def __receipt(self, msgObj, cookie):
        try:
            receiptFile = "bank_receipt."+str(time.time())
            sigFile = receiptFile + ".signature"
            debugPrint("Paying Client Wallet: Receipt and signature received. Saving as %s and %s" % (receiptFile, sigFile))
            receiptBytes = eval(msgObj.Receipt)
            sigBytes = eval(msgObj.ReceiptSignature)
            with open(receiptFile, "wb") as f:
                f.write(receiptBytes)
            with open(sigFile, "wb") as f:
                f.write(sigBytes)
            if not self.__bankClients[cookie].verify(receiptBytes, sigBytes):
                responseTxt = "Received a receipt with mismatching signature.\n"
                responseTxt += "\tPlease report this to the bank administrator.\n"
                debugPrint("Paying Client Wallet: ",responseTxt)
                return False, "Received a receipt with mismatching signature."
            else:
                debugPrint("Paying Client Wallet: Valid receipt received.")
                return True, msgObj
        except Exception as e:
            print(traceback.format_exc())

DEBUG = True
def debugPrint(*s):
    if DEBUG:
        print("\033[96m[%s]" % round(time.time() % 1e4, 4), *s, "\033[0m")
