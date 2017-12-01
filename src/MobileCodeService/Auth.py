'''
Created on Dec 1, 2017

@author: seth_
'''
import random

class IMobileCodeServerAuth:
    TIMEOUT_ATTRIBUTE = "Timeout"
    
    def getId(self): raise NotImplementedError()
    def getSessionCookie(self, clientCookie): raise NotImplementedError()
    def permit_newConnection(self, transport): raise NotImplementedError()
    def clearState(self, cookie): raise NotImplementedError()
    def permit_newSession(self, cookie, transport): raise NotImplementedError()
    def permit_runMobileCode(self, cookie, code): raise NotImplementedError()
    def getSessionAttributes(self, cookie): raise NotImplementedError()
    def getAuthorizedResult(self, cookie, rawOutput): raise NotImplementedError()
    def getCharges(self, cookie, runtime): raise NotImplementedError()
    
class IMobileCodeClientAuth:
    def createCookie(self): raise NotImplementedError() 
    def permit_SessionOpen(self, clientCookie, sessionCookie, serverAuthId, negotiationAttributes, serverEngineId, serverWalletId):
        raise NotImplementedError()
    def permit_status(self, cookie, completed, runtime): raise NotImplementedError()
    def permit_result(self, cookie, result, charges): raise NotImplementedError()
    def getFinalResult(self, cookie, prePaymentResult, authorization): raise NotImplementedError()

class NullServerAuth(IMobileCodeServerAuth):
    def getId(self):
        return "Null Server Auth 1.0"
    
    def getSessionCookie(self, clientCookie):
        cookie = (clientCookie << 32) + random.randint(0,2**32)
        return cookie
    
    def permit_newConnection(self, transport):
        return True, ""
    
    def clearState(self, cookie):
        pass
    
    def permit_newSession(self, cookie, transport):
        return True, ""
    
    def permit_runMobileCode(self, cookie, code):
        return True, ""
    
    def getSessionAttributes(self, cookie):
        return []
    
    def getAuthorizedResult(self, cookie, rawOutput):
        return rawOutput, b""
    
    def getCharges(self, cookie, runtime):
        return 0
    
class NullClientAuth(IMobileCodeClientAuth):
    def createCookie(self):
        return random.randint(0, 2**32)
    
    def permit_SessionOpen(self, clientCookie, sessionCookie, serverAuthId, negotiationAttributes, serverEngineId, serverWalletId):
        if clientCookie == (sessionCookie >> 32):
            return True, ""
        return False, "Cookie Mismatch"
    
    def permit_status(self, cookie, completed, runtime):
        return True, ""
    
    def permit_result(self, cookie, result, charges):
        return True, ""
    
    def getFinalResult(self, cookie, prePaymentResult, authorization):
        return prePaymentResult