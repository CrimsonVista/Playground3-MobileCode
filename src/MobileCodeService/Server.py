'''
Originally created on Apr 2, 2014
Updated to Python3/Playground3 on Nov 28, 2017

@author: sethjn
'''

from .Packets import MobileCodePacket
from .Packets import OpenSession, OpenSessionResponse
from .Packets import RunMobileCode
from .Packets import GetMobileCodeStatus, GetMobileCodeStatusResponse
from .Packets import GetMobileCodeResult, GetMobileCodeResultResponse
from .Packets import Payment, PaymentResponse
from .Packets import GeneralFailure, AuthFailure, EngineFailure, WalletFailure

import playground
import logging
import time

from asyncio import get_event_loop, Protocol

logger = logging.getLogger("playground.org,"+__name__)

#from apps.bank.BankCore import LedgerLine

#RANDOM_u64 = lambda: random.randint(0,(2**64)-1)

class MobileCodeSession:
    def __init__(self, cookie):
        self.state = None
        self.cookie = cookie
        self.negotiationAttributes = {}

        self.runtime = None
        self.encryptedOutput = None
        self.decryptionKey = None
        
class ServerProtocol(Protocol):
    
    STATE_UNINIT = "Uninitialized"
    STATE_RESTORE_STATE = "Restore state in connectionless protocol"
    STATE_OPEN = "Open"
    STATE_FINISHED = "Finished"
    STATE_PURCHASE = "Purchase decryption key started"
    STATE_REREQUEST = "Rerequest decryption key"
    STATE_RUNNING = "Running code"
    STATE_ERROR = "Error"
    
    DEFAULT_SESSION_TIMEOUT = 1*60*60 # one hour maximum run
    
    Sessions = {}
    
    #SANDBOX_CONTROLLER = os.path.join(LOCATION_OF_PLAYGROUND, "extras", "sandbox", "IOEnabledSandbox.py")

    
    def __init__(self, wallet, auth, engine):
        
        # The ServerProtocol state machine can work in a connection oriented
        # or connectionless fashion. The restore signals return it to the 
        # saved state
        
        self._wallet = wallet
        self._auth = auth
        self._engine = engine
        self._state = self.STATE_UNINIT
        self._deserializer = MobileCodePacket.Deserializer()
        self._timeoutBuckets = []
        self.transport = None
        
    def connection_made(self, transport):
        mobileCodeClient = transport.get_extra_info("peername")
        logger.debug("Mobile Code Server received connection from {}".format(mobileCodeClient))
        permitted, reason = self._auth.permit_newConnection(transport)
        if not permitted:
            logger.debug("Connection denied. Reason={}".format(reason))
            return transport.close()
        self.transport = transport
    
    def data_received(self, data):
        self._deserializer.update(data)
        for pkt in self._deserializer.nextPackets():
            logger.debug("Server received packet with cookie {}".format(pkt.Cookie))
            session = self.Sessions.get(pkt.Cookie, None)
            if session == None:
                state = self.STATE_UNINIT
            else:
                state = session.state
            if state == self.STATE_UNINIT:
                self._handleOpenSession(pkt)
            elif state == self.STATE_OPEN:
                self._handleRunMobileCode(pkt)
            elif state == self.STATE_RUNNING:
                self._handleCheckMobileCodeStatus(pkt)
            elif state == self.STATE_FINISHED:
                self._handleMobileCodeFinished(pkt)
            else:
                logger.debug("Got unexpected state {}. Ignored.".format(state))
        self.transport.close()
        
    def _closeSession(self, cookie):
        if cookie in self.Sessions:
            del self.Sessions[cookie]
        self._wallet.clearState(cookie)
        self._auth.clearState(cookie)
        self._engine.clearState(cookie)
        
    def _sendError(self, errorPacket):
        if errorPacket.Closed:
            self._closeSession(errorPacket.Cookie)

        self.transport and self.transport.write(errorPacket.__serialize__())
        
    def _handleOpenSession(self, packet):
        if not isinstance(packet, OpenSession):
            return self._sendError(GeneralFailure(Cookie=packet.Cookie,
                                                  ErrorMessage="Expected Open Packet got {}".format(packet),
                                                  Closed = False))
        
        permitted, reason = self._auth.permit_newSession(packet.Cookie, self.transport)
        if not permitted:
            logger.debug("Attempt to open session denied. Reason={}".format(reason))
            return self._sendError(AuthFailure(Cookie=packet.Cookie,
                                                       ErrorMessage=reason, Closed=False))
            
        session = MobileCodeSession(self._auth.getSessionCookie(packet.Cookie))
        negotiationAttributes = self._auth.getSessionAttributes(packet.Cookie)
        session.negotiationAttributes = dict(negotiationAttributes)
        session.state = self.STATE_OPEN
        
        logger.debug("Server created session with cookie {}".format(session.cookie))
        self.Sessions[session.cookie] = session
        timeout = session.negotiationAttributes.get(self._auth.TIMEOUT_ATTRIBUTE, self.DEFAULT_SESSION_TIMEOUT)
        get_event_loop().call_later(timeout, self._closeSession, session.cookie)
        
        response = OpenSessionResponse(Cookie = session.cookie,
                                       WalletId = self._wallet.getId(),
                                       AuthId   = self._auth.getId(),
                                       EngineId = self._engine.getId(),
                                       NegotiationAttributes = negotiationAttributes)
        self.transport.write(response.__serialize__())
            
        
    def _handleRunMobileCode(self, packet):
        if not isinstance(packet, RunMobileCode):
            return self._sendError(GeneralFailure(Cookie=packet.Cookie,
                                                  ErrorMessage="Expected Run Mobile Code Packet got {}".format(packet),
                                                  Closed=True))
        session = self.Sessions[packet.Cookie]
        
        permitted, reason = self._auth.permit_runMobileCode(packet.Cookie, packet.Code)
        if not permitted:
            logger.debug("Request to run mobile code denied. Reason={}".format(reason))
            return self._sendError(AuthFailure(Cookie=packet.Cookie,
                                                       ErrorMessage=reason,
                                                       Closed=True))
        
        launched, reason = self._engine.runMobileCode(packet.Cookie, packet.Code)
        if not launched:
            logger.debug("Execution of mobile code failed. Reason={}".format(reason))
            return self._sendError(EngineFailure(Cookie=packet.Cookie,
                                                 ErrorMessage=reason,
                                                 Closed=True))
        else:
            session.state = self.STATE_RUNNING
            logger.debug("Execution of Python Code begun")
            return self._handleCheckMobileCodeStatus(packet)

        
    def _handleCheckMobileCodeStatus(self, packet):
        if not isinstance(packet, GetMobileCodeStatus) and not isinstance(packet, RunMobileCode):
            return self._sendError(GeneralFailure(Cookie=packet.Cookie,
                                                  ErrorMessage="Expected Check Mobile Code Status got {}".format(packet),
                                                  Closed=False))
        session = self.Sessions[packet.Cookie]
        
        complete, runtime = self._engine.getMobileCodeStatus(packet.Cookie)
        if runtime < 0:
            return self._sendError(EngineFailure(Cookie=packet.Cookie,
                                                 ErrorMessage="No status for cookie {}".format(packet.Cookie),
                                                 Closed=True))
        session.runtime = runtime
        if complete:
            session.state = self.STATE_FINISHED
            
        response = GetMobileCodeStatusResponse(Cookie=packet.Cookie, Complete=complete, Runtime=runtime)
        self.transport.write(response.__serialize__())
        
    def _handleMobileCodeFinished(self, packet):
        if isinstance(packet, GetMobileCodeStatus):
            return self._handleCheckMobileCodeStatus(packet)
        
        elif isinstance(packet, GetMobileCodeResult):
            session = self.Sessions[packet.Cookie]
            if session.encryptedOutput == None:
                complete, runtime = self._engine.getMobileCodeStatus(packet.Cookie)
                if runtime == -1:
                    # this must mean it was deleted!
                    error = GeneralFailure(Cookie=packet.Cookie, 
                                           ErrorMessage="Code result no longer available", Closed=True)
                    return self._sendError(error,)
                
                if not complete:
                    error = GeneralFailure(Cookie=packet.Cookie, 
                                           ErrorMessage="Somehow, code in finished state is not complete", 
                                           Closed=True)
                    return self._sendError(error)
                
                session.runtime = runtime
                
                rawOutput = self._engine.getMobileCodeOutput(packet.Cookie)
                session.authorizedOutput, session.authorizationData = self._auth.getAuthorizedResult(packet.Cookie, rawOutput)
                
                session.charges = self._auth.getCharges(packet.Cookie, runtime)
            response = GetMobileCodeResultResponse(Cookie=packet.Cookie, 
                                                   Result=session.authorizedOutput,
                                                   Charges=session.charges)
            self.transport.write(response.__serialize__())
        elif isinstance(packet, Payment):
            session = self.Sessions[packet.Cookie]
            
            accepted, message = self._wallet.processPayment(packet.Cookie, session.charges, packet.PaymentData)
            if accepted:
                response = PaymentResponse(Cookie=packet.Cookie,
                                           Authorization=session.authorizationData)
            else:
                response = WalletFailure(Cookie=packet.Cookie,
                                                       Message=message,
                                                       Closed=False)
            self.transport.write(response.__serialize__())
        else:
            return self._sendError(GeneralFailure(Cookie=packet.Cookie,
                                                  ErrorMessage="Received unexpected message in finished state: {}".format(packet),
                                                  Closed=False))
        
    