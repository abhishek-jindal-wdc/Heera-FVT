import Constants
import os
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WaypointReg
import SDUtils
import Extensions.CVFImports as pyWrap
import random
import VBAToPBA_AddressTranslator
import CMDP.EINCTD_Library as CMDP_AP_Lib

class EPWRFAILHandler:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not EPWRFAILHandler.__staticPFObj:
            EPWRFAILHandler.__staticPFObj = super(EPWRFAILHandler,cls).__new__(cls, *args, **kwargs)

        return EPWRFAILHandler.__staticPFObj

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
        self.addrTranslatorObj = VBAToPBA_AddressTranslator.VBAToPBA_AddressTranslator()
        self.cmdpAPLib = CMDP_AP_Lib.CMDP_AccessPattern_Lib()
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba        
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj, self.logger)
            self.wayPointDict = {
                "WP_PS_BBM_PH_BLOCK_RELINK"         : [self.WP_PS_BBM_PH_BLOCK_RELINK, 'PrintArguments'], 
                "WP_FTL_HWD_WRITE_JB_VBA"           : [self.WP_FTL_HWD_WRITE_JB_VBA,'PrintArguments'],
                "WP_PS_EPWR_FAIL"                    : [self.WP_PS_EPWR_FAIL, 'PrintArguments'],
                "WP_PS_EPWR_ACTIVATE"               : [self.WP_PS_EPWR_ACTIVATE, 'PrintArguments']
                
                
              }
            self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        
   
    def WP_PS_EPWR_FAIL(self, eventKeys, arg, processorID):
        self.EPWRFail = True  
        
    def WP_PS_EPWR_ACTIVATE(self, eventKeys, args, processorID):
        self.isEpwrStarted = True
        if self.isErrorInjected == False:
            errorPba = self.addrTranslatorObj.GetVbaToTlcFlashAddress(vba=self.vba)
            self.InjectUECC(errorPba, wordline=args[2])
            self.isErrorInjected = True            
    
    def WP_PS_BBM_PH_BLOCK_RELINK(self,eventKey,args, pid):
        self.RelinkingHappened = True
    
        
    def InjectUECC(self,errorPba, wordline=0):
        try:
            sandiskValidationPathValue = os.getenv("FVTPATH")
            subfolderName = "ValidationLib"
            subfolderPath = os.path.join(sandiskValidationPathValue, subfolderName)
            stmfile = 'C:\Program Files (x86)\SanDisk\SanDisk ValidationScripts\FVT_SDExpress\ValidationLib\STM_files\NORMAL_VER1.03_BER_1646_1523_1441_1646_OPTBER_1646_1524_1448_1433.stm'
            stmObj = self.livetObj.GetFlash().LoadSTMfromDisk(stmfile) # STM Handle
            REVERT_ON_ERASE = 1 # this is the default value assumed as of now
            package = 0 # this is the default value assumed as of now
            self.livetObj.GetFlash().ApplySTMtoWordline(stmObj, package, errorPba['dieInFim'], errorPba['plane'], errorPba['block'], wordline, REVERT_ON_ERASE)  
        except Exception as e_obj:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'EXCEPTION: In InjectUECC() - ' + str(e_obj))
        return
                
    
    def ResetVariables(self):
        self.writtendata = []
        self.PFdetected = False
        self.EPWRFail = False
        self.PBLflag = False
        self.isEpwrStarted = False
        self.gc_TAG = False
        self.isErrorInjected = False
        self.RelinkingHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterPFHandling = None
        self.AddressBeforePFHandling = None
        self.SLCvbaWritten = []
        self.SLCjbWritten = []
        self.TLCvbaWritten = []
        self.TLCjbWritten = []   
        self.BlockAddedToPartialList = -1
    
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
    
    def EPWRfailonTLCPCIE(self, Blockstate, **kwargs):
        startLba = 0
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC PF HANDLER *************')
        
        #Change mode to TLC
        self.sctputilsobj.changeModeToTLC()
    
        #data writes	    
        while self.isEpwrStarted != True:
            self.ccmObj.Write(self.lba,self.txlen)
            self.ccmObj.DoFlushCache()
            self.lba = self.lba + self.txlen
        
        
        if(not self.EPWRFail):
            self.logger.Info(self.globalVarsObj.TAG, "EPWR fail wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False           
        
        if(not self.RelinkingHappened):
            self.logger.Info(self.globalVarsObj.TAG, "Relink wasn't detected after EPWR Fail")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False         
        
        
        self.logger.Info(self.globalVarsObj.TAG, "############ PCIE TLC EPWR fail handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            
        
        