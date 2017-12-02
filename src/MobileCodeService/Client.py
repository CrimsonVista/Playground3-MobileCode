'''
Created on Nov 29, 2017

@author: seth_
'''

from .Packets import MobileCodePacket, MobileCodeFailure
from .Packets import OpenSession, OpenSessionResponse
from .Packets import RunMobileCode
from .Packets import GetMobileCodeStatus, GetMobileCodeStatusResponse
from .Packets import GetMobileCodeResult, GetMobileCodeResultResponse
from .Packets import Payment, PaymentResponse
from .Packets import GeneralFailure, AuthFailure, EngineFailure, WalletFailure

import playground

from asyncio import get_event_loop, Protocol, Future, run_coroutine_threadsafe
import random, logging

logger = logging.getLogger("playground.org,"+__name__)

class MobileCodeClient:
    def __init__(self, connector, address, port, code, auth, wallet):
        self.connector = connector
        self.address = address
        self.port = port
        
        self.auth = auth
        self.wallet = wallet
        
        # SESSION DATA
        self.state = None
        self.cookie = None
        self.code = code
        self.prePaymentResult = None
        self.finalResult = None
        self.charges = 0
        self.authorization = None
        self.paymentData = None
        self.cookie = None
        self.resultFuture = Future()
        
    def failed(self, reason):
        self.resultFuture.set_exception(Exception(reason))
        self.state = StatelessClient.STATE_ERROR
        
    def transition(self, newState):
        if self.state == [StatelessClient.STATE_ERROR or StatelessClient.STATE_CLOSED]:
            raise Exception("Cannot transition out of state {}".self.state)
        self.state = newState
        
        if self.state == StatelessClient.STATE_CLOSED:
            self.resultFuture.set_result(self.finalResult)
            
        else:
        
            client = StatelessClient(self, self.auth, self.wallet)
            coro = playground.getConnector(self.connector).create_playground_connection(lambda: client, self.address, self.port)
            get_event_loop().create_task(coro)
            #coro = playground.getConnector(self.connector).create_playground_server(lambda: client, self.port)
            #server = loop.run_until_complete(coro)
        
    def run(self):
        logging.debug("Mobile Code Client starting")
        self.transition(StatelessClient.STATE_START)
        return self.resultFuture

