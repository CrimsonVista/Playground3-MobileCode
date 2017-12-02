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

import playground

from BankMessages import Receipt

#####
##  Wallet Interfaces
#####
class IMobileCodeServerWallet:
    def clearState(self, cookie): raise NotImplementedError()
    def getId(self): raise NotImplementedError() 
    def processPayment(self, cookie, charges, paymentData): raise NotImplementedError()

    
class IMobileCodeClientWallet:
    def preparePayment(self, cookie, charges): raise NotImplementedError()
    def getPayment(self, cookie, charges): raise NotImplementedError()

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
    def preparePayment(self, cookie, charges):
        # Null wallet does not make payment
        debugPrint("NullClientWallet called preparePayment")
        return

    def getPayment(self, cookie, charges):
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
    def __init__(self, bankstackfactory, username, pw, myaccount, merchantaccount, bankaddr=BANK_FIXED_PLAYGROUND_ADDR, bankport=BANK_FIXED_PLAYGROUND_PORT):
        self._loginName = username
        self._pw = pw
        self.__bankAddr = bankaddr
        self.__bankPort = bankport
        self.__srcPaymentAccount = myaccount
        self.__destPaymentAccount = merchantaccount

        self.__d = None
        
        self.__asyncLoop = asyncio.get_event_loop()

        # Immediately connect to the bank (Should we wait for something instead?)
        coro = playground.getConnector().create_playground_connection(bankstackfactory, self.__bankAddr, self.__bankPort)
        fut = asyncio.run_coroutine_threadsafe(coro, self.__asyncLoop)
        fut.add_done_callback(self.__handleClientConnection)
        debugPrint("PayingClientWallet initialized!")

    def __handleClientConnection(self, fut):
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
        self.__bankConnected(protocol)
        print("Client Connected. Starting UI t:{}. p:{}".format(transport, protocol))

    def __bankConnected(self, result):
        try:
            self.__bankClient = result
            # self.__bankClient.setLocalErrorHandler(self)
            self.__d = self.__bankClient.waitForConnection() # self.__bankClient.loginToServer()
            self.__bankClient.waitForTermination().addCallback(lambda *args: self.quit())
            self.__d.addCallback(self.__loginToServer)
            self.__d.addErrback(self.__noLogin)
            debugPrint("Paying Client Wallet: Logging in to bank. Waiting for server\n")
            return self.__d
        except:
            print(traceback.format_exc())

    def __loginToServer(self, success):
        if not success:
            return self.__noLogin(Exception("Failed to login"))
        self.__d = self.__bankClient.loginToServer()
        self.__d.addCallback(self.__login)
        self.__d.addErrback(self.__noLogin)
        return self.__d

    def __noLogin(self, e):
        debugPrint("Paying Wallet Client: Failed to login to bank: %s\n" % str(e))

    def __login(self, success):
        debugPrint("Paying Wallet Client: Logged in to bank. Switching to account: %s\n" % self.__srcPaymentAccount)
        self.__d = self.__bankClient.switchAccount(self.__srcPaymentAccount)
        self.__d.addCallback(self.__switchAccount)
        self.__d.addErrback(self.__failed)

    def __switchAccount(self, msgObj):
        debugPrint("PayingClientWallet: Successfully logged into account.")
        self.__connected = True

    def __failed(self, e):
        debugPrint("PayingClientWallet \033[91m  Switching account failed. Reason: %s\033[0m" % str(e))
        return Exception(e)

    async def getPayment(self, cookie, charges):
        debugPrint("PayingClientWallet called get payment with cookie=", cookie, "charges=", charges)
        if self.__connected:

            result = await self.__getTransferProof(cookie, charges)
            if result:
                debugPrint("PayingClientWallet transfer receipt size:", len(result))
                return result, "Received receipt from Bank"
            else:
                debugPrint("PayingClientWallet did not get result")
                return None, "Error on trying to transfer money"
        else:
            debugPrint("PayingClientWallet is not connected to the bank?")
            return None, "Paying client wallet is not connected to the bank"
    
    async def __getTransferProof(self, cookie, charges):
        debugPrint("PayingClientWallet sending transfer to bank")
        fut = self.__bankClient.transfer(self.__destPaymentAccount, charges, str(cookie)).f
        try:
            debugPrint("PayingClientWallet waiting on bank transfer receipt")
            result = await fut
        except Exception as e:
            debugPrint("PayingClientWallet transfer got exception:\n", e)
            return None

        debugPrint("PayingClientWallet transfer receipt received. Checking it...", result)
        check, receipt = self.__receipt(result)
        if check:
            # Remove potentially private data from the packet
            receipt.ClientNonce = 0
            receipt.ServerNonce = 0
            receipt.RequestId = 0
            return receipt.__serialize__()
        else:
            return None

    def __receipt(self, msgObj):
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
            if not self.__bankClient.verify(receiptBytes, sigBytes):
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