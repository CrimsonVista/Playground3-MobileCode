'''
reated on Dec 2, 2017

@author: sethjn
'''
import ParallelTSP_mobile
maxPaths,  numToPath, shortestPath = ParallelTSP_mobile.maxPaths, ParallelTSP_mobile.numToPath, ParallelTSP_mobile.computeShortestPath

import sys
"""
TODO: Real install, real paths. For now, just assume the follwoing

  Playground3-MobileCode\src\MobileCodeService
  BitPoints-Bank-Playground3-\

Assume we're in samples, find relative root
"""
import os
sys.path.append("../../../Playground3-MobileCode/src")
sys.path.append("../../../BitPoints-Bank-Playground3-")
  
from MobileCodeService.Packets import MobileCodePacket, MobileCodeFailure
from MobileCodeService.Auth import IMobileCodeServerAuth, NullClientAuth, SimplePayingClientAuth
from MobileCodeService.Wallet import NullClientWallet, PayingClientWallet
from MobileCodeService.Client import MobileCodeClient, MobileCodeServerTracker
from MobileCodeService.Packets import GeneralFailure
#from BitPoints_Bank_Playground3.ui.CLIShell import TwistedStdioReplacement, CLIShell
from ui.CLIShell import CLIShell, AdvancedStdio

from playground.common import Timer, Minutes, Seconds
import playground
#from cryptography import x509
from asyncio import get_event_loop, Protocol, Future
import random, logging, sys, os, getpass, math, time, shutil, subprocess, asyncio
import _pickle as cPickle
from playground.asyncio_lib.SimpleCondition import SimpleCondition
#from asyncio import Condition

logger = logging.getLogger("playground.org,"+__name__)

from cryptography.hazmat.backends import default_backend
backend = default_backend()

def getCertFromBytes(pem_data):
    return x509.load_pem_x509_certificate(pem_data, backend)

"""
ParallelTSP.py

This is a distributed algorithm for calculating the traveling salesman
problem (TSP). 

The traveling salesman problem is formulated as a person traveling to
n different cities. There are different costs associated with the
connection between each city. In the classic version, the cost is "distance"
but don't be fooled. Just because the distance between X and Y is d1 and
the distance between Y and Z is d2, don't assume that the distance between
X and Z can't be smaller than d1 + d2, or even than d1 or d2 alone. The
costs cannot be predicted through any kind of transitivity. Think of it
more like the cost of airline tickets. The costs between any pair
of cities is not just based on distance, but on how many people travel
between them, the difficulties of access, and so forth.

Given this backdrop, the question is, how do you find the shortest path
through the network, where the salesman visits every city and returns 
home (a complete circuit) with the shortest path (lowest cost)?

This algorithm is the naive "brute force" version. It basically tries
all possible combinations. The only optimization is that it keeps track
of the current shortest path and ignores completing branches that are
already longer than the known minimum.

To make it distributed, a subset of the brute force computations are
chunked out and given to a remote node. The remote node returns the
shortest path for that subset.

 
"""

with open("ParallelTSP_mobile.py") as f:
    tspCodeTemplate = f.read()
 
def generateDistanceMatrix(n, minCost=1, maxCost=9):
    """
    This generates a distance matrix m such that m[i][j] 
    is the distance between city number i and city number j.
    m[i][i] is always zero, and m[i][j] == m[j][i]
    """
    if n < 3: raise Exception("TSP requires 3 or more cities")
    if minCost < 1: raise Exception("TSP requires non-zero, non-negative cost between cities")
    
    # fill first diagonal half of matrix
    matrix = [ [(column > row and random.randint(minCost, maxCost) or 0) for column in range(n)] for row in range(n) ]
    # mirror other diagonal half, keeping the actual diagonal ([i][i]) zero
    for row in range(n):
        for column in range(row):
            matrix[row][column] = matrix[column][row]
    return matrix

def processCodeTemplate(s,replacements):
    """
    Given a code template, replace strings and remove comments
    """
    while '"""REM_START' in s and 'REM_END"""' in s:
        startIndex = s.find('"""REM_START')
        endIndex = s.find('REM_END"""') + len('REM_END"""')
        if endIndex < startIndex: break
        s = s[:startIndex] + s[endIndex:]
    
    # replace strings; multiple times if necessary
    for key in replacements:
        while key in s:
            s = s.replace(key, str(replacements[key]))
    return s

