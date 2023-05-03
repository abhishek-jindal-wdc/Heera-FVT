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
import CMDP.CMDP_AccessPattern_Lib as CMDP_AP_Lib

class EPWRFAILSDHandler:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not EPWRFAILSDHandler.__staticPFObj:
            EPWRFAILSDHandler.__staticPFObj = super(EPWRFAILSDHandler,cls).__new__(cls, *args, **kwargs)

        return EPWRFAILSDHandler.__staticPFObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.SDutilsObj = SDUtils.SDUtils
        self.switch= SDUtils.SDUtils()
        self.utilsObj = Utils.Utils()
        self.EPWRUtilsObj=EPWRUtils.EPWRUtils()
        self.sctpObj = SctpUtils.SctpUtils()        
        self.addrTranslatorObj = VBAToPBA_AddressTranslator.VBAToPBA_AddressTranslator()
        self.cmdpAPLib = CMDP_AP_Lib.CMDP_AccessPattern_Lib()
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba 
        self.lba = self.globalVarsObj.startLba
        self.tlcThrsCfgValue = -15
        self.slcThrsCfgValue = -10
        g_string_print_length = 35
        
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj, self.logger)
            self.wayPointDict = {
                "WP_PS_BBM_PH_BLOCK_RELINK"         : [self.WP_PS_BBM_PH_BLOCK_RELINK, 'PrintArguments'], 
                "WP_FTL_RLC_WRITE_JB_VBA"           : [self.WP_FTL_RLC_WRITE_JB_VBA,'PrintArguments'],
                "WP_FTL_BML_PARTIAL_BLOCK_ADDED"    : [self.WP_FTL_BML_PARTIAL_BLOCK_ADDED, 'PrintArguments'],
                "WP_PS_EPWR_FAIL"                   : [self.WP_PS_EPWR_FAIL, 'PrintArguments'],
                "WP_FTL_RLC_RLC_START"              : [self.WP_FTL_RLC_RLC_START, 'PrintArguments'],
                "WP_PS_EPWR_ACTIVATE"               : [self.WP_PS_EPWR_ACTIVATE, 'PrintArguments']
                
              }
            self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        
            
            
       
        
        
    def WP_FTL_BML_PARTIAL_BLOCK_ADDED(self,eventKey,args, pid):
        self.BlockAddedToPartialList = args[0]
        self.logger.Info(self.globalVarsObj.TAG, "WP_FTL_BML_PARTIAL_BLOCK_ADDED_Callback appeared with arguments: %s." %(str(args)))
        self.assertEqual(self.DestBlock,args[0],"-E- Destination block wasn't added to PBL")  
        self.PBLflag = True
        return        
        
    def WP_FTL_RLC_RLC_START(self ,eventKeys, arg, processorID):
        self.gc_TAG  = True    
    
    def WP_FTL_RLC_WRITE_JB_VBA(self,eventKey,args, pid):
        self.vba=arg[1]
        self.DestBlock= arg[0]
        
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
               
    
    
    def EPWRfailonSDTLC(self, Blockstate, **kwargs):
        startLba = 0
        self.txlen = 64
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING Destination TLC PF HANDLER *************')
        
        # to check device in SD mode
        self.switch.switchProtocol(self.deviceModeToSwitchCfgValue)
        
        #Setting thresholds
        if not (self.slcThrsCfgValue == 0 or self.tlcThrsCfgValue == 0): #Handle thresholds and adjust device range when test starts
            self.lbaRangeCfgValue = self.utilsObj.ThresholdHandler("start", self.slcThrsCfgValue, self.tlcThrsCfgValue)
        self.relocationStatisticsDictBeforeGcValue = self.sctpObj.GetRelocationStatistics()   #Get Relocation statistics
        self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)
        self.logger.Info(self.globalVarsObj.TAG, "|     Relocation Statistics Before test     |")
        self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)
        for key,val in self.relocationStatisticsDictBeforeGcValue.iteritems():
            self.logger.Info(self.globalVarsObj.TAG, "| {:<35} | {:<3} |".format(key, val))
            self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)
            
        #Perform writes until GC gets trigger   
        while self.gc_TAG != True:
            if self.lba <= (self.globalVarsObj.maxLba - self.txlen):
                self.ccmObj.Write(self.lba,self.txlen)
                self.lba = self.lba + self.txlen
            else:
                raise ValidationError.TestFailError("-E- Beyond Max LBA")  
            
        # Perform more writes to relocate data from slc to tlc
        while self.isEpwrStarted != True:
            self.ccmObj.Write(self.lba,self.txlen)
            self.lba = self.lba + self.txlen 
        
        
        
        if(not self.EPWRFail):
            self.logger.Info(self.globalVarsObj.TAG, "EPWR fail wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False 
        
        if(not self.PBLflag):
            self.logger.Info(self.globalVarsObj.TAG, "Block wasn't added to PBL")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False          
        
        
        
        self.logger.Info(self.globalVarsObj.TAG, "############ TLC EPWR fail handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            
        
