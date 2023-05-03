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
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.IFSObj = IFS.IFS_Framework()        
        self.HistoryObj = History.EpicCallbacks()
        self.fsUtilObj = FSUtils.FSUtils()

        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            self.wayPointDict = {
                "WP_PS_PF_DETECTED"                 : [self.WP_PS_PF_DETECTED],
            }
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.BootObj = Boot.BOOT_Framework()
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
        self.FileId = None
        self.DieBeforePFinjection = None
        self.PlaneBeforePFinjection = None
        self.BlockBeforePFinjection = None
        self.pfInjected =False
        self.SwitchedFromPRIMARYtoSECONDARY = False
        self.pfInjectedSec = False 
        self.bad_blocks = []     
        self.CorruptPrimary = True
        self.CorruptSecondary = True
        self.BacktoBackPF = False        
        self.InBOOTPFHandling = False
        self.PrimaryBootBlock = False
        self.AddressBeforePFwasInjected = None
        self.AddressAfterPFwasInjected = None
        self.PhysicalAddressOfPrimaryBootBlock = None
        self.PhysicalAddressOfSecondaryBootBlock = None
        self.WriteStarted = []
        self.InjectedLogPF = False
        self.RecentlyWrittenLogJb = None
        self.BootPFinjected = False
        self.sctputilsobj.InjectIFSErrors(Constants.FS_CONSTANTS.IFS_CLR_ERR_INJ)           
        
        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    def PFHandlerIFS(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)                
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS PF HANDLER *************')
        #kwargs keys -> BlocksToFail(max 10), PrimaryBlockFail, SecondaryBlockFail, PrimarySecondaryBlockFail
        

        FileNumber = random.randint(170,180)     
        
        (FSPFCount, FSEFCount, FSRFCount, BootBlkSpares, PtnblkSpares) = self.fsUtilObj.GetFSblkErrorCount()
        ProgramErrorCount_BeforeEI=FSPFCount      
        
        errorType = random.choice([Constants.FS_CONSTANTS.IFS_ERR_WR_PF_PRI,\
                                   Constants.FS_CONSTANTS.IFS_ERR_WR_PF_SEC,\
                                   Constants.FS_CONSTANTS.IFS_ERR_COMP_WR_PF_PRI,\
                                   Constants.FS_CONSTANTS.IFS_ERR_COMP_WR_PF_SEC,\
                                   Constants.FS_CONSTANTS.IFS_ERR_PF_WR_PRI_DIR,\
                                   Constants.FS_CONSTANTS.IFS_ERR_PF_WR_SEC_DIR])
        
        self.logger.Info(self.globalVarsObj.TAG, "Randomly selected file is: %d\n"%FileNumber)       
        
        self.sctputilsobj.InjectIFSErrors(errorType, FileNumber)
        self.fsUtilObj.FsCompactionDiagFileWrites(FileNumber, 10, 10, True)    
        
        (FSPFCount, FSEFCount, FSRFCount, BootBlkSpares, PtnblkSpares) = self.fsUtilObj.GetFSblkErrorCount()    
        ProgramErrorCount_AfterEI=FSPFCount
        
        if ProgramErrorCount_AfterEI == ProgramErrorCount_BeforeEI:
            self.logger.Info(self.globalVarsObj.TAG, "IFS PF NOT DETECTED")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "IFS PF NOT DETECTED"            

        
        self.logger.Info(self.globalVarsObj.TAG, "############ IFS PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
       
           
    def PFHandlerBOOT(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)                
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING BOOT PF HANDLER *************')

        FileNumber = random.randint(170,180)     
        
        directoryFileId = Constants.FS_CONSTANTS.DIRECTORY_FILE_ID		
        lengthOfDirectoryFileInSectors, fileSizeInBytes = self.sctputilsobj.LengthOfFileInSectors(directoryFileId)
        directoryFileBufferBefore = pyWrap.Buffer.CreateBuffer(lengthOfDirectoryFileInSectors, 0x00, isSector=True)                
        directoryFileBufferBefore = self.sctputilsobj.ReadFileSystem(directoryFileId, lengthOfDirectoryFileInSectors, directoryFileBufferBefore)    
        (BlockOwnerBeforeWrites, BootIFSStringListBefore, PtnIFSStringListBeforeComp) = self.fsUtilObj.GetFSIndexAndBlockInfo(directoryFileBufferBefore)          
        
        PrimBootBlockindex = BlockOwnerBeforeWrites['PrimBoot']
        PrimBootBlkBeforeEI= PtnIFSStringListBeforeComp[PrimBootBlockindex]  		

        SecBootBlockindexBeforeEI = BlockOwnerBeforeWrites['SecBoot']
        SecBootBlkBeforeEI= PtnIFSStringListBeforeComp[SecBootBlockindexBeforeEI] 		
        
        errorType = random.choice([Constants.FS_CONSTANTS.IFS_ERR_COMP_UPD_BP_PRI,\
                                   Constants.FS_CONSTANTS.IFS_ERR_COMP_UPD_BP_SEC,\
                                   Constants.FS_CONSTANTS.IFS_ERR_WR_UPD_BP_PRI,\
                                   Constants.FS_CONSTANTS.IFS_ERR_WR_UPD_BP_SEC])        
        self.sctputilsobj.InjectIFSErrors(errorType=errorType, fileNumber=FileNumber)
        self.fsUtilObj.FsCompactionDiagFileWrites(FileNumber, 10, 10, True)    
        
        directoryFileBufferAfter = pyWrap.Buffer.CreateBuffer(lengthOfDirectoryFileInSectors, 0x00, isSector=True)                
        directoryFileBufferAfter = self.sctputilsobj.ReadFileSystem(directoryFileId, lengthOfDirectoryFileInSectors, directoryFileBufferAfter)            
        (BlockOwnerAfterWrites, BootIFSStringListAfter, PtnIFSStringListAfterComp) = self.fsUtilObj.GetFSIndexAndBlockInfo(directoryFileBufferAfter)          
        
        PrimBootBlockindexAfter = BlockOwnerAfterWrites['PrimBoot']
        PrimBootBlkAfterEI= PtnIFSStringListAfterComp[PrimBootBlockindexAfter] 
    
        SecBootBlockindexAfterEI = BlockOwnerAfterWrites['SecBoot']
        SecBootBlkAfterEI= PtnIFSStringListAfterComp[SecBootBlockindexAfterEI] 	
        
        if (errorType in [Constants.FS_CONSTANTS.IFS_ERR_WR_UPD_BP_PRI,Constants.FS_CONSTANTS.IFS_ERR_COMP_UPD_BP_PRI]) and (PrimBootBlockindexAfter !=PrimBootBlockindex) and (PrimBootBlkBeforeEI !=PrimBootBlkAfterEI):
            self.logger.Info(self.globalVarsObj.TAG, "Boot Block Compaction happened successfully")   
        elif(errorType in [Constants.FS_CONSTANTS.IFS_ERR_WR_UPD_BP_SEC,Constants.FS_CONSTANTS.IFS_ERR_COMP_UPD_BP_SEC]) and (SecBootBlockindexAfterEI!=SecBootBlockindexBeforeEI) and (SecBootBlkAfterEI !=SecBootBlkBeforeEI):
            self.logger.Info(self.globalVarsObj.TAG, "Boot Block Compaction happened successfully")            
        else:
            self.logger.Info(self.globalVarsObj.TAG, "PF wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "BOOT PF wasn't detected"
            
            
        
        self.logger.Info(self.globalVarsObj.TAG, "############ BOOT PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