class AddrPod(object):
    def __init__(self, addr):
        self.addr = addr
        self.jobsSent = 0
        self.jobsCompleted = 0
        self.pathsCompleted = 0
        self.jobErrors = 0
        self.paid = 0
        self.currentJob = None
        self.alive = True
        self.connector = "default"
        
    def assignJob(self, codeId):
        self.currentJob = codeId
        self.jobsSent += 1
        
    def jobComplete(self, paths, cost):
        self.currentJob = None
        self.paid += cost
        self.pathsCompleted += paths
        self.jobsCompleted += 1
        
    def jobFailed(self, cost):
        self.currentJob = None
        self.paid += cost
        self.jobErrors += 1
        
        
class ParallelTSP:
    #TODO: This class is big, confusing, monolithic, and all kinds of bad.
    #NEEDS REFACTORING!!!!!
    
    PATHS_PER_PARALLEL = 150000
    VERIFY_ODDS = .1
    
    def getCodeString(self, startPath, endPath):
        """
        Get the code string. Note that the replacements are in quotes,
        and the quotes have to be removed. That's why they're stored with
        the quotes included.
        """
        return processCodeTemplate(tspCodeTemplate, {
             '"__sandbox__"':'"__main__"',
             '"__template_cities__"':self.__citiesStr, 
             '"__template_start_num__"':startPath, 
             '"__template_end_num__"':endPath})
    
    def __init__(self, tracker, auth, wallet, n, pathsPerParallel=None, maxRate=20):

        self.tracker =tracker
        self.auth = auth
        self.wallet = wallet
        
        self.__matrix = generateDistanceMatrix(n)
        self.__parallelCodes = {}
        self.__citiesStr = "[" + ",\n".join([str(row)+"\n" for row in self.__matrix]) + "]"
        self.__maxPaths = maxPaths(n)
        self.__curPath = 0
        self.__pathsPerParallel = pathsPerParallel and pathsPerParallel or self.PATHS_PER_PARALLEL

        self.__shortest = None
        self.__bestPath = None
        self.__resubmit = []
        self.__finished = False
        self.__checkIds = {}
        self.__idsToPaths = {}
        self.__completedPaths = 0
        self.__addrData = {}
        self.__maxRate = maxRate
        self.__serverAvailableCondition = SimpleCondition()
        self.__serversAvailable = []
        
    def finished(self): 
        return self.__finished
    
    def citiesMatrix(self): return self.__matrix
    
    def finalResult(self): return self.__shortest, self.__bestPath
        
    def hasNext(self):
        return (self.__curPath < self.__maxPaths)
    
    def mobileCodeId(self):
        return "Parallel TSP"
    
    def maxRate(self):
        return self.__maxRate
    
    def maxRuntime(self):
        return 1*60*60
    
    def maxPaths(self):
        return self.__maxPaths
    
    def currentBestPath(self):
        return (self.__bestPath, self.__shortest)
    
    def iterAddrStats(self):
        for addr in self.__addrData.values():
            yield addr
    
    def currentExecutions(self):
        executions = []
        for codeId in self.__parallelCodes.keys():
            paths, computingAddr, finished = self.__idsToPaths[codeId]
            executions.append((codeId, paths, computingAddr, finished))
        return executions
    
    def completedPathCount(self):
        return self.__completedPaths
        
    def getNextCodeUnit(self, addr):
        """
        Get the next piece of mobile code for the server at the
        address. Check if there are jobs that need to be resubmitted,
        otherwise create a new job
        """
        if addr not in self.__addrData:
            return None, None # not yet processed.
            
        if self.__addrData[addr].currentJob != None or not self.__addrData[addr].alive:
            return None, None
        
        while self.__resubmit:
            codeStr, codeId = self.__resubmit.pop()
            if codeId not in self.__parallelCodes: continue
            self.__parallelCodes[codeId][1] = addr
            self.__idsToPaths[codeId][1] = addr
            self.__addrData[addr].assignJob(codeId)
            return codeStr, codeId
        
        if not self.hasNext():
            # Looks like we're already done.
            return None, None
        
        start = self.__curPath
        end = min(start + (self.__pathsPerParallel-1), self.__maxPaths)

        instructionStr = self.getCodeString(start, end)
        #instruction = playground.network.common.DefaultPlaygroundMobileCodeUnit(codeStr)
        codeId = random.randint(0,(2**64)-1)
        self.__parallelCodes[codeId] = [instructionStr, addr]
        self.__idsToPaths[codeId] = [(start,end), addr, False]
        logger.info("CodeStr Len: %d" % len(instructionStr))
        if random.random() < self.VERIFY_ODDS:
            self.__checkIds[codeId] = (start, end)
        self.__curPath = end+1
        self.__addrData[addr].assignJob(codeId)
        return instructionStr, codeId
    
    def pickleBack(self, codeId, future, cost):
        codeOutput = future.result()
        
        logger.info("Received a result pickle with id %s" % (str(codeId),))
        if codeId  not in self.__parallelCodes:
            logger.info("No such ID %s" % (str(codeId),))
            return False, "No such ID"
        
        addr = self.__parallelCodes[codeId][1]
        logger.info("Now verifying result pickle from %s" % (str(addr),))
        
        # OK. To load the CodeOutput, it's in bytes, but its bytes
        # of a string that has only ascii characters... or better
        # only have them. If it doesn't have them, it was an error 
        logger.debug("Data: \n{}".format(codeOutput))
        try:
            pickleData = codeOutput.decode('utf8')
            if pickleData.endswith("\n"):
                pickleData = pickleData[:-1]
            resultObj = cPickle.loads(bytes.fromhex(pickleData)) # pickledStr
        except Exception as e:
            logger.info("Pickle load failed: {}".format(e))
            resultObj = Exception(codeOutput) # assume it is an exception
        
        if not isinstance(resultObj, Exception):
            return self.codeCallback(codeId, resultObj, cost)
        else:
            return self.codeErrback(codeId, resultObj, cost)
    
    def codeCallback(self, id, resultObj, cost):
        logger.info("callback: %s" % str(resultObj))
        try:
            dist, path = resultObj
        except:
            return False, "Invalid result. Expected distance, path"
        if type(dist) != int or type(path) != list:
            return False, "Invalid result, Expected int, list"
        verifiedOK = True
        addr = self.__parallelCodes[id][1]
        
        if id in self.__checkIds:
            logger.info("Validating ID %d" % id)
            start, end = self.__checkIds[id]
            del self.__checkIds[id]
            expectedDist, expectedPath = shortestPath(self.__matrix, start, end)
            if expectedDist != dist or expectedPath != path:
                logger.info("Verification failure. Expected %s (%d) but got %s (%d)" % (str(expectedPath), expectedDist,
                                                                                        str(path), dist))
                verifiedOK = False
                dist, path = expectedDist, expectedPath
        if verifiedOK: 
            self.__idsToPaths[id][2] = True
            start, end = self.__idsToPaths[id][0]
            self.__completedPaths += (end-start)+1
            self.__addrData[addr].jobComplete((end-start)+1, cost)
            self.notifyNewServer(*addr)
        else:
            self.__addrData[addr].jobFailed(cost)
        del self.__parallelCodes[id]
        if self.__shortest == None or dist < self.__shortest:
            self.__shortest = dist
            self.__bestPath = path
        if (not self.hasNext()) and len(self.__parallelCodes) == 0 and len(self.__resubmit) == 0:
            self.__finished = True
            logger.info("==FINISHED==")
        if verifiedOK:
            return True, ""
        else:
            return False, "Failed verification."
            
    def codeErrback(self, id, exceptionObj, cost):
        logger.info("exception back: %s" % str(exceptionObj))
        if id not in self.__parallelCodes:
            return False, "Unknown id %d" % id
        addr = self.__parallelCodes[id][1]
        self.__addrData[addr].jobFailed(cost)
        self.__resubmit.append((self.__parallelCodes[id][0], id))
        self.__idsToPaths[1] = "<Needs Reassignment>"
        return False, "There shouldn't be exceptions"
        
    
    def updateAvailableServers(self):
        validTime = 120.0
        servers = []
        for serverKey in self.tracker.serverDb:
            lastSeen, traits = self.tracker.serverDb[serverKey]
            if serverKey not in self.__addrData:
                self.__addrData[serverKey] = AddrPod(serverKey)
            for traitString in traits:
                if "=" in traitString:
                    k, v = traitString.split("=")
                    if k.strip() == IMobileCodeServerAuth.CONNECTOR_ATTRIBUTE:
                        self.__addrData[serverKey].connector = v.strip()
            if time.time() - lastSeen > validTime:
                self.__addrData[serverKey].alive = False
                continue
            if serverKey in self.__addrData and self.__addrData[serverKey].currentJob != None:
                continue
            if not self.auth.permit_Connector(self.__addrData[serverKey].connector):
                self.__addrData[serverKey].connector = None
                continue
            servers.append(serverKey)
        self.__serversAvailable = servers
        self.__serverAvailableCondition.notify()
    
    def notifyNewServer(self, address, port):
        self.updateAvailableServers()
    
    async def start(self):
        self.updateAvailableServers()
        self.tracker.registerListener(self.notifyNewServer)
        while not self.finished():
            nextServer = None
            while len(self.__serversAvailable) == 0:
                await self.__serverAvailableCondition.awaitCondition(lambda: len(self.__serversAvailable) > 0)
                if self.finished(): break
            nextServer = self.__serversAvailable.pop(0)
            
            # check the connector for the mobile code server
            connector = self.__addrData[nextServer].connector
            if not connector: continue
            
            #Get the code to run
            mobileCode, codeId = self.getNextCodeUnit(nextServer)
            if mobileCode:
                address, port = nextServer
                oneShotClient = MobileCodeClient(connector, address, port, mobileCode, 
                                                 self.auth,  self.wallet)
                # MobileCodeClient(connector, address, port, mobileCode, auth, wallet)
                result = oneShotClient.run()
                result.add_done_callback(lambda future: self.pickleBack(codeId, future, oneShotClient.charges))
            

