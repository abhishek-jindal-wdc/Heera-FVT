#STM LEVELS {'REHLevel: ReadRetry || REHLevel: BES5  || REHLevel: BES7'}
# 1 --  Read Retry --- Read retry waypoint 0 BER stm
# 2 --  BES5  ---- DGM BES args[2] == 1 ---- 0 BER
# 3 --  BES7  ---- DGM BES args[2] == 1 ---- 0.9 STM 

import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
from collections import defaultdict
import random 
import CMDP.CMDP_History as History


class CECChandler:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not CECChandler.__staticPFObj:
            CECChandler.__staticPFObj = super(CECChandler,cls).__new__(cls, *args, **kwargs)

        return CECChandler.__staticPFObj

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
        #self.cmdpAPLib = CMDP_AP_Lib.EINCTD_Library()
        self.ccmObj = self.globalVarsObj.ccmObj        
        self.HistoryObj = History.EpicCallbacks()
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            if(self.HistoryObj.Verbose):
                self.wayPointDict = {
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ, 'PrintArguments'],
                    "WP_FTL_MTM_JB_VBA"                 : [self.WP_FTL_MTM_JB_VBA,'PrintArguments'],
                    "WP_MTM_WRITE_PART"                 : [self.WP_MTM_WRITE_PART,'PrintArguments'],     
                    "WP_FTL_XOR_STORE_PARITY_REQ"       : [self.WP_FTL_XOR_STORE_PARITY_REQ, 'PrintArguments'],
                    "WP_FWR_LOG_WRITE_LOG_COPY"         : [self.WP_FWR_LOG_WRITE_LOG_COPY,'PrintArguments'],     
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ,'PrintArguments'],
                    "WP_PS_REH_BES7"                    : [self.WP_PS_REH_BES7_Callback,'PrintArguments'],   
                    "WP_FTL_XOR_LOAD_PARITY_REQ"        : [self.WP_FTL_XOR_LOAD_PARITY_REQ,'PrintArguments'],
                    "WP_FTL_XOR_REBUILD_PARITY_REQ"     : [self.WP_FTL_XOR_REBUILD_PARITY_REQ_Callback, 'PrintArguments'],
                    "WP_FTL_READONLY_TRIGGER"           : [self.WP_FTL_READONLY_TRIGGER_Callback,'PrintArguments'],
                    "WP_LOG_GO_BACK_ONE_COPY"           : [self.WP_LOG_GO_BACK_ONE_COPY,'PrintArguments'], 
                    "WP_PS_XOR_RECOVERY_START"          : [self.WP_PS_XOR_RECOVERY_START, 'PrintArguments'],
                    "WP_LOG_GO_BACK_ONE_ENTRY"          : [self.WP_LOG_GO_BACK_ONE_ENTRY, 'PrintArguments'],
                    "WP_PS_REH_START"                   :['PrintArguments',self.WP_PS_REH_START_Callback],
                    "WP_PS_REH_RESULT"                  :['PrintArguments', self.WP_PS_REH_RESULT_Callback],
                    "WP_PS_REH_LDPC_ISR"                :['PrintArguments', self.WP_PS_REH_LDPC_ISR_Callback],
                    "WP_PS_REH_REREAD_WITH_CF"          :['PrintArguments', self.WP_PS_REH_REREAD_WITH_CF_Callback],
                    "WP_PS_REH_BES5"                    :['PrintArguments', self.WP_PS_REH_BES5_Callback],
                    "WP_PS_REH_BES7"                    :['PrintArguments', self.WP_PS_REH_BES7_Callback],
                    "WP_PS_DGM_BES"                     :['PrintArguments', self.WP_PS_DGM_BES_Callback]                    
                }
            else:
                self.wayPointDict = {
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ],
                    "WP_FTL_MTM_JB_VBA"                 : [self.WP_FTL_MTM_JB_VBA],
                    "WP_MTM_WRITE_PART"                 : [self.WP_MTM_WRITE_PART],     
                    "WP_FTL_XOR_STORE_PARITY_REQ"       : [self.WP_FTL_XOR_STORE_PARITY_REQ],
                    "WP_FWR_LOG_WRITE_LOG_COPY"         : [self.WP_FWR_LOG_WRITE_LOG_COPY],     
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ],
                    "WP_FTL_XOR_LOAD_PARITY_REQ"        : [self.WP_FTL_XOR_LOAD_PARITY_REQ],
                    "WP_FTL_XOR_REBUILD_PARITY_REQ"     : [self.WP_FTL_XOR_REBUILD_PARITY_REQ_Callback],
                    "WP_FTL_READONLY_TRIGGER"           : [self.WP_FTL_READONLY_TRIGGER_Callback],
                    "WP_LOG_GO_BACK_ONE_COPY"           : [self.WP_LOG_GO_BACK_ONE_COPY], 
                    "WP_PS_XOR_RECOVERY_START"          : [self.WP_PS_XOR_RECOVERY_START],
                    "WP_LOG_GO_BACK_ONE_ENTRY"          : [self.WP_LOG_GO_BACK_ONE_ENTRY],
                    "WP_PS_REH_START"                   :[self.WP_PS_REH_START_Callback],
                    "WP_PS_REH_RESULT"                  :[self.WP_PS_REH_RESULT_Callback],
                    "WP_PS_REH_LDPC_ISR"                :[self.WP_PS_REH_LDPC_ISR_Callback],
                    "WP_PS_REH_REREAD_WITH_CF"          :[self.WP_PS_REH_REREAD_WITH_CF_Callback],
                    "WP_PS_REH_BES5"                    :[self.WP_PS_REH_BES5_Callback],
                    "WP_PS_REH_BES7"                    :[self.WP_PS_REH_BES7_Callback],
                    "WP_PS_DGM_BES"                     :[self.WP_PS_DGM_BES_Callback]
                }
                
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)        
        
    def ErrorHandlerFunction(self,errorGroup, errorCode) :
        print( "\n!!!Callback received. Received error group : {0} error code : {1} " .format(errorGroup,errorCode))
        self.ReadError = True
    
    
    def WP_PS_REH_START_Callback(self,eventKeys, args, processorID):
        self.REHstarted = True
    
    def WP_PS_REH_RESULT_Callback(self,eventKeys, args, processorID):
        self.REHended = True
    
    def WP_PS_REH_LDPC_ISR_Callback(self,eventKeys, args, processorID):
        if(args[2] + args[4] != self.VBAtowhichErrorwasinjected ):
            self.VBAcheckIncorrect = True
            
    def WP_PS_REH_REREAD_WITH_CF_Callback(self,eventKeys, args, processorID):
        self.ReadRetryDone = True if(args[0] == 0) else False
        self.RechedReadRetry.append(args[1])
        if(self.MODE == 'SLC_ReadRetry'):
            self.errorInjObj.STMonWL(self.AddressBeforeCECCHandling, 'CMDP\\0_BER.stm')
        
    def WP_PS_REH_BES5_Callback(self,eventKeys, args, processorID):
        self.BES5Reached = True if(args[0] == 0) else False
        self.ReachedBES5.append(args[1])
    
    def WP_PS_DGM_BES_Callback(self,eventKeys, args, processorID):
        if(self.MODE == 'SLC_BES5' and args[2] == 1):
            self.errorInjObj.STMonWL(self.AddressBeforeCECCHandling, 'CMDP\\0_BER.stm')

        elif(self.MODE == 'SLC_BES7' and args[2] == 1):
            self.errorInjObj.STMonWL(self.AddressBeforeCECCHandling, 'CMDP\\BES7SB2_SecondSTM_1.8at_bes_coarse_level.stm')
            
        
    def WP_FWR_LOG_WRITE_LOG_COPY(self,eventKeys, args, processorID):
        try:
            if(args[0]==0):
                self.PrimaryLogBlock=True
                self.version += 1
            elif(args[0]==1):
                self.PrimaryLogBlock=False
        except:
            pass
        
    def WP_FTL_XOR_LOAD_PARITY_REQ(self,eventKey,args, pid):
        self.XorParityLoaded = True
    
    def WP_PS_XOR_RECOVERY_START(self,eventKey,args, pid):
        self.XorParityRecovery = True
        
    def WP_FTL_XOR_REBUILD_PARITY_REQ_Callback(self,eventKey,args, pid):
        self.ParityRebuilt = True
    
    def WP_LOG_GO_BACK_ONE_COPY(self,eventKeys, args, processorID):
        self.LogWentBackOneCopy = True
        
    def WP_PS_REH_BES7_Callback(self,eventKey,args, pid):
        self.CECCdetected = True
        self.BES7Reached = True if(args[0] == 0) else False
        self.ReachedBES7.append(args[1])        
        
    def WP_FTL_MTM_JB_VBA(self,eventKey,args, pid):
        self.MTMvbaWritten.append(args[1])       
        self.MTMjbWritten.append(args[0])
        
    def WP_FTL_READONLY_TRIGGER_Callback(self,eventKey,args, pid):
        self.CardinROmode = True
        
    def WP_MTM_WRITE_PART(self,eventKey,args, pid):
        self.MTMconsolidationHappened = True
        
    def WP_FTL_XOR_STORE_PARITY_REQ(self,eventKey,args, pid):
        #print("Args : XORM_Cb.activeXbid= %s , XORM_Cb.activeOpbid = %s , protectedJba.jumboBlockId = %s , opbXorJba.fmuInBlock = %s ,opbXorJba.jumboBlockId = %s , isSLC = %s , vba = %s"%(args[0],args[1],args[2],args[3],args[4],args[5],args[6]))                
        self.XorDumpHappened = True
        self.xor_paritystores.append(args)
        self.LatestProtectedJB = args[2]
        self.XORopb[self.LatestProtectedJB].append(args[-1])
    
    def WP_FWR_LOG_WRITE_REQ(self,eventKey,args, pid):
        self.LogDumpHappened = True    
        if(self.PrimaryLogBlock):
            self.LogJBIDdataPrimary.setdefault(self.version,[])
            self.LogJBIDdataPrimary[self.version].append([args[0],args[2]])
        else:
            self.LogJBIDdataSecondary.setdefault(self.version,[])
            self.LogJBIDdataSecondary[self.version].append([args[0],args[2]])        
    
    def WP_PS_PF_DETECTED(self,eventKey,args, pid):
        self.PFdetected = True
    
    def WP_LOG_GO_BACK_ONE_ENTRY(self,eventKeys, args, processorID):
        self.LogWentBackOneEntry = True    
    
    def WP_PS_BBM_PH_BLOCK_RELINK(self,eventKey,args, pid):
        if(args[4]== self.AddressBeforePFHandling['physicalblock'] and args[3]== self.AddressBeforePFHandling['plane']):
            self.RelinkingHappened = False
        else:
            self.RelinkingHappened = True
        
    def ResetVariables(self):
        self.CECCdetected = False
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
        self.XorParityLoaded = False
        self.ParityRebuilt = False
        self.CardinROmode = False
        self.Mode = 'Primary'
        self.LogWentBackOneCopy = False
        self.LogWentBackOneEntry = False
        self.LogJBIDbeforeShutdown = None
        self.LogJBIDAfterShutdown = None
        self.XorParityRecovery = False
        self.MODE = None
        self.ReadError = False
        self.ReadRetryDone = False
        self.BES5Reached = False
        self.BES7Reached = False
        
        #################
        self.ReachedBES7 = []
        self.ReachedBES5 = []
        self.RechedReadRetry = []
        #################
        
    def LogErrorModeChooser(self):
        modes = ['Secondary','Both'] #BOTH DISABLED AS THE TEST NEEDS TO RUN further
        self.Mode = random.choice(modes)
        self.logger.Info(self.globalVarsObj.TAG,'%s Mode chosen'%(self.Mode))
        if(self.Mode == 'Primary'):
            return [self.LogJBIDdataPrimary[self.version][-1][-1]]
        elif(self.Mode =='Secondary'):
            return [self.LogJBIDdataSecondary[self.version][-1][-1]]
        else:
            return [self.LogJBIDdataPrimary[self.version][-1][-1], self.LogJBIDdataSecondary[self.version][-1][-1]]
        
    def PFinjector(self,VBA):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1)        
        phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramError ,errorPersistence,0,1,0,0)
        self.livetObj.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, 'PF is injected to ',physical_address)
        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    def WritesToTriggerMTMWrites(self, startLba):
        txLen = random.choice([256, 512, 1024])
        self.ccmObj.Write(startLba, txLen)
        self.writtendata.append([startLba, txLen])
        return txLen
    
    def AllignedSequentialWrites(self,NoOfWrites):
        #Was getting consolidation at i= 9881
        currentLBA = 0
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
            
            self.writtendata.append([currentLBA, self.FMU])
            self.logger.Info(self.globalVarsObj.TAG, '%d : WRITE ON LBA %d of transfer length %d'%(writeNumber , currentLBA, self.FMU))
            currentLBA += (self.FMU + gapLeft + 1)
            
            
    def CECCHandlerXOR(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING XOR CECC HANDLER *************')
        self.GetMode(**kwargs)        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        

        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.AddressBeforeCECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
            self.errorInjObj.STMonCol(self.AddressBeforeCECCHandling, 'CMDP\\BES7SB2_FirstSTM_0.9at_default_level.stm')
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which CECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which CECC is injected :',self.AddressBeforeCECCHandling)
        
        else:
            #Trigger XOR Writes
            #########################
            while(not self.XorDumpHappened):
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(20 * Constants.MB / 512), txLenThreshold=None)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()            
                
            ########################        
            
            VBAtowhichErrorwasinjected = self.XORopb[self.LatestProtectedJB][-1]            #self.xor_paritystores[-1][-1] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.AddressBeforeCECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
            self.errorInjObj.STMonCol(self.AddressBeforeCECCHandling, 'CMDP\\BES7SB2_FirstSTM_0.9at_default_level.stm')
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which CECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which CECC is injected :',self.AddressBeforeCECCHandling)
        
        
        self.SDutilsObj.performShutdown(operation='UGSD')
        
        ReadRetryPBA = [self.sctputilsobj.TranslateVbaToDeVbaAndPba(vba, 1) for vba in self.RechedReadRetry]
        BES5PBA = [self.sctputilsobj.TranslateVbaToDeVbaAndPba(vba, 1) for vba in self.ReachedBES5]
        BES7PBA = [self.sctputilsobj.TranslateVbaToDeVbaAndPba(vba, 1) for vba in self.ReachedBES7]
        self.ReadRetryDone = self.AddressBeforeCECCHandling in ReadRetryPBA
        self.BES5Reached = self.AddressBeforeCECCHandling in BES5PBA
        self.BES7Reached = self.AddressBeforeCECCHandling in BES7PBA
        
        self.XorDumpHappened = False 
        while(not self.XorDumpHappened):
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()            
            
        
        if(self.MODE == 'SLC_ReadRetry'):
            if not(self.ReadRetryDone and not self.BES5Reached and not self.BES7Reached):
                self.logger.Info(self.globalVarsObj.TAG, "BES5/BES7 Waypoints triggered for read retry")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "BES5/BES7 Waypoints triggered for read retry"                    
            
        elif(self.MODE == 'SLC_BES5'):
            if not(self.ReadRetryDone and self.BES5Reached and not self.BES7Reached):
                self.logger.Info(self.globalVarsObj.TAG, "BES7 Waypoint triggered for BES5 Pass scenario")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "BES7 Waypoint triggered for BES5 Pass scenario"                  
            
        elif(self.MODE == 'SLC_BES7'):
            if not(self.ReadRetryDone and self.BES5Reached and self.BES7Reached and not self.ReadError):      
                self.logger.Info(self.globalVarsObj.TAG, "Read Error Triggered")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "Read Error Triggered" 

        
        self.logger.Info(self.globalVarsObj.TAG, "############ XOR CECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def CECCHandlerLOG(self, Blockstate, **kwargs):        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING LOG CECC HANDLER *************')
        self.GetMode(**kwargs)        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        

        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.AddressBeforeCECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.errorInjObj.STMonCol(self.AddressBeforeCECCHandling, 'CMDP\\BES7SB2_FirstSTM_0.9at_default_level.stm')
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which CECC is injected :',self.AddressBeforeCECCHandling)
        
        else:
            #Trigger LOG Writes
            #########################
            while(not self.LogDumpHappened):
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()            
                
            #Write Again To create Multiple Entries
            self.LogDumpHappened = False
            while(not self.LogDumpHappened):
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()            
                
            ########################        
            
            
            VBAarray = self.LogErrorModeChooser()
            
            for VBA in VBAarray:
                VBAtowhichErrorwasinjected = VBA
                self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
                self.AddressBeforeCECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
                self.errorInjObj.STMonCol(self.AddressBeforeCECCHandling, 'CMDP\\BES7SB2_FirstSTM_0.9at_default_level.stm')
                self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
                self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which CECC is injected :',self.AddressBeforeCECCHandling)
            
        
        if(not self.LogDumpHappened):
            self.logger.Info(self.globalVarsObj.TAG, 'Log Dump Didnt Happen')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False        
    
        if('ModeAfterSwitch' in kwargs.keys()):
            if(kwargs['ModeAfterSwitch'] != 'Operational'):
                if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.SDutilsObj.performShutdown(operation='GSD')
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="GSD") 
                else:
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")
                
        #Trigger LOG Writes
        #########################
        self.LogJBIDbeforeShutdown = self.LogJBIDdataSecondary[self.version][-1][0]
        self.LogDumpHappened = False 
        self.SDutilsObj.performShutdown("UGSD")
        self.LogJBIDAfterShutdown = self.LogJBIDdataSecondary[self.version][-1][0]
        ########################  
        
        ReadRetryPBA = [self.sctputilsobj.TranslateVbaToDeVbaAndPba(vba, 1) for vba in self.RechedReadRetry]
        BES5PBA = [self.sctputilsobj.TranslateVbaToDeVbaAndPba(vba, 1) for vba in self.ReachedBES5]
        BES7PBA = [self.sctputilsobj.TranslateVbaToDeVbaAndPba(vba, 1) for vba in self.ReachedBES7]
        self.ReadRetryDone = self.AddressBeforeCECCHandling in ReadRetryPBA
        self.BES5Reached = self.AddressBeforeCECCHandling in BES5PBA
        self.BES7Reached = self.AddressBeforeCECCHandling in BES7PBA
        
        if(self.MODE == 'SLC_ReadRetry'):
            if not(self.ReadRetryDone and not self.BES5Reached and not self.BES7Reached):
                self.logger.Info(self.globalVarsObj.TAG, "BES5/BES7 Waypoints triggered for read retry")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "BES5/BES7 Waypoints triggered for read retry"                    
            
        elif(self.MODE == 'SLC_BES5'):
            if not(self.ReadRetryDone and self.BES5Reached and not self.BES7Reached):
                self.logger.Info(self.globalVarsObj.TAG, "BES7 Waypoint triggered for BES5 Pass scenario")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "BES7 Waypoint triggered for BES5 Pass scenario"                  
            
        elif(self.MODE == 'SLC_BES7'):
            if not(self.ReadRetryDone and self.BES5Reached and self.BES7Reached and not self.ReadError):      
                self.logger.Info(self.globalVarsObj.TAG, "Read Error Triggered")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "Read Error Triggered"                  
            
        self.logger.Info(self.globalVarsObj.TAG, "############ LOG CECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def CECCHandlerMTM(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING MTM CECC HANDLER *************')
        self.GetMode(**kwargs)
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.PFinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforePFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection :',self.AddressBeforePFHandling)
        
        else:
            #Trigger MTM Writes
            startLba = 0
            #########################
            while(self.MTMvbaWritten == []):
                self.AllignedSequentialWrites(10000)
            ########################        
            
            VBAtowhichErrorwasinjected = self.MTMvbaWritten[-1]
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.AddressBeforeCECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
            self.errorInjObj.STMonWL(self.AddressBeforeCECCHandling, 'CMDP\\BES7SB2_FirstSTM_0.9at_default_level.stm')
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which CECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which CECC is injected :',self.AddressBeforeCECCHandling)
            
        
        if('ModeAfterSwitch' in kwargs.keys()):
            if(kwargs['ModeAfterSwitch'] != 'Operational'):
                if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.SDutilsObj.performShutdown(operation='GSD')
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="GSD") 
                else:
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")
                    
        #Trigger MTM Reads
        #########################
        for LBA, tlen in self.writtendata:
            self.ccmObj.Read(LBA, tlen)
        #########################
        
        
        if(self.MODE == 'SLC_ReadRetry'):
            if not(self.ReadRetryDone and not self.BES5Reached and not self.BES7Reached):
                self.logger.Info(self.globalVarsObj.TAG, "BES5/BES7 Waypoints triggered for read retry")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "BES5/BES7 Waypoints triggered for read retry"                    
            
        elif(self.MODE == 'SLC_BES5'):
            if not(self.ReadRetryDone and self.BES5Reached and not self.BES7Reached):
                self.logger.Info(self.globalVarsObj.TAG, "BES7 Waypoint triggered for BES5 Pass scenario")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "BES7 Waypoint triggered for BES5 Pass scenario"                  
            
        elif(self.MODE == 'SLC_BES7'):
            if not(self.ReadRetryDone and self.BES5Reached and self.BES7Reached and not self.ReadError):      
                self.logger.Info(self.globalVarsObj.TAG, "Read Error Triggered")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "Read Error Triggered"     
        

        self.logger.Info(self.globalVarsObj.TAG, "############ MTM CECC handling SUCCESSFULL###############")

        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    
       
        
        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
    
    def GetMode(self, **kwargs):
        self.MODE = kwargs['combination_']['ErrorType']
        
        