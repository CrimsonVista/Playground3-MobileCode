'''
Created on Dec 1, 2017

@author: seth_
'''

class IMobileCodeServerWallet:
    def clearState(self, cookie): raise NotImplementedError()
    def getId(self): raise NotImplementedError() 
    def processPayment(self, cookie, charges, paymentData): raise NotImplementedError()
    
class IMobileCodeClientWallet:
    def getPayment(self, cookie, charges): raise NotImplementedError()

class NullServerWallet(IMobileCodeServerWallet):
    def clearState(self, cookie):
        pass
    
    def getId(self):
        return "Null Wallet 1.0"  
    
    def processPayment(self, cookie, charges, paymentData):
        if charges == 0:
            return True, ""
        return False, "Null Wallet doesn't accept payments"  

class NullClientWallet(IMobileCodeClientWallet):
    def getPayment(self, cookie, charges):
        return None, "Null wallet does not make payment"