class ParallelTSPCLI(CLIShell):
        BANNER = """
    Parallel Traveling Salesman. Sends out paths to be computed
    by remote hosts. Results are collected until the best path
    is known. Execute 'start' to begin the computation. 
    Execute 'status' to see how things are going.
    """
        def __init__(self, ptsp):
            CLIShell.__init__(self, banner = self.BANNER)   

            self.ptsp = ptsp
            self.options = {}
            self.__poll = None
            self.__pollingCallback = None
            self.__started = False
            startHandler = CLIShell.CommandHandler("start",helpTxt="Start the parallelTsp",
                                                   defaultCb=self.start,
                                                   mode=CLIShell.CommandHandler.STANDARD_MODE)
            self.registerCommand(startHandler)
            #configHandler = CLIShell.CommandHandler("config",helpTxt="Show current config (can't change yet)",
            #                                        defaultCb=self.config,
            #                                        mode=CLIShell.CommandHandler.STANDARD_MODE)
            #self.registerCommand(configHandler)
            statusHandler = CLIShell.CommandHandler("status",helpTxt="Show current status",
                                                    defaultCb=self.status,
                                                    mode=CLIShell.CommandHandler.STANDARD_MODE)
            statusHandler.configure(1, self.status, helpTxt="Show status and set to poll the status",
                                    usage="[polling time]")
            self.registerCommand(statusHandler)
            #checkbalanceHandler = CLIShell.CommandHandler("balance", helpTxt="Check the current account balance",
            #                                              defaultCb=self.checkBalance,
            #                                              mode=CLIShell.CommandHandler.STANDARD_MODE)
            #self.registerCommand(checkbalanceHandler)
            sampleCodeString = CLIShell.CommandHandler("sample", helpTxt="Generate A sample remote code string",
                                                       mode=CLIShell.CommandHandler.STANDARD_MODE)
            sampleCodeString.configure(3, self.getSampleCodeString, 
                                       helpTxt="Get a sample code string for the given parameters", 
                                       usage="[startpath] [endpath] [filename]")
            self.registerCommand(sampleCodeString)
            
            #blacklistCommand = CLIShell.CommandHandler("blacklist", helpTxt="Get the list of blacklisted nodes",
            #                                           mode=CLIShell.CommandHandler.STANDARD_MODE,
            #                                           defaultCb=self.blacklistedAddrs)
            #self.registerCommand(blacklistCommand)
            
        def __checkBalanceResponse(self, f, writer):
            e = f.exception()
            if not e:
                self.transport.write("Current balance in account: %d\n" % f.result())
            else:
                self.transport.write("Check balance failed: {}\n".format(e))
            
        def checkBalance(self, writer):
            f = self.ptsp.wallet.checkBalance()
            f.add_done_callback(lambda f: self.__checkBalanceResponse(f, writer))
            
        def config(self, writer):
            for k, v in self.options.items():
                self.transport.write("%s: %s\n" % (k,v))
                
        def getSampleCodeString(self, writer, startPath, endPath, filename):
            try:
                startPath = int(startPath)
            except:
                writer("Invalid start path\n")
                return
            try:
                endPath = int(endPath)
            except:
                writer("Invalid end path\n")
                return
            codeStr = self.ptsp.getCodeString(startPath, endPath)
            with open(filename, "w+") as f:
                f.write(codeStr)
            writer("Wrote file %s\n" % filename)
            
        def blacklistedAddrs(self, writer):
            if not self.__started:
                self.transport.write("Can't get blacklist Not yet started\n")
                return
            bl = self.ptsp.auth.getBlacklist()
            writer("Blacklisted Addresses:\n")
            for addr in bl:
                writer("  %s\n" % addr)
            writer("\n")
                
        def status(self, writer, poll=None):
            if not self.__started:
                self.transport.write("Can't get status. Not yet started\n")
                return
            if poll != None:
                # We're changing the polling time. Cancel the current, then
                # set the new polling time
                try:
                    poll = int(poll)
                except:
                    self.transport.write("Polling time must be an integer. Got %s" % poll)
                    return
                if poll < 0:
                    self.transport.write("Polling time must be a positive integer. Got %d" % poll)
                    return
                if self.__pollingCallback:
                    self.__pollingCallback.cancel()
                    if poll == 0:
                        self.__pollingCallback = None
                self.__poll = poll
            template = """
        Max Paths: %(Max_Path_Count)s
        Completed Paths: %(Completed_Path_Count)s
        Currently Executing Paths: %(Current_Path_Count)s
    %(Current_Execution_Details)s
        Address Data:
    %(Addr_Stats)s"""
            if self.ptsp.finished():
                template = ("FINISHED: %s\n" % str(self.ptsp.finalResult())) + template
            templateData = {}
            templateData["Max_Path_Count"] = self.ptsp.maxPaths()
            templateData["Completed_Path_Count"] = self.ptsp.completedPathCount()
            
            currStr = ''
            currentExecutions = self.ptsp.currentExecutions()
            currentPathCount = 0
            for execId, paths, addr, finished in currentExecutions:
                currStr += "\t\t%s:\t%s\t%s\n" % (addr, execId, paths)
                start, end = paths
                currentPathCount += (end-start)+1
            templateData["Current_Path_Count"] = currentPathCount
            addrStr =  "\t\t%-15s\t%-10s\t%-10s\t%-10s\t%s\n" % ("Address", "Jobs Sent", "Completed Jobs", "Errors", "Paid")
            for addrData in self.ptsp.iterAddrStats():
                addrStr += "\t\t%-15s\t%-10s\t%-10s\t%s\t%s\n" % (addrData.addr, addrData.jobsSent, 
                                                                  addrData.jobsCompleted, addrData.jobErrors, 
                                                                  addrData.paid)  
            
            templateData["Current_Execution_Details"] = currStr
            templateData["Addr_Stats"] = addrStr
            
            self.transport.write((template % templateData)+"\n")
            if self.__poll:
                # if we have a polling time set, fire.
                self.__pollingCallback = Timer(lambda: self.status(writer))
                self.__pollingCallback.run(self.__poll)
            
        def start(self, writer):
            if self.__started:
                self.transport("Program already started.\n")
                return
            self.__started=True
            coro = self.ptsp.start()
            future = asyncio.get_event_loop().create_task(coro)
            future.add_done_callback(lambda future: self.finish())
            #kargs = {}
            #parameters = self.options.getSection("ptsp.parameters")
            #if parameters.has_key("n"):
            #    kargs["n"] = int(parameters["n"])
            #if parameters.has_key("paths_per_parallel_execution"):
            #    kargs["pathsPerParallel"] = int(parameters["paths_per_parallel_execution"])
            #self.ptsp = ParallelTSP()#**kargs)
            
            
            #Parallel(self.ptsp, self.finish)
            
        def finish(self):
            #resultsFile = "tsp_results."+str(time.time())+".txt"
            self.transport.write("Finished computation\n")
            self.transport.write("\tResult: %s\n" % str(self.ptsp.finalResult()))
            if self.__pollingCallback:
                self.__pollingCallback.cancel()
                self.__pollingCallback = None

