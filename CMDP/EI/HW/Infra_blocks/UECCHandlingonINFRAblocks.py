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

class UECChandler:
    
    __staticUECCObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not UECChandler.__staticUECCObj:
            UECChandler.__staticUECCObj = super(UECChandler,cls).__new__(cls, *args, **kwargs)

        return UECChandler.__staticUECCObj

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
        
             
        self.BootObj = Boot.BOOT_Framework()
        self.ResetVariables()
    
        
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
        self.sctputilsobj.InjectIFSErrors(Constants.FS_CONSTANTS.IFS_CLR_ERR_INJ)           
        
       
        
    def UECCHandlerIFS(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS UECC HANDLER *************')
        #kwargs keys -> BlocksToFail(max 10), PrimaryBlockFail, SecondaryBlockFail, PrimarySecondaryBlockFail
        FileNumber = random.randint(170,180)   
        fileLengthInSectors = 10
        (_, _, FSRFCountBefore, _, _) = self.fsUtilObj.GetFSblkErrorCount()
        
        writeFileBuffer = pyWrap.Buffer.CreateBuffer(5120, 0xA5, isSector=False)         
        self.sctputilsobj.WriteFileSystem(FileNumber, fileLengthInSectors, writeFileBuffer)	        

        
        errorType = random.choice([#Constants.FS_CONSTANTS.IFS_ERR_COMP_RD_PRI,\
                                   #Constants.FS_CONSTANTS.IFS_ERR_COMP_RD_SEC,\
                                   Constants.FS_CONSTANTS.IFS_ERR_RD_PRI,\
                                   Constants.FS_CONSTANTS.IFS_ERR_RD_SEC])                
        self.sctputilsobj.InjectIFSErrors(errorType, FileNumber)      
        
        
        readFileBuffer = pyWrap.Buffer.CreateBuffer(5120, 0x00, isSector=False)        
        readFileBuffer = self.sctputilsobj.ReadFileSystem(FileNumber, fileLengthInSectors, readFileBuffer)
        self.fsUtilObj.FsCompactionDiagFileWrites(FileNumber, 10, 10, True)    
        
        (_, _, FSRFCountAfter, _, _) = self.fsUtilObj.GetFSblkErrorCount()
                
        
        #compare bad blocks list
        if(FSRFCountAfter == FSRFCountBefore):
            self.logger.Info(self.globalVarsObj.TAG, "IFS UECC not detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            return "IFS UECC not detected"
        
        self.logger.Info(self.globalVarsObj.TAG, "############ IFS UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        return True
    
    
    
    def UECCHandlerBOOT(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING BOOT UECC HANDLER *************')
        #kwargs keys -> BlocksToFail(max 10), PrimaryBlockFail, SecondaryBlockFail, PrimarySecondaryBlockFail
        #Not supported
                
        self.logger.Info(self.globalVarsObj.TAG, "############ BOOT PF handling SUCCESSFULL###############")
        self.ResetVariables()
        return True    
          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
