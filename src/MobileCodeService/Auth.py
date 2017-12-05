'''
Created on Dec 1, 2017

@author: seth_
'''
import random

class IMobileCodeServerAuth:
    AUTHID_ATTRIBUTE = "Auth.Id"
    TIMEOUT_ATTRIBUTE = "Auth.Timeout"
    FLATRATE_ATTRIBUTE = "Auth.Flatrate"
    TIMERATE_ATTRIBUTE = "Auth.Timerate"
    CONNECTOR_ATTRIBUTE = "Auth.Connector"
    
    PAYTO_ACCOUNT_ATTRIBUTE = "Auth.PaytoAccount"
    
    @classmethod
    def EncodeTrait(cls, key, value):
        return "{}={}".format(key,value)
    
    def getId(self): raise NotImplementedError()
    def getDiscoveryTraits(self): raise NotImplementedError()
    def getSessionCookie(self, clientCookie): raise NotImplementedError()
    def permit_newConnection(self, transport): raise NotImplementedError()
    def clearState(self, cookie): raise NotImplementedError()
    def permit_newSession(self, cookie, transport): raise NotImplementedError()
    def permit_runMobileCode(self, cookie, code): raise NotImplementedError()
    def getSessionAttributes(self, cookie): raise NotImplementedError()
    def getAuthorizedResult(self, cookie, rawOutput): raise NotImplementedError()
    def getCharges(self, cookie, runtime): raise NotImplementedError()
    
class IMobileCodeClientAuth:
    def permit_Connector(self, connectorName): raise NotImplementedError()
    def createCookie(self): raise NotImplementedError() 
    def permit_SessionOpen(self, clientCookie, sessionCookie, serverAuthId, negotiationAttributes, serverEngineId, serverWalletId):
        raise NotImplementedError()
    def permit_status(self, cookie, completed, runtime): raise NotImplementedError()
    def permit_result(self, cookie, result, charges): raise NotImplementedError()
    def getFinalResult(self, cookie, prePaymentResult, authorization): raise NotImplementedError()

class NullServerAuth(IMobileCodeServerAuth):
    
    def __init__(self):
        self.traits = {self.AUTHID_ATTRIBUTE: self.getId(),
                       self.TIMEOUT_ATTRIBUTE: 60,
                       self.FLATRATE_ATTRIBUTE: 0}
    
    def getId(self):
        return "Null Server Auth 1.0"
    
    def getDiscoveryTraits(self):
        return [ self.EncodeTrait(attr, self.traits[attr]) for attr in self.traits.keys() ]
    
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
        return self.getDiscoveryTraits()
    
    def getAuthorizedResult(self, cookie, rawOutput):
        return rawOutput, b""
    
    def getCharges(self, cookie, runtime):
        return 0
    
class NullClientAuth(IMobileCodeClientAuth):
    def permit_Connector(self, connectorName):
        return True
    
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

class SimplePayingServerAuth(NullServerAuth):
    def __init__(self, flatfee):
        assert(type(flatfee) == type(1))
        assert(flatfee >= 0)
        self.fee = flatfee
        self.RateTrait = (self.FLATRATE_ATTRIBUTE, self.fee)
        
    def getId(self):
        return "Simple Paying Server Auth 1.0"

    def getCharges(self, cookie, runtime):
        return self.fee

class SimplePayingClientAuth(NullClientAuth):
    pass