USAGE = """
ParallelTSP <bank cert> <username> <payfromaccount> -stack=<network stack>
"""
#<bank cert> <login name> <account name> <playground server> <playground port> <-stack=stack_name>
#"""

def main():
    from OnlineBank import BankClientProtocol, BANK_FIXED_PLAYGROUND_ADDR, BANK_FIXED_PLAYGROUND_PORT
    from CipherUtil import loadCertFromFile
    #logctx = LoggingContext()
    #logctx.nodeId = "parallelTSP_"+myAddr.toString()

    # set this up as a configuration option
    #logctx.doPacketTracing = True
    #playground.playgroundlog.startLogging(logctx)

    # Having placeHolders for asyncio

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=True)
    ptspArgs = {}
    
    from playground.common.logging import EnablePresetLogging, PRESET_DEBUG
    #EnablePresetLogging(PRESET_DEBUG)
        
    args= sys.argv[1:]
    i = 0
    for arg in args:
        if arg.startswith("-"):
                k,v = arg.split("=")
                ptspArgs[k]=v
        else:
                ptspArgs[i] = arg
                i+=1
    stack = ptspArgs.get("-stack","default")
    bankAddress = ptspArgs.get("-bankaddr", BANK_FIXED_PLAYGROUND_ADDR)
    bankPort = ptspArgs.get("-bankport", BANK_FIXED_PLAYGROUND_PORT)
            
    tracker = MobileCodeServerTracker()
    tracker.startScan()

    bankcert = loadCertFromFile(ptspArgs[0])
    payeraccount = ptspArgs[2]
    username = args[1]
    pw = getpass.getpass("Enter bank password for {}: ".format(username))

    bankstackfactory = lambda: BankClientProtocol(bankcert, username, pw)
    wallet = PayingClientWallet(stack, bankstackfactory, username, pw, payeraccount,
                                bankAddress, bankPort)

    clientAuth = SimplePayingClientAuth()
    PTSP = ParallelTSP(tracker, clientAuth, wallet, n=5)        
    def initShell():
        uiFactory = ParallelTSPCLI(PTSP)
        uiFactory.registerExitListener(lambda reason: loop.call_later(2.0, loop.stop))
        a = AdvancedStdio(uiFactory)

    # loop.set_debug(enabled=True)
    loop.call_soon(initShell)

    
    # TODO - Will switchAddr be changed to "localhost" ?
    # stack can be "default" or user provided stack from ~/.playgroun/connector
    
    
    #parallelMaster = MobileCodeClient(stack, switchAddr, port, samplecode, NullClientAuth(), NullClientWallet())
    #coro = playground.getConnector(stack).create_playground_connection(lambda: TwistedStdioReplacement.StandardIO(ParallelTSPCLI(configOptions, parallelMaster)),switchAddr, port)
    #transport, protocol = loop.run_until_complete(coro)
    loop.run_forever()
    tracker.stopScan()
    loop.close()

    
if __name__ == "__main__":
    main()