class StatelessClient(Protocol):
    STATE_START   = "Initial State"
    STATE_OPEN    = "Opening Session for Mobile Code"
    STATE_RUNNING = "Mobile Code Running"
    STATE_FINISHED= "Mobile Code Finished"
    STATE_PAYMENT = "Make Payment"
    
    STATE_ERROR = "ERROR STATE FAILURE"
    
    STATE_CLOSED = "Mobile Code Session Closed"
    
    def __init__(self, session, auth, wallet):
        self.session = session
        self.transport = None
        self.deserializer = MobileCodePacket.Deserializer()
        
        self.auth = auth
        self.wallet = wallet
        
    def connection_made(self, transport):
        logger.debug("Mobile Code Client connected. State is {}".format(self.session.state))
        self.transport = transport
        if self.session.state == self.STATE_START:
            return self.sendOpenSession()
        elif self.session.state == self.STATE_OPEN:
            return self.sendMobileCode()
        elif self.session.state == self.STATE_RUNNING:
            return self.sendStatusRequest()
        elif self.session.state == self.STATE_FINISHED:
            return self.sendResultRequest()
        elif self.session.state == self.STATE_PAYMENT:
            return self.sendPaymentRequest()
        else:
            raise Exception("Unknown state {}".format(self.session.state))
            
    def sendOpenSession(self):
        self.session.cookie = self.auth.createCookie()
        request = OpenSession(Cookie=self.session.cookie)
        self.transport.write(request.__serialize__())
        
    def handleOpenSession(self, response):
        if not isinstance(response, OpenSessionResponse):
            return self._handleFailure(Exception("Expected OpenSessionResponse but got {}".format(response)))
        updatedCookie = response.Cookie
        serverAuthId = response.AuthId
        serverEngineId = response.EngineId
        serverWalletId = response.WalletId
        negotiationAttributes = response.NegotiationAttributes
        
        permitted, reason = self.auth.permit_SessionOpen(self.session.cookie, updatedCookie, 
                                                          serverAuthId, negotiationAttributes,
                                                          serverEngineId, serverWalletId)
        
        if not permitted:
            self.session.failed(reason)
        else:
            self.session.cookie = updatedCookie
            self.session.transition(self.STATE_OPEN)
        
    def sendMobileCode(self):
        request = RunMobileCode(Cookie=self.session.cookie,
                                Code=self.session.code)
        self.transport.write(request.__serialize__())
        
    def handleMobileCode(self, response):
        return self.handleStatusRequest(response)
        
    def sendStatusRequest(self):
        request = GetMobileCodeStatus(Cookie=self.session.cookie)
        self.transport.write(request.__serialize__())
        
    def handleStatusRequest(self, response):
        if not isinstance(response, GetMobileCodeStatusResponse):
            return self._handleFailure(Exception("Expected GetMobileCodeStatusResponse but got {}".format(response)))
        
        permitted, reason = self.auth.permit_status(response.Cookie, response.Complete, response.Runtime)
        if not permitted:
            return self.session.failed(reason)
        
        complete = response.Complete
        self.session.runtime = response.Runtime
        
        if complete:
            logger.debug("Code is complete. runtime is {}".format(self.session.runtime))
            self.session.transition(self.STATE_FINISHED)
        else:
            logger.debug("Code is not complete. runtime is {}".format(self.session.runtime))
            get_event_loop().call_later(3.0, self.session.transition, self.STATE_RUNNING)
        
    def sendResultRequest(self):
        request = GetMobileCodeResult(Cookie=self.session.cookie)
        self.transport.write(request.__serialize__())
        
    def handleResultRequest(self, response):
        if not isinstance(response, GetMobileCodeResultResponse):
            return self._handleFailure(Exception("Expected GetMobileCodeResultResponse but got {}".format(response)))
        
        permitted, reason = self.auth.permit_result(response.Cookie, response.Result, response.Charges)
        if not permitted:
            return self.session.failed(reason)
        
        self.session.prePaymentResult = response.Result
        self.session.charges = response.Charges
        
        self.session.transition(self.STATE_PAYMENT)
        
    def sendPaymentRequest(self):
        if self.session.charges > 0:
            coro = self.wallet.getPayment(self.session.cookie, self.session.charges)
            fut = run_coroutine_threadsafe(coro, get_event_loop())
            fut.add_done_callback(self.__sendPayment)
        else:
            paymentData = b""
            fut = Future()
            fut.set_result((paymentData, None))
            self.__sendPayment(fut)

    def __sendPayment(self, result):
        assert(result.exception() is None)
        paymentData, message = result.result()
        if not paymentData:
            return self.session.failed(message)
        self.session.paymentData = paymentData
        request = Payment(Cookie=self.session.cookie,
                          PaymentData=self.session.paymentData)
        self.transport.write(request.__serialize__())
        print("Client has sent the payment!")
        
    def handlePaymentRequest(self, response):
        if not isinstance(response, PaymentResponse):
            return self._handleFailure(Exception("Expected PaymentResponse but got {}".format(response)))
        self.session.authorization = response.Authorization
        self.session.finalResult = self.auth.getFinalResult(self.session.cookie, self.session.prePaymentResult, self.session.authorization)
        self.session.transition(self.STATE_CLOSED)
        
    def data_received(self, data):
        self.deserializer.update(data)
        for pkt in self.deserializer.nextPackets():
            if isinstance(pkt, MobileCodeFailure):
                return self._handleFailure(pkt)
            
            elif self.session.state == self.STATE_START:
                return self.handleOpenSession(pkt)
            elif self.session.state == self.STATE_OPEN:
                return self.handleMobileCode(pkt)
            elif self.session.state == self.STATE_RUNNING:
                return self.handleStatusRequest(pkt)
            elif self.session.state == self.STATE_FINISHED:
                return self.handleResultRequest(pkt)
            elif self.session.state == self.STATE_PAYMENT:
                return self.handlePaymentRequest(pkt)
            else:
                raise Exception("Unknown state {}".format(self.session.state))
                
            
    def _handleFailure(self, failure):
        # TODO late. Better error handling
        
        if isinstance(failure, Exception):
            errorMessage = str(failure)
        else:
            errorMessage = failure.ErrorMessage
        logger.debug("Mobile Code Execution Failed: {}".format(errorMessage))
        # TODO later. Handle different failures differently
        self.session.failed(errorMessage)     