import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
import IFS
import Boot
import CMDP.CMDP_History as History
import random
import FSUtils
import NVMeCMDWrapper as NVMeWrap


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
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.IFSObj = IFS.IFS_Framework()        
        self.HistoryObj = History.EpicCallbacks()
        self.fsUtilObj = FSUtils.FSUtils()                 
        
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            self.wayPointDict = {
            }
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.BootObj = Boot.BOOT_Framework()
        self.ResetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)        

        
    def ErrorHandlerFunction(self,statusCodeType,statusCode):	
        self.logger.Info(self.globalVarsObj.TAG, "Callback received with received status code: %d and status code type: %d"%(statusCode,statusCodeType))       
        self.KWARGS['EINobj'].cmdpScsiFeLib.inLowVoltageMode = False
        
        if((statusCode == 144)):
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
        
        self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762 
            
        
    def ResetVariables(self):
        self.writtendata = []
        self.PFdetected = False
        self.XorDumpHappened = False
        self.RelinkingnotHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterWAHandling = None
        self.LogDumpHappened = False
        self.MTMconsolidationHappened = False
        self.FileId = None
        self.DieBeforeWAinjection = None
        self.PlaneBeforeWAinjection = None
        self.BlockBeforeWAinjection = None
        self.WAInjected =False
        self.SwitchedFromPRIMARYtoSECONDARY = False
        self.WAInjectedSec = False 
        self.bad_blocks = []     
        self.CorruptPrimary = True
        self.CorruptSecondary = True
        self.BacktoBackWA = False        
        self.InBOOTWAHandling = False
        self.PrimaryBootBlock = False
        self.AddressBeforeWAwasInjected = None
        self.AddressAfterWAwasInjected = None
        self.PhysicalAddressOfPrimaryBootBlock = None
        self.PhysicalAddressOfSecondaryBootBlock = None
        self.WriteStarted = []
        self.InjectedLogPF = False
        self.RecentlyWrittenLogJb = None
        self.BootWAinjected = False
        self.SetSwitchDuringAbort(setFlag=1)
        #self.sctputilsobj.InjectIFSErrors(Constants.FS_CONSTANTS.IFS_CLR_ERR_INJ)    
        self.sctputilsobj.ErrorInjection(subOpcode=0x0001)
        self.KWARGS = {}
        
        
    def SetSwitchDuringAbort(self, setFlag = 0):
        self.globalVarsObj.configParser.SetValue("Switch_protocol_after_abort", setFlag)
            
    def WAHandlerIFS(self, Blockstate, **kwargs):
        self.KWARGS = kwargs
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)                
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS PF HANDLER *************')
        #kwargs keys -> BlocksToFail(max 10), PrimaryBlockFail, SecondaryBlockFail, PrimarySecondaryBlockFail
        

        FileNumber = random.randint(170,180)     
        
        (FSPFCount, FSEFCount, FSRFCount, BootBlkSpares, PtnblkSpares) = self.fsUtilObj.GetFSblkErrorCount()
        ProgramErrorCount_BeforeEI=FSPFCount      
                        
        #self.sctputilsobj.InjectIFSErrors(errorType, FileNumber)
        self.sctputilsobj.ErrorInjection(binType='lnfraBlksWriteRandomDPA')
        self.fsUtilObj.FsCompactionDiagFileWrites(FileNumber, 10, 10, True)    
        
        (FSPFCount, FSEFCount, FSRFCount, BootBlkSpares, PtnblkSpares) = self.fsUtilObj.GetFSblkErrorCount()    
        ProgramErrorCount_AfterEI=FSPFCount
        
        if ProgramErrorCount_AfterEI == ProgramErrorCount_BeforeEI:
            self.logger.Info(self.globalVarsObj.TAG, "IFS WA NOT DETECTED")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            return "IFS WA NOT DETECTED"            

        
        self.logger.Info(self.globalVarsObj.TAG, "############ IFS WA handling SUCCESSFULL###############")
        self.ResetVariables()
        return True

    
    def WAHandlerBOOT(self, Blockstate, **kwargs):
        global WriteAbortDetected    
        self.KWARGS = kwargs
        
        self.DeregisterAllWaypoint()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)                
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING BOOT WA HANDLER *************')
        #kwargs keys -> BlocksToFail(max 10), PrimaryBlockFail, SecondaryBlockFail, PrimarySecondaryBlockFail
        self.InBOOTWAHandling = True
        
        #To Avoid IFS clash
        self.CorruptPrimary = False 
        self.CorruptSecondary = False
        self.BacktoBackWA = False        
        #################################
        
        #self.sctputilsobj.ForceBootUpdate()   
        try:            
            self.WriteSequentiallyTillBootFlushHappens()
        except:
            self.errorManager.ClearAllErrors() 
            
        self.InBOOTWAHandling = False
        self.BootBlockInfo = self.BootObj.getRecentBootPage()
        
        self.BootBlockPrimaryAddressBeforeWA = self.BootBlockInfo['PrimaryBootPage']     
        self.BootBlockSecondaryAddressBeforeWA = self.BootBlockInfo['SecondaryBootPage']       
        self.BootPagePrimaryBeforeWA = self.BootBlockInfo['LatestPageNumberPrimary']
        self.BootPageSecondaryBeforeWA = self.BootBlockInfo['LatestPageNumberSecondary']
        self.VersionNumberPrimaryBeforeWA = self.BootBlockInfo['LatestRevisionCountPrimary']
        self.VersionNumberSecondaryBeforeWA = self.BootBlockInfo['LatestRevisionCountSecondary']        
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "WA wasn't detected"
        
        self.BootBlockInfoAfterWA = self.BootObj.getRecentBootPage()
    
        self.LatestBootBlockPrimaryAddress = self.BootBlockInfoAfterWA['PrimaryBootPage']     
        self.LatestBootBlockSecondaryAddress = self.BootBlockInfoAfterWA['SecondaryBootPage']       
        self.latestBootPagePrimary = self.BootBlockInfoAfterWA['LatestPageNumberPrimary']
        self.latestBootPageSecondary = self.BootBlockInfoAfterWA['LatestPageNumberSecondary']
        self.latestVersionNumberPrimary = self.BootBlockInfoAfterWA['LatestRevisionCountPrimary']
        self.latestVersionNumberSecondary = self.BootBlockInfoAfterWA['LatestRevisionCountSecondary']
        
        if(self.latestVersionNumberPrimary != self.latestVersionNumberSecondary):
            self.logger.Info(self.globalVarsObj.TAG, "Firmware Version numbers are not corrected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "Firmware Version numbers are not corrected"        
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "WA wasn't detected"
        
        if(self.LatestBootBlockPrimaryAddress == self.BootBlockPrimaryAddressBeforeWA):
            self.logger.Info(self.globalVarsObj.TAG, "New Boot block wasnt allocated even after WA was detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "New Boot block wasnt allocated even after WA was detected"             
        
        self.logger.Info(self.globalVarsObj.TAG, "############ BOOT WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
