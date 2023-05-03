import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
import random
import CMDP.EINCTD_Library as CMDP_AP_Lib
import NVMeCMDWrapper as NVMeWrap
import CMDP.CMDP_History as History

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
        self.cmdpAPLib = CMDP_AP_Lib.EINCTD_Library()
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba        
        self.livetObj.UnregisterLivetCallback(self.livetObj.lcFlashProgramAbort)        
        self.livetObj.RegisterLivetCallback(self.livetObj.lcFlashProgramAbort, OnWriteAbort)                        
        self.HistoryObj = History.EpicCallbacks()
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            self.wayPointDict = {
                "WP_PS_BBM_PH_BLOCK_RELINK"         : [self.WP_PS_BBM_PH_BLOCK_RELINK], 
                "WP_FTL_HWD_WRITE_JB_VBA"           : [self.WP_FTL_HWD_WRITE_JB_VBA],
                "WP_FTL_RLC_WRITE_JB_VBA"           : [self.WP_FTL_RLC_WRITE_JB_VBA],
                "WP_FTL_BML_PARTIAL_BLOCK_ADDED"    : [self.WP_FTL_BML_PARTIAL_BLOCK_ADDED],
                "WP_PS_OTG_PROG_FLASH_ADDR"         : [self.WP_PS_OTG_PROG_FLASH_ADDR],
                "WP_MNT_PERFORM_BRLC"               : [self.WP_MNT_PERFORM_BRLC]
            }
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)          
    
    def ErrorHandlerFunction(self,statusCodeType,statusCode):	
        self.logger.Info(self.globalVarsObj.TAG, "Callback received with received status code: %d and status code type: %d"%(statusCode,statusCodeType))       
        if(self.AlreadySwitched):
            self.errorManager.ClearAllErrors()
            return 
        
        if(WriteAbortDetected or (statusCode == 144) or (statusCode == 5) or self.FromTLC2TLCrelocation):
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
    
    def WP_MNT_PERFORM_BRLC(self,eventKey,args, pid) :
        self.BRLChappended = True
        
    def WP_PS_OTG_PROG_FLASH_ADDR(self,eventKey,args, pid):
        if(args[1] == 1 and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.TLCvbaWritten.append(args[0])
            
    def WP_FTL_BML_PARTIAL_BLOCK_ADDED(self,eventKey,args, pid):
        #partialItem_p->partialJBA.jumboBlockId, ptnId, partialListType,SAT_VCGetVC(partialItem_p->partialJBA), partialItem_p->partialAddReason
        
        self.BlockAddedToPartialList = True
        self.BlockWhichWasAddedToPartialBlock = args[0]
        
        
    def InjectErrorFromWP(self,vba,die,plane,block,wl,string,channel):
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        package = channel
        phyAddress=[die,plane,block,wl,string,0,0]            
        self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)
        self.logger.Info(self.globalVarsObj.TAG, "Injected Write Abort on VBA: %d"% (vba))
        self.logger.Info(self.globalVarsObj.TAG, "Physical Address -> Die: %d, Plane: %d, PhysicalBlock: %d, Wordline: %d, String: %d" \
                         % (die,plane,block,wl,string))
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)        
            
    def WP_FTL_RLC_WRITE_JB_VBA(self,eventKey,args, pid):
        self.TLCvbaWritten.append(args[1])       
        self.TLCjbWritten.append(args[0])
        
    def WP_FTL_HWD_WRITE_JB_VBA(self,eventKey,args, pid):
        self.SLCvbaWritten.append(args[1])       
        self.SLCjbWritten.append(args[0])
       
    def WP_PS_WA_DETECTED(self,eventKey,args, pid):
        self.WAdetected = True
    
    def WP_PS_BBM_PH_BLOCK_RELINK(self,eventKey,args, pid):
        if(args[4]== self.AddressBeforeWAHandling['physicalblock'] and args[3]== self.AddressBeforeWAHandling['plane']):
            self.RelinkingnotHappened = False
        else:
            self.RelinkingHappened = True
    
    def WAinjector(self,VBA, blocktype=0):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1, blockType=blocktype)    
        VBA |= 32768
        self.sctputilsobj.ErrorInjection(subOpcode=0, configType="singleError", operationType="Prog", addrType="VBA", addr=VBA, nsid=1, pattern="WA", dataBuffer=None, binType=None, ErrLog=1, MBrevive=1, JBrevive=1, SurvivePC=1, isE2E=0, slot1=[0,0,0,0])
        self.logger.Info(self.globalVarsObj.TAG, 'WA is injected to {}'.format(str(physical_address)))                
    
    def ResetVariables(self):
        global WriteAbortDetected
        WriteAbortDetected = False
        self.BRLChappended = False
        self.JBBeforeWAHandling = False
        self.JBAfterWAHandling = False
        self.BlockWhichWasAddedToPartialBlock = None
        self.BlockAddedToPartialList = False
        self.writtendata = []
        self.AlreadySwitched = False
        self.WAdetected = False
        self.RelinkingHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterWAHandling = None
        self.AddressBeforeWAHandling = None
        self.SLCvbaWritten = []
        self.SLCjbWritten = []
        self.TLCvbaWritten = []
        self.TLCjbWritten = []   
        self.FromTLC2TLCrelocation = False
        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    def GetLastWrittenAddress(self):
        LBA, tlen = self.HistoryObj.HistoryObj.GlobalWriteData[-1]
        
        self.globalVarsObj.ccmObj.Read(startLba = LBA, txLen= tlen)
        self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762
        
        #LBA = LBA + tlen - 1
        BLOCKDICT  = self.sctputilsobj.LBA2VBA(LBA, returnDict= True)
        PBA =  self.sctputilsobj.TranslateVbaToDeVbaAndPba(BLOCKDICT['vba'], 1, blockType=BLOCKDICT['blockType'])
        PBA['VBA'] = BLOCKDICT['vba']
        return PBA        
        
                
    def WAHandlerSLC(self, Blockstate, **kwargs):

        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST SLC WA HANDLER *************')
        
        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
        
        else:
            #Trigger Host Writes
            #Pre WA write
            #########################
            #self.writtendata = writeTotriggerHostAccumulation()
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)
            # Write a random number of JB
            
            ########################
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
            
            
            VBAtowhichErrorwasinjected = self.GetLastWrittenAddress()['VBA']  + 16
            self.WAinjector(VBAtowhichErrorwasinjected)
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
            self.JBBeforeWAHandling = self.SLCjbWritten[-1]
            self.logger.Info(self.globalVarsObj.TAG, 'SLC JB before WA Detection :',self.JBBeforeWAHandling)            
            
        #########################
        #WA detection Write
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=5000, txLenThreshold=None)
        ########################
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            try:
                self.globalVarsObj.ccmObj.DoFlushCache()
            except:
                self.ErrorHandlerFunction(0,144)

        
        self.JBAfterWAHandling = self.SLCjbWritten[-1]
        self.logger.Info(self.globalVarsObj.TAG, 'SLC JB After WA Detection :',self.JBAfterWAHandling)
        
        if(not self.AlreadySwitched):
            self.logger.Info(self.globalVarsObj.TAG, "SLC Write Abort wasnt detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            return "SLC Write Abort wasnt detected"            
            
        self.logger.Info(self.globalVarsObj.TAG, "############ Host SLC handling SUCCESSFULL###############")
        self.ResetVariables()
        return True        
    
    
    def WAHandlerTLC(self, Blockstate, **kwargs):
        global WriteAbortDetected                        
        startLba = 0
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC WA HANDLER *************')
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)   
        
        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
            self.FromTLC2TLCrelocation = True            
        else:
            startLba = 0
        
        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 48
            
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
        
        else:
            #Trigger Host Writes
            #########################
            self.sctputilsobj.SetMvpThreshold(-10,-15)
            self.TLCvbaWritten = []
            while(self.TLCvbaWritten == []):            
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()                     
            ########################            
            
            VBAtowhichErrorwasinjected = self.TLCvbaWritten[-1] + 48
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
            self.JBBeforeWAHandling = self.TLCjbWritten[-1]
            self.logger.Info(self.globalVarsObj.TAG, 'TLC JB before WA Detection :',self.JBBeforeWAHandling)            
            

        #########################
        self.TLCvbaWritten = []
        while(self.TLCvbaWritten == []):            
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024, txLenThreshold=None)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()          
        
        ######################## 
        
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "TLC WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "TLC WA wasn't detected"
        
           
        self.JBAfterWAHandling = self.TLCjbWritten[-1]
        self.logger.Info(self.globalVarsObj.TAG, 'TLC JB After WA Detection :',self.JBAfterWAHandling)
        
        if(not self.BlockAddedToPartialList and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "TLC Block Wasn't added to partial List in SD mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "TLC Block Wasn't added to partial List"              
        
        if(not self.BRLChappended and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC didnt happen in nvme mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC didnt happen in nvme mode"  
        
        if(self.BRLChappended and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC Happened in SD mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC Happened in SD mode" 
                
        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            
        
