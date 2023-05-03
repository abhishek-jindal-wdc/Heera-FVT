import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
from collections import defaultdict
import SDExpressWrapper as SDExWrap
import CTFServiceWrapper as ServiceWrap
import CMDP.CMDP_History as History
import NVMeCMDWrapper as NVMeWrap

WriteAbortDetected = False

def OnWriteAbort(package, addr):
    """
    Write Abort callback function
    Arguments: 
    """
    global WriteAbortDetected
    WriteAbortDetected = True
    print('DETECTED WRITE ABORT')

class WAhandler:
    
    __staticWAObj = None

    ##
    # @brief A method to create a singleton object of LOG WA HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not WAhandler.__staticWAObj:
            WAhandler.__staticWAObj = super(WAhandler,cls).__new__(cls, *args, **kwargs)

        return WAhandler.__staticWAObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = GlobalVars.GlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.SDutilsObj = SDUtils.SDUtils
        self.livetObj.UnregisterLivetCallback(self.livetObj.lcFlashProgramAbort)        
        self.livetObj.RegisterLivetCallback(self.livetObj.lcFlashProgramAbort, OnWriteAbort)                        
        self.HistoryObj = History.EpicCallbacks()
        
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            if(self.HistoryObj.Verbose):
                self.wayPointDict = {
                    "WP_PS_BBM_PH_BLOCK_RELINK"         : [self.WP_PS_BBM_PH_BLOCK_RELINK, 'PrintArguments'], 
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ, 'PrintArguments'],
                    "WP_FTL_MTM_JB_VBA"                 : [self.WP_FTL_MTM_JB_VBA,'PrintArguments'],
                    "WP_MTM_WRITE_PART"                 : [self.WP_MTM_WRITE_PART,'PrintArguments'],     
                    "WP_FTL_XOR_STORE_PARITY_REQ"       : [self.WP_FTL_XOR_STORE_PARITY_REQ, 'PrintArguments'],
                    "WP_FWR_LOG_WRITE_LOG_COPY"         : [self.WP_FWR_LOG_WRITE_LOG_COPY,'PrintArguments'],     
                    "WP_FTL_BML_PARTIAL_BLOCK_ADDED"    : [self.WP_FTL_BML_PARTIAL_BLOCK_ADDED_Callback, 'PrintArguments'],
                    "WP_MNT_PERFORM_BRLC"               : [self.WP_MNT_PERFORM_BRLC, 'PrintArguments']
                    
                }
            else:
                self.wayPointDict = {
                    "WP_PS_BBM_PH_BLOCK_RELINK"         : [self.WP_PS_BBM_PH_BLOCK_RELINK], 
                    "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ],
                    "WP_FTL_MTM_JB_VBA"                 : [self.WP_FTL_MTM_JB_VBA],
                    "WP_MTM_WRITE_PART"                 : [self.WP_MTM_WRITE_PART],     
                    "WP_FTL_XOR_STORE_PARITY_REQ"       : [self.WP_FTL_XOR_STORE_PARITY_REQ],
                    "WP_FWR_LOG_WRITE_LOG_COPY"         : [self.WP_FWR_LOG_WRITE_LOG_COPY],     
                    "WP_FTL_BML_PARTIAL_BLOCK_ADDED"    : [self.WP_FTL_BML_PARTIAL_BLOCK_ADDED_Callback],
                    "WP_MNT_PERFORM_BRLC"               : [self.WP_MNT_PERFORM_BRLC]
                    
                }
                
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        #self.errorManager = self.globalVarsObj.nvmeSession.GetErrorManager()
        #self.errorManager.RegisterCallback(self.ErrorHandlerFunction)
        
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)        
    
    def WAinjector_on_physical_location_log(self,VBA):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1)   
        if(physical_address['channel'] == 1):
            if(physical_address['die'] == 1):
                if(physical_address['stringnumber'] == 3):
                    physical_address['wordline'] += 1
                    physical_address['plane'] = 0
                    physical_address['stringnumber'] == 0
                else:
                    physical_address['stringnumber']+=1
                physical_address['die'] = 0
            elif(self.globalVarsObj.DeviceParameters.No_of_dies > 1):
                physical_address['die'] = 1
            physical_address['channel'] = 0
        else:
            physical_address['channel'] = 0
                

        phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]            
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        self.livetObj.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, 'WA is injected to ',physical_address)
        
        
    def WAinjector_on_physical_location(self,VBA):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1)   
        if(physical_address['channel'] == 1):
            if(physical_address['die'] == 1):
                if(physical_address['stringnumber'] == 3):
                    if(physical_address['plane'] == 1):
                        physical_address['wordline'] += 1
                        physical_address['plane'] = 0
                    else:
                        physical_address['plane'] = 1
                    physical_address['stringnumber'] == 0
                else:
                    physical_address['stringnumber']+=1
                physical_address['die'] = 0
            elif(self.globalVarsObj.DeviceParameters.No_of_dies > 1):
                physical_address['die'] = 1
            physical_address['channel'] = 0
        else:
            physical_address['channel'] = 0
                

        phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]            
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        self.livetObj.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, 'WA is injected to ',physical_address)

        
    def ErrorHandlerFunction(self,statusCodeType,statusCode):	
        self.logger.Info(self.globalVarsObj.TAG, "Callback received with received status code: %d and status code type: %d"%(statusCode,statusCodeType))       
        if((WriteAbortDetected or (statusCode == 144) or (statusCode == 5)) and not self.AlreadySwitched):
            self.errorManager.ClearAllErrors() 
            self.AlreadySwitched = True
            self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762                            
            if(self.vtfContainer.activeProtocol == 'SD_OF_SDPCIe'):
                pass
            else:
                ulActivateControllerTimeOut = 0
                retTuple = self.globalVarsObj.configParser.GetValue("activate_controller_time_out", ulActivateControllerTimeOut)
                ulActivateControllerTimeOut = retTuple[0]             
                ObjNVMeActivateCtlr = NVMeWrap.ActivateCntrlrCMD(False, False, False, True, ulActivateControllerTimeOut)
                ObjNVMeActivateCtlr.Execute()
                ObjNVMeActivateCtlr.HandleOverlappedExecute()
                ObjNVMeActivateCtlr.HandleAndParseResponse()                
        else:
            self.errorManager.ClearAllErrors() 
                
    def WP_FWR_LOG_WRITE_LOG_COPY(self,eventKeys, args, processorID):
        try:
            if(args[0]==0):
                self.PrimaryLogBlock=True
                self.version += 1
            elif(args[0]==1):
                self.PrimaryLogBlock=False
        except:
            pass
    
    def WP_MNT_PERFORM_BRLC(self,eventKey,args, pid):
        self.BRLCperformed = True
        
        
    def WP_FTL_BML_PARTIAL_BLOCK_ADDED_Callback(self,eventKey,args, pid):
        #partialItem_p->partialJBA.jumboBlockId, ptnId, partialListType,SAT_VCGetVC(partialItem_p->partialJBA), partialItem_p->partialAddReason
        
        self.BlockAddedToPartialList = True
        self.BlockWhichWasAddedToPartialBlock = args[0]
        
        
    def WP_FTL_MTM_JB_VBA(self,eventKey,args, pid):
        self.MTMvbaWritten.append(args[1])       
        self.MTMjbWritten.append(args[0])
        
    
    def WP_MTM_WRITE_PART(self,eventKey,args, pid):
        self.MTMconsolidationHappened = True
        
    def WP_FTL_XOR_STORE_PARITY_REQ(self,eventKey,args, pid):
        #print("Args : XORM_Cb.activeXbid= %s , XORM_Cb.activeOpbid = %s , protectedJba.jumboBlockId = %s , opbXorJba.fmuInBlock = %s ,opbXorJba.jumboBlockId = %s , isSLC = %s , vba = %s"%(args[0],args[1],args[2],args[3],args[4],args[5],args[6]))                
        self.XorDumpHappened = True
        self.xor_paritystores.append(args)
        self.LatestProtectedJB = args[2]
        self.LatestXORJB = args[4]
        self.XORopb[self.LatestProtectedJB].append(args[-1])
    
    def WP_FWR_LOG_WRITE_REQ(self,eventKey,args, pid):
        self.LogDumpHappened = True    
        if(self.PrimaryLogBlock):
            self.LogJBIDdataPrimary.setdefault(self.version,[])
            self.LogJBIDdataPrimary[self.version].append([args[0],args[2]])
        else:
            self.LogJBIDdataSecondary.setdefault(self.version,[])
            self.LogJBIDdataSecondary[self.version].append([args[0],args[2]])        
    
    
    def WP_PS_BBM_PH_BLOCK_RELINK(self,eventKey,args, pid):
        pass
    
    def ResetVariables(self):
        global WriteAbortDetected
        WriteAbortDetected = False
        
        self.JBBeforeWAHandling = False
        self.JBAfterWAHandling = False
        self.LatestXORJB = False
        self.BlockAddedToPartialList = False
        self.writtendata = []
        self.WAdetected = False
        self.XorDumpHappened = False
        self.RelinkingnotHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterWAHandling = None
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
        self.AlreadySwitched = False
        self.SetSwitchDuringAbort(setFlag=1)
        self.BRLCperformed = False
    
    def SimpleSequentialWrites(self, LBA):
        self.globalVarsObj.ccmObj.Write(LBA, 1024)
        if(self.vtfContainer.activeProtocol == 'NVMe_OF_SDPCIe'):
            self.globalVarsObj.ccmObj.DoFlushCache()
        return LBA+1024
        
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
            
            try: 
                self.globalVarsObj.ccmObj.Write(currentLBA, self.FMU)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()
            except:
                self.errorManager.ClearAllErrors() 

            self.logger.Info(self.globalVarsObj.TAG, '%d : WRITE ON LBA %d of transfer length %d'%(writeNumber , currentLBA, self.FMU))
            currentLBA += (self.FMU + gapLeft + 1)
        self.HistoryObj.HistoryObj.LastWrittenLBA = currentLBA
            
    def SetSwitchDuringAbort(self, setFlag = 0):
        self.globalVarsObj.configParser.SetValue("Switch_protocol_after_abort", setFlag)
    
    def WAinjector(self,VBA):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1)        
        phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        self.livetObj.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, 'WA is injected to ',physical_address)
        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    def WAHandlerXOR(self, Blockstate, **kwargs):
        global WriteAbortDetected     
        self.DeregisterAllWaypoint()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        self.SetSwitchDuringAbort(setFlag=1)
        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING XOR WA HANDLER *************')
        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
            
        else:
            #Trigger XOR Writes
            #########################
            currentLBA = self.globalVarsObj.startLba            
            while(not self.XorDumpHappened):
                try:
                    #self.cmdpAPLib.DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
                    currentLBA = self.SimpleSequentialWrites(currentLBA)
                except:
                    print()
            ########################        
            
            VBAtowhichErrorwasinjected = self.XORopb[self.LatestProtectedJB][-1] + 16           #self.xor_paritystores[-1][-1] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection : {}'.format(str(self.AddressBeforeWAHandling)))
            self.JBBeforeWAHandling = self.LatestXORJB
            self.logger.Info(self.globalVarsObj.TAG, 'XOR JB before WA Detection : {}'.format(str(self.JBBeforeWAHandling)))            
            
            
        self.XorDumpHappened = False 
        while(not self.XorDumpHappened):
            #self.cmdpAPLib.DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
            try:
                currentLBA = self.SimpleSequentialWrites(currentLBA)
            except:
                self.errorManager.ClearAllErrors() 
        
        self.XorDumpHappened = False 
        while(not self.XorDumpHappened):
            currentLBA = self.SimpleSequentialWrites(currentLBA)

        
        if(not self.XorDumpHappened):
            self.logger.Info(self.globalVarsObj.TAG, 'Xor Dump Didnt Happen')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'Xor Dump Didnt Happen'
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "XOR WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "XOR WA wasn't detected"
              
        
        self.JBAfterWAHandling = self.LatestXORJB
        self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
        self.logger.Info(self.globalVarsObj.TAG, 'XOR JB before WA Detection : {}'.format(str(self.JBBeforeWAHandling)))            
        self.logger.Info(self.globalVarsObj.TAG, 'XOR JB After WA Detection : {}'.format(str(self.JBAfterWAHandling)))            
                
        if(self.JBAfterWAHandling == self.JBBeforeWAHandling and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "XOR Block Wasn't added to partial List")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "XOR Block Wasn't added to partial List"             
        
        if(not self.BRLCperformed and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC didnt happen in nvme mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC didnt happen in nvme mode"  
        
        if(self.BRLCperformed and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC Happened in SD mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC Happened in SD mode" 
        
        self.logger.Info(self.globalVarsObj.TAG, "############ XOR WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def WAinjectionLOG(self):
        #self.globalVarsObj.sctpUtilsObj.ErrorInjection(binType="logWriteFTLRamdomDPA")
        self.sctputilsobj.ErrorInjection(subOpcode=0, configType="singleError", operationType="Prog", addrType="OPBID", addr=4, nsid=1, pattern="WA", dataBuffer=None, binType=None, ErrLog=1, MBrevive=1, JBrevive=1, SurvivePC=1, isE2E=0, slot1=[0,0,0,0])
        
    def WAHandlerLOG(self, Blockstate, **kwargs):
        self.SetSwitchDuringAbort(setFlag=1)
        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING LOG WA HANDLER *************')
        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection : {}'.format(str(self.AddressBeforeWAHandling)))
        
        else:
            #Trigger LOG Writes
            #########################
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
            ########################        
            
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
                
            self.WAinjectionLOG()
            
        #Trigger LOG Writes
        #########################
        try:
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(50 * Constants.MB / 512), txLenThreshold=None)
        except:
            self.ErrorHandlerFunction(0,144)            
        ########################  

                  
                
        self.logger.Info(self.globalVarsObj.TAG, "############ LOG WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def WAHandlerMTM(self, Blockstate, **kwargs):
        global WriteAbortDetected     
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)                
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING MTM WA HANDLER *************')
        
        if('ErrorVBA' in kwargs.keys()):
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection : {}'.format(str(self.AddressBeforeWAHandling)))
        
        else:
            #Trigger MTM Writes
            #########################
            while(self.MTMvbaWritten == []):
                #self.cmdpAPLib.DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(45 * Constants.MB / 512), txLenThreshold=None)
                self.AllignedSequentialWrites(10000)
            ########################        
            
            VBAtowhichErrorwasinjected = self.MTMvbaWritten[-1]  + 16
            
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                VBAtowhichErrorwasinjected += 32
                
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection : {}'.format(str(self.AddressBeforeWAHandling)))
            self.JBBeforeWAHandling = self.MTMjbWritten[-1]
            self.logger.Info(self.globalVarsObj.TAG, 'MTM JB before WA Detection : {}'.format(str(self.JBBeforeWAHandling)))    
            
        #Trigger MTM Writes
        #########################
        self.MTMvbaWritten = []
        while(self.MTMvbaWritten == []):
            #self.cmdpAPLib.DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten= int(45 * Constants.MB / 512), txLenThreshold=None)
            self.AllignedSequentialWrites(10000)
        ######################## 
        
        
        if(not self.MTMconsolidationHappened):
            self.logger.Info(self.globalVarsObj.TAG, 'MTM Consolidation Didnt Happen')
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return 'MTM Consolidation Didnt Happen'
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "MTM WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "MTM WA wasn't detected"
                
        if(not self.BRLCperformed and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC didnt happen in nvme mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC didnt happen in nvme mode"  
        
        if(self.BRLCperformed and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC Happened in SD mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC Happened in SD mode" 
        
        
        self.JBAfterWAHandling = self.MTMjbWritten[-1]
        self.logger.Info(self.globalVarsObj.TAG, 'MTM JB After WA Detection : {}'.format(str(self.JBAfterWAHandling)))
        
        if(self.JBAfterWAHandling == self.JBBeforeWAHandling and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "MTM Block Wasn't added to partial List")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "MTM Block Wasn't added to partial List"          

        
        self.logger.Info(self.globalVarsObj.TAG, "############ MTM WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    
       
        
        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
