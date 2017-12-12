'''
Created on Dec 1, 2017

@author: seth_
'''

import os, subprocess, time

class IMobileCodeEngine:
    def clearState(self, cookie): raise NotImplementedError()
    def getId(self): raise NotImplementedError()
    def runMobileCode(self, cookie, code): raise NotImplementedError()
    
    def getMobileCodeStatus(self, cookie): raise NotImplementedError()
    def getMobileCodeOutput(self, cookie): raise NotImplementedError()

class DefaultMobileCodeEngine(IMobileCodeEngine):
    def __init__(self):
        self._processes = {}
        
    def clearState(self, cookie):
        if cookie in self._processes:
            self._processes[cookie].finalize()
            del self._processes[cookie]
    
    def getId(self):
        return "Default Mobile Code Engine 1.0"
    
    def runMobileCode(self, cookie, code):
        tempfile = "/tmp/playground_mobilecode_script_{}_{}.py".format(os.getpid(), str(time.time()).replace(".","_"))
        try:
            with open(tempfile,"w+") as f:
                f.write(code)
            p = subprocess.Popen(["python", f.name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            
            self._processes[cookie] = ProcessPod(p, tempfile, time.time())
            result = True, ""
        except Exception as e:
            result = False, str(e)
        return result
    
    def getMobileCodeStatus(self, cookie):
        if not cookie in self._processes:
            # perhaps counter intuitively, if there is no such process,
            # we say that it's complete so we're not "waiting" for it
            return True, -1
        
        return self._processes[cookie].getStatus()
        
    
    def getMobileCodeOutput(self, cookie):
        if not cookie in self._processes:
            return None
        proc = self._processes[cookie]
        if proc.p.poll() == None:
            return None
        return proc.p.stdout.read()
    
class ProcessPod:
    def __init__(self, p, filename, startTime, endTime=0):
        self.p = p
        self.filename = filename
        self.startTime = startTime
        self.endTime = endTime
        
    def getStatus(self):
        if self.p.poll() == None:
            return False, time.time() - self.startTime
        elif self.endTime == 0:
            # it's over now. 
            if os.path.exists(self.filename):
                os.unlink(self.filename)
            self.endTime = time.time()
        return True, self.endTime - self.startTime
        
    def finalize(self):
        self.p.kill()
        if os.path.exists(self.filename):
            os.unlink(self.filename)
