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
import SDCommandWrapper as SDWrapper
import os
import Lib.FWStructs.FWObjectWrapper as fwWrap

class UECChandler:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not UECChandler.__staticPFObj:
            UECChandler.__staticPFObj = super(UECChandler,cls).__new__(cls, *args, **kwargs)

        return UECChandler.__staticPFObj

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
                    "WP_LOG_GO_BACK_ONE_ENTRY"          : [self.WP_LOG_GO_BACK_ONE_ENTRY, 'PrintArguments']
                }
            else:
                self.wayPointDict = {
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ],
                    "WP_FTL_MTM_JB_VBA"                 : [self.WP_FTL_MTM_JB_VBA],
                    "WP_MTM_WRITE_PART"                 : [self.WP_MTM_WRITE_PART],     
                    "WP_FTL_XOR_STORE_PARITY_REQ"       : [self.WP_FTL_XOR_STORE_PARITY_REQ],
                    "WP_FWR_LOG_WRITE_LOG_COPY"         : [self.WP_FWR_LOG_WRITE_LOG_COPY],     
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ],
                    "WP_PS_REH_BES7"                    : [self.WP_PS_REH_BES7_Callback],   
                    "WP_FTL_XOR_LOAD_PARITY_REQ"        : [self.WP_FTL_XOR_LOAD_PARITY_REQ],
                    "WP_FTL_XOR_REBUILD_PARITY_REQ"     : [self.WP_FTL_XOR_REBUILD_PARITY_REQ_Callback],
                    "WP_FTL_READONLY_TRIGGER"           : [self.WP_FTL_READONLY_TRIGGER_Callback],
                    "WP_LOG_GO_BACK_ONE_COPY"           : [self.WP_LOG_GO_BACK_ONE_COPY], 
                    "WP_PS_XOR_RECOVERY_START"          : [self.WP_PS_XOR_RECOVERY_START],
                    "WP_LOG_GO_BACK_ONE_ENTRY"          : [self.WP_LOG_GO_BACK_ONE_ENTRY]                    
                }
                
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)        
        
    def ErrorHandlerFunction(self,errorGroup, errorCode) :
        print( "\n!!!Callback received. Received error group : {0} error code : {1} " .format(errorGroup,errorCode))
        if(errorGroup==65291 and errorCode==11):
            self.errorManager.ClearAllErrors()  
    
        if(errorGroup==65338 and errorCode==2097152):
            self.errorManager.ClearAllErrors()     
    
        if(errorGroup==65338 and errorCode==524288):
            self.errorManager.ClearAllErrors() 
    
        if(errorGroup==2 and errorCode==129):
            self.errorManager.ClearAllErrors()    
        
        if(errorCode == 130):
            self.CardinROmode =True
        
        if(errorCode == 1<< 19):
            self.isGeneralErrorSet = True
            
        
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
        self.UECCdetected = True
    
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
        self.UECCdetected = False
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
        self.isGeneralErrorSet = False
    
    def LogErrorModeChooser(self):
        modes = ['Primary','Secondary','Both'] #BOTH DISABLED AS THE TEST NEEDS TO RUN further
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
                    
            try: 
                self.globalVarsObj.ccmObj.Write(currentLBA, self.FMU)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()
            except:
                self.errorManager.ClearAllErrors() 
                
            self.writtendata.append([currentLBA, self.FMU])
            self.logger.Info(self.globalVarsObj.TAG, '%d : WRITE ON LBA %d of transfer length %d'%(writeNumber , currentLBA, self.FMU))
            currentLBA += (self.FMU + gapLeft + 1)
            
            
    def UECCHandlerXOR(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING XOR UECC HANDLER *************')
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        

        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
            self.errorInjObj.InjectUECC(self.AddressBeforeUECCHandling)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
        
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
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
            self.errorInjObj.InjectUECC(self.AddressBeforeUECCHandling)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
        
        
        if('ModeAfterSwitch' in kwargs.keys()):
                if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.SDutilsObj.performShutdown(operation='GSD')
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="ABORT") 
                else:
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")        
    
        self.XorDumpHappened = False 
        while(not self.XorDumpHappened):
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()            

        
        if(not self.XorDumpHappened):
            self.logger.Info(self.globalVarsObj.TAG, 'Xor Dump Didnt Happen')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'Xor Dump Didnt Happen'
        
        if(not self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "UECC wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "UECC wasn't detected"
        
        if(self.CardinROmode):
            self.logger.Info(self.globalVarsObj.TAG, "Card Went To RO mode.. Shouldn't go")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "Card Went To RO mode.. Shouldn't go"            
        
        if(not self.ParityRebuilt):
            self.logger.Info(self.globalVarsObj.TAG, "XOR Parity Wasn't rebuilt")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "XOR Parity Wasn't rebuilt"        
        

        
        self.logger.Info(self.globalVarsObj.TAG, "############ XOR UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def UECCHandlerLOG(self, Blockstate, **kwargs):        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING LOG UECC HANDLER *************')
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        

        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.errorInjObj.InjectUECC(self.AddressBeforeUECCHandling)            
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
        
        else:
            #Trigger LOG Writes
            #########################
            while(not self.LogDumpHappened):
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
            
            #Write Again To create Multiple Entries
            self.LogDumpHappened = False
            while(not self.LogDumpHappened):
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
            
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.ccmObj.DoFlushCache()
            ########################        
            
            
            VBAarray = self.LogErrorModeChooser()
            
            for VBA in VBAarray:
                VBAtowhichErrorwasinjected = VBA
                self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
                self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
                self.errorInjObj.InjectUECConCol(self.AddressBeforeUECCHandling)            
                self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
                self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
            
        
        if(not self.LogDumpHappened):
            self.logger.Info(self.globalVarsObj.TAG, 'Log Dump Didnt Happen')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'Log Dump Didnt Happen'        
    
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
        
        if(not self.LogWentBackOneCopy and self.Mode != 'Primary'):
            self.logger.Info(self.globalVarsObj.TAG, 'Log Didnt go back One Copy Even when Secondary is corrupt')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'Log Didnt go back One Copy Even when Secondary is corrupt'      
        
        if(self.LogWentBackOneCopy and self.Mode == 'Primary'):
            self.logger.Info(self.globalVarsObj.TAG, 'Log went back One Copy Even when Primary is corrupt, has to pick from secondary')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'Log went back One Copy Even when Primary is corrupt, has to pick from secondary'      
        
        #if(self.LogJBIDAfterShutdown == self.LogJBIDbeforeShutdown):
            #self.logger.Info(self.globalVarsObj.TAG, 'Log Block is written to same JB after UGSD')
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.DeregisterAllWaypoint()
            #return False    
        
        if(self.Mode == 'Both' and not self.LogWentBackOneEntry):
            self.logger.Info(self.globalVarsObj.TAG, 'Log Didnt go back One Entry Even After Corruption of Active log')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'Log Didnt go back One Entry Even After Corruption of Active log'            
            
        self.logger.Info(self.globalVarsObj.TAG, "############ LOG UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def CheckForGeneralError(self):   
        if self.isGeneralErrorSet == False:
            # Send CMD13 and check status
            cmdObj = SDWrapper.SendStatus(uiRCA = 0xD555, bSendTaskStatus = bool(0))
            if cmdObj.pyResponseData.r1Response.uiCardStatus & (1<<19) != (1<<19):
                return False
            if cmdObj.pyResponseData.r1Response.uiCardStatus & SDWrapper.STATUS_CODE_CURRENT_STATE_TRAN_S_X != SDWrapper.STATUS_CODE_CURRENT_STATE_TRAN_S_X:
                return False
            return True
            
    def UECCHandlerMTM(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING MTM UECC HANDLER *************')

        self.stats = self.sctputilsobj.GetErrorHandlingStatistics()
        self.sctpParsedObj_bef = fwWrap.FWDiagCustomObject(self.stats, "EH_ErrorCounterXML_s").EH_ErrorCounterXML_s.PS0.__dict__
        UECCcounterAtStart = self.sctpParsedObj_bef['entryToUECCList']

        #Trigger MTM Writes
        startLba = 0
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
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="GSD") 
                else:
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")

        self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762
        dataBuffer = pyWrap.Buffer.CreateBuffer(4096, patternType=pyWrap.ALL_0, isSector=False)        
        filename = os.path.join(os.getenv("FVTPATH"),"ValidationLib",'EI_files','Rnd15sXORMTM.bin')
        dataBuffer.FillFromFile(filename,True)
        start_offset = 0x150 + 16 + 1
        for i in range(40):
            dataBuffer.SetByte(start_offset,0)
            start_offset += 72


        self.sctputilsobj.ErrorInjectionOnlyBuffer(dataBuffer = dataBuffer)

        #Trigger MTM Reads
        #########################
        for LBA, tlen in self.writtendata:
            self.ccmObj.Read(LBA, tlen)
            self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762            
        #########################

        self.stats = self.sctputilsobj.GetErrorHandlingStatistics()
        self.sctpParsedObj = fwWrap.FWDiagCustomObject(self.stats, "EH_ErrorCounterXML_s").EH_ErrorCounterXML_s.PS0.__dict__

        if(self.sctpParsedObj['entryToUECCList'] == UECCcounterAtStart):
            self.logger.Info(self.globalVarsObj.TAG, "MTM UECC not detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            return "MTM UECC not detected"                

        
        if(not self.MTMconsolidationHappened):
            self.logger.Info(self.globalVarsObj.TAG, 'MTM Consolidation Didnt Happen')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'MTM Consolidation Didnt Happen'
        
        if(self.CardinROmode and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "Card Went To RO mode.. Shouldn't go")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "Card Went To RO mode.. Shouldn't go"            
        
        
        if(not self.CardinROmode and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "Card Didnt go To RO mode.. Should go")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "Card Didnt go To RO mode.. Should go"        
        
        if(not self.XorParityRecovery and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "XOR recovery not started in NVMe mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "XOR recovery not started in NVMe mode"            
        
        
        if(self.XorParityRecovery and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "XOR recovery started in SD mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "XOR recovery started in SD mode"      
        
        if(not self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "UECC wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "UECC wasn't detected"       
        
        if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe" and self.CheckForGeneralError()):
            self.logger.Info(self.globalVarsObj.TAG, "General Error set")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "General Error set"       
            
        
        if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
            SDWrapper.SetTimeoutCallback(True)   
            self.vtfContainer.switchProtocol()
            self.vtfContainer.DoProduction(security_production=False)
            self.ccmObj.Format(SES=1)
        
        self.logger.Info(self.globalVarsObj.TAG, "############ MTM UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
        
        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
