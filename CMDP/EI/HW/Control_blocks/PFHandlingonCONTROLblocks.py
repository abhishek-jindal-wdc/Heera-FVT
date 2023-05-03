import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
from collections import defaultdict
import CMDP.CMDP_History as History
import Lib.FWStructs.FWObjectWrapper as fwWrap

class PFhandler:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not PFhandler.__staticPFObj:
            PFhandler.__staticPFObj = super(PFhandler,cls).__new__(cls, *args, **kwargs)

        return PFhandler.__staticPFObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = GlobalVars.GlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.SDutilsObj = SDUtils.SDUtils()
        self.HistoryObj = History.EpicCallbacks()
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            if(self.HistoryObj.Verbose):
                self.wayPointDict = {
                    "WP_PS_PF_DETECTED"                 : [self.WP_PS_PF_DETECTED, 'PrintArguments']                    
                }
            else:
                self.wayPointDict = {
                    "WP_PS_PF_DETECTED"                 : [self.WP_PS_PF_DETECTED]                    
                }                
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
    
    def WP_PS_PF_DETECTED(self,eventKey,args, pid):
        self.PFdetected = True
                
    def ResetVariables(self):
        self.writtendata = []
        self.PFdetected = False
        self.XorDumpHappened = False
        self.RelinkingnotHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterPFHandling = None
        self.LogDumpHappened = False
        self.MTMconsolidationHappened = False
        self.xor_paritystores = []
        self.version= 0
        self.PrimaryLogBlock = True
        self.LogJBIDdataPrimary = {}
        self.LogJBIDdataSecondary = {}
        self.MTMvbaWritten = []
        self.MTMjbWritten = []
        self.XORopb = defaultdict(lambda:[])
        self.LatestProtectedJB = -1
        self.RelinkingHappened = False
        self.XORrecoveryStarted = False
        self.ParityRebuildStarted = False  
        
        if(self.vtfContainer.getActiveProtocol() != 'SD_OF_SDPCIe'):
            self.sctputilsobj.ErrorInjection(subOpcode=0x0001)
        
        
    def PFinjector(self,VBA):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1)        
        phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramError ,errorPersistence,0,1,0,0)
        self.livetObj.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, 'PF is injected to {}'.format(str(physical_address)))
        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    def PFHandlerXOR(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING XOR PF HANDLER *************')
        
        
        #Trigger XOR Writes
        #########################
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.globalVarsObj.ccmObj.DoFlushCache()                
        ########################        
                    
   
        
        #if(self.vtfContainer.getActiveProtocol() == 'SD_OF_SDPCIe'):
        #    self.sctputilsobj.ErrorInjection(subOpcode=0x0001)

        self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762
        #self.sctputilsobj.ErrorInjection(binType = "LOG")
        
        #self.sctputilsobj.ErrorInjection(binType = "XORCompaction")
        self.sctputilsobj.ErrorInjection(subOpcode=0, configType="singleError", operationType="XORstoreError", addrType="OPBID", addr=7, nsid=1, pattern="1WL", dataBuffer=None, binType=None, ErrLog=1, MBrevive=1, JBrevive=1, SurvivePC=1, isE2E=0, slot1=[0,0,0,0])
        
        
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.globalVarsObj.ccmObj.DoFlushCache()            
        
        
        self.stats = self.sctputilsobj.GetErrorHandlingStatistics()
        self.sctpParsedObj = fwWrap.FWDiagCustomObject(self.stats, "EH_ErrorCounterXML_s").EH_ErrorCounterXML_s.PS0.__dict__
        
        if(not self.sctpParsedObj['programFailure']):
            self.logger.Info(self.globalVarsObj.TAG, "XOR PF not detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "XOR PF not detected"                
             
        
        
        self.logger.Info(self.globalVarsObj.TAG, "############ XOR PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
            
        
    def PFHandlerLOG(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)          
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING LOG PF HANDLER *************')
        
        #Trigger LOG Writes
        #########################
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.globalVarsObj.ccmObj.DoFlushCache()                
        ########################        
                    
        
        if('ModeAfterSwitch' in kwargs.keys()):
            if(kwargs['ModeAfterSwitch'] != 'Operational'):
                if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.SDutilsObj.performShutdown(operation=self.globalVarsObj.randomObj.choice(['GSD','UGSD']))        
        

        #if(self.vtfContainer.getActiveProtocol() == 'SD_OF_SDPCIe'):
        #    self.sctputilsobj.ErrorInjection(subOpcode=0x0001)

        #self.sctputilsobj.ErrorInjection(binType = "LOG")
        self.sctputilsobj.ErrorInjection(subOpcode=0, configType="singleError", operationType="Prog", addrType="OPBID", addr=4, nsid=1, pattern="1WL", dataBuffer=None, binType=None, ErrLog=1, MBrevive=1, JBrevive=1, SurvivePC=1, isE2E=0, slot1=[0,0,0,0])
        
        #Trigger LOG Writes
        #########################
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.globalVarsObj.ccmObj.DoFlushCache()            
        ########################       
                 
        self.stats = self.sctputilsobj.GetErrorHandlingStatistics()
        self.sctpParsedObj = fwWrap.FWDiagCustomObject(self.stats, "EH_ErrorCounterXML_s").EH_ErrorCounterXML_s.PS0.__dict__
        
        if(not self.sctpParsedObj['programFailure']):
            self.logger.Info(self.globalVarsObj.TAG, "LOG PF not detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "LOG PF not detected"                
            
        self.logger.Info(self.globalVarsObj.TAG, "############ LOG PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def AllignedSequentialWrites(self,NoOfWrites):
        #Was getting consolidation at i= 9881
        currentLBA = self.HistoryObj.HistoryObj.LastWrittenLBA
        cycles_completed = 0
        self.SectorSize = 512
        self.FMU = 8
        gapLeft = int(32 * Constants.MB // self.SectorSize) 
        #Writes 8 sectors(4k) data sequentially for the above defined times.
        for writeNumber in range(NoOfWrites):
            if(currentLBA + self.FMU + gapLeft) >= int(self.globalVarsObj.endLba/2) :
                #Restart the cycle , start from first if it exceeds lastLBA
                cycles_completed += 1
                currentLBA = cycles_completed * self.FMU +1 
                if(currentLBA + self.FMU) >= int(self.globalVarsObj.endLba/2) :
                    currentLBA = 0
                    
            self.globalVarsObj.ccmObj.Write(currentLBA, self.FMU)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
                
            self.logger.Info(self.globalVarsObj.TAG, '%d : WRITE ON LBA %d of transfer length %d'%(writeNumber , currentLBA, self.FMU))
            currentLBA += (self.FMU + gapLeft + 1)
        self.HistoryObj.HistoryObj.LastWrittenLBA = currentLBA
            
    def PFHandlerMTM(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING MTM PF HANDLER *************')
        
    
        #Trigger MTM Writes
        #########################
        self.AllignedSequentialWrites(10000)
        
        ########################        
            
                    
        if('ModeAfterSwitch' in kwargs.keys()):
            if(kwargs['ModeAfterSwitch'] != 'Operational'):
                if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.SDutilsObj.performShutdown(operation='GSD')
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="ABORT") 
                else:
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 


        self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762
        self.sctputilsobj.ErrorInjection(binType = "MTM")
        
        
        #Trigger MTM Writes
        #########################
        self.AllignedSequentialWrites(5000)
        ######################## 
        
        
        self.stats = self.sctputilsobj.GetErrorHandlingStatistics()
        self.sctpParsedObj = fwWrap.FWDiagCustomObject(self.stats, "EH_ErrorCounterXML_s").EH_ErrorCounterXML_s.PS0.__dict__
        
        if(not self.sctpParsedObj['programFailure']):
            self.logger.Info(self.globalVarsObj.TAG, "MTM PF not detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "MTM PF not detected"                
             
        
        
        self.logger.Info(self.globalVarsObj.TAG, "############ MTM PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    
       
        
        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
