'''
Created on Nov 30, 2017

@author: seth_
'''

from playground.network.packet import PacketType
from playground.network.packet.fieldtypes import UINT16, UINT32, UINT64, LIST, BUFFER, STRING, BOOL
#from playground.network.packet.fieldtypes.attributes import Optional
#from playground.common import CustomConstant as Constant

MOBILE_CODE_PACKAGE = "playground.org.mobilecode."

class MobileCodePacket(PacketType):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"MobileCodePacket"
    DEFINITION_VERSION = "1.0"
    FIELDS = []
    
class MobileCodeServiceDiscovery(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"MobileCodeServiceDiscovery"
    DEFINITION_VERSION = "1.0"
    FIELDS = []
    
class MobileCodeServiceDiscoveryResponse(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"MobileCodeServiceDiscoveryResponse"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Address", STRING),
        ("Port", UINT16),
        ("Traits", LIST(STRING))
        ]
    
class OpenSession(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"OpenSession"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ]
    
class OpenSessionResponse(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"OpenSessionResponse"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("WalletId", STRING),
        ("AuthId", STRING),
        ("EngineId", STRING),
        ("NegotiationAttributes", LIST(STRING))
        ]
    
class RunMobileCode(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"RunMobileCode"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("Code", STRING)
        ]

class GetMobileCodeStatus(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"GetMobileCodeStatus"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64)
        ]
    
class GetMobileCodeStatusResponse(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"GetMobileCodeStatusResponse"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("Complete", BOOL),
        ("Runtime", UINT32)
        ]
    
class GetMobileCodeResult(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"GetMobileCodeResult"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64)
        ]
    
class GetMobileCodeResultResponse(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"GetMobileCodeResultResponse"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("Result", BUFFER),
        ("Charges", UINT32)
        ]
    
class Payment(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"SubmitPayment"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("PaymentData", BUFFER)
        ]
    
class PaymentResponse(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"SubmitPaymentResult"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("Authorization", BUFFER)
        ]
    
class MobileCodeFailure(MobileCodePacket):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"MobileCodeFailure"
    DEFINITION_VERSION = "1.0"
    FIELDS = []
    
class GeneralFailure(MobileCodeFailure):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"GeneralFailure"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("ErrorMessage", STRING),
        ("Closed", BOOL)
        ]
    
class AuthFailure(MobileCodeFailure):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"AuthFailure"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("ErrorMessage", STRING),
        ("Closed", BOOL)
        ]
    
class WalletFailure(MobileCodeFailure):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"WalletFailure"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("ErrorMessage", STRING),
        ("Closed", BOOL)
        ]
    
class EngineFailure(MobileCodeFailure):
    DEFINITION_IDENTIFIER = MOBILE_CODE_PACKAGE+"EngineFailure"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("Cookie", UINT64),
        ("ErrorMessage", STRING),
        ("Closed", BOOL)
        ]