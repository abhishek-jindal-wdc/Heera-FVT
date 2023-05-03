import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import SctpUtils
import SDUtils
import Extensions.CVFImports as pyWrap
from collections import defaultdict
import CMDP_History as History
import ValidationLib.LDPCUtils as LDPCUtils
from Constants import LDPCREH as LDPCConstants
from Constants import GC as GCConstants
import CommonCodeManager    as CCM
import EIMediator           as EIMediator
import FwConfig             as FWConfig                         
import Utils                as Utils   
import WaypointReg


class CECChandler:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object PF HANDLER
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
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars() 
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.HistoryObj = History.EpicCallbacks()
        self.utilsObj       = Utils.Utils(self.vtfContainer)
        self.ldpcObj        = LDPCUtils.LDPCUtils(self.vtfContainer)
        #self.globalVarsObj.printWaypointArgs = False
        self.ReadRetryState = LDPCConstants.ReadRetryState	
	self.ccmObj         = self.globalVarsObj.ccmObj        
	self.sctpUtilsObj   = SctpUtils.SctpUtils()    
	self.__fwConfigData = FWConfig.FwConfig(self.vtfContainer)
	self.eiObj          = EIMediator.ErrorInjectionClass(self.globalVarsObj)
	
	
 
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = self.globalVarsObj.WayPointObj

            self.wayPointDict = {
	    'LDPC_HB_DECODE_START'  : [],
            'LDPC_HB_DECODE_END'    : [],
            'LDPC_SB_DECODE_START'  : [],
            'LDPC_SB_DECODE_END'    : [],
            'LDPC_DECODE_SUCCESS'   : [self.OnLDPCDecodeSuccess],
            'LDPC_BES_START'        : [],
            'LDPC_BES_END'          : [],
            "LDPC_BER"              : [],                        
            'UM_READ'               : [],
            'UECC_DETECTED'         : [self.OnUECCDetected],
            'CECC_DETECTED'         : [],
            "GAT_BLOCK_TRANSITION"  : [self.OnGATBlockTransition],
            "GCC_GOING_TO_READ"     : [],
            "CONTROL_PAGE_READ"     : [],
            "CONTROL_PAGE_WRITE"    : [self.OnControlPageWrite], 
	    "READ_ONLY_MODE"        : [self.OnReadOnlyMode],
                
            }
                   
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
         
        
    def OnUECCDetected(self,args):
        self.UECCdetected = True
	
    def OnEpwrStart(self,argDict):
	"""
	"""
	metaBlock = argDict["Block"]
	sector = argDict["Sector"]
	#if argDict["Block"]==self.PrimaryMB :
	    #self.epqwrOnPrimary=True

	return  	
    def OnReadOnlyMode(self,argdict):
	self.globalVarsObj.readOnlyMode=True
	self.globalVarsObj.clearError=True
	pass     
    
    #----------------------------------------------------------------------
    def InjectCECCError(self, MB, MBOffset, Page):
	DecodeError = self.globalVarsObj.randomObj.choice(['HB', 'SB1', 'SB2'])
	#DecodeError="HB"
	if DecodeError == 'HB':
	    # HB Correctable
	    self.phyAddr = self.ldpcObj.PassHBDecodeAtDefaultLevel(MB=MB, sectorOffset=MBOffset, Page=Page)
	    
	if DecodeError == 'SB1':
	    # SB1 Correctable
	    self.phyAddr = self.ldpcObj.PassSB1DecodeAtDefaultLevel(MB=MB, sectorOffset=MBOffset, Page=Page)
	    
	if DecodeError == 'SB2':
	    # SB2 Correctable
	    self.phyAddr = self.ldpcObj.FailSB1DecodeAtDefaultLevel(MB=MB, sectorOffset=MBOffset, Page=Page)
	
    def OnControlPageWrite(self,args):
		
	"""
	"BankNum","Pagetype","PgNum","MBNum","OffsetInMB","isPrimary", "Plane"         
	"""
	global ErrorPhase
	MBNum, OffsetInMB, Plane, PgNum, BankNum, pageType, isPrimary = args['MBNum'],args['OffsetInMB'], args['Plane'], args['PgNum'], args['BankNum'], args['Pagetype'],args['isPrimary']
	
	if ErrorPhase != 'DuringWriteToGATBlock':
	    self.PageForErrorInjection=Constants.ConfigParams.BE_SPECIFIC_MIP_ID_BYTE_IN_HEADER
	if self.PageForErrorInjection == pageType:
	    if self.InjectError and isPrimary and self.EIBLockType:
		ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		ErrorManager.ClearAllErrors()	
		self.logger.Info(self.globalVarsObj.TAG, "Error Injected On Primary 0x%x!"%(self.PageForErrorInjection))
				
		self.InjectCECCError(MBNum, OffsetInMB, "SLC")	
		self.insertPowerCycle=True
		self.InjectError=False
		
	    elif self.InjectError and isPrimary==0 and self.EIBLockType==0:
		ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		ErrorManager.ClearAllErrors()	
		self.logger.Info(self.globalVarsObj.TAG, "Error Injected On Secondary!0x%x!"%(self.PageForErrorInjection))
		
		self.InjectCECCError(MBNum, OffsetInMB, "SLC")	
		self.insertPowerCycle=True
		self.InjectError=False
		
	    	  
	return
    


    def ResetVariables(self):

	# Test Variables
	self.stream = 'Random'
	self.phyAddr = None   
	self.GATBlockTransitionOccurred = False
	self.PageForErrorInjection = self.globalVarsObj.randomObj.choice(
	[Constants.ConfigParams.CONTROL_BLOCK_GAT_DIRECTORY_PAGE_HEADER,
	Constants.ConfigParams.CONTROL_BLOCK_IGAT_PAGE_HEADER,	
	#Constants.ConfigParams.CONTROL_BLOCK_RGAT_PAGE_HEADER,
	Constants.ConfigParams.CONTROL_BLOCK_RGAT_DIRECTORY_PAGE_HEADER,
	])
	self.SB2DecodeFailed = False
	self.DecodeSuccessfulInGCPhase2 = False
	self.InjectError=True 
	self.EIBLockType=self.globalVarsObj.randomObj.choice([0, 1])

        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
	self.globalVarsObj.LivetObj.UnregisterLivetCallback(self.globalVarsObj.LivetObj.lcFlashProgramFail)
        
    
    def CECCHandlerMIP(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']
	self.wayPointHandlerObj.SetDict()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)
	
	
	self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING MIP CECC HANDLER *************')
	
        startLba       = self.globalVarsObj.randomObj.randint(0, self.globalVarsObj.maxLba)
        initialLba     = startLba    # storing startLba, required for invalidation
        transferlength = 0x60
        sectorsWritten = 0
        self.sectorsToWrite = self.__fwConfigData.slcMBSize
	self.writtenLbasList=[]
        
        while sectorsWritten < self.sectorsToWrite:
            if startLba + transferlength >= self.globalVarsObj.maxLba:
                startLba = 0
	    try:
		self.ccmObj.Write(startLba, transferlength)
	    except:
		if self.globalVarsObj.readOnlyMode:
		    ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		    ErrorManager.ClearAllErrors()		    
		    self.logger.Info(self.globalVarsObj.TAG, "Card is in Read Only mode")
		    
	    self.writtenLbasList.append(startLba)
            startLba = self.globalVarsObj.randomObj.randint(0, self.globalVarsObj.maxLba)
            sectorsWritten += transferlength
	    

	#Reading back written LBA's
	for readLba in self.writtenLbasList: 
	    self.ccmObj.Read(readLba, transferlength)
    
	if self.SB2DecodeFailed:
	    self.logger("", "UECC dectected but not injected on blocks: %s" % self.UECCDetectedBlockList)
	    return False
	else:
	    self.logger.Info("", "UECC did not occur as expected")
	    
	if self.DecodeSuccessfulInGCPhase2:
	    self.logger("", "GC Phase2 Decode triggered but not expected on Control Blocks!")
	    return False
	else:
	    self.logger.Info("", "GC Phase2 Decode did not trigger as expected on Control Blocks")
		

        self.logger.Info(self.globalVarsObj.TAG, "############ MIP CECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    

    #----------------------------------------------------------------------
    def OnLDPCDecodeSuccess(self, args):
        """
        ReadRetryState, GCPhase
        """
        if args["GCPhase"] == GCConstants.GCPhase2:
            self.DecodeSuccessfulInGCPhase2 = True
        return
    
    #----------------------------------------------------------------------
    def OnGATBlockTransition(self, args):
        """ 
        Args: LastActiveMB, Current_ActivePrimaryMB
        """
        self.GATBlockTransitionOccurred = True
        
        return
    
    #----------------------------------------------------------------------    
    def OnSBDecodeEnd(self, args):
        """
        Args: ['ReadStatus', 'DecodeMode', 'Die', 'Plane', 'Block', 'BlockType', 'WL', 'String', 'EccPage']
        """     
        if args['DecodeMode'] == LDPCConstants.SB2_Decode and args['ReadStatus'] == LDPCConstants.UECC:
            self.SB2DecodeFailed = True
        return    
    

    
    #-----------------------------------------------------------          
    def CECCHandlerGAT(self, Blockstate, **kwargs):
	global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	self.wayPointHandlerObj.SetDict()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)
	
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING GAT CECC HANDLER *************')
	
        startLba       = self.globalVarsObj.randomObj.randint(0, self.globalVarsObj.maxLba)
        initialLba     = startLba    # storing startLba, required for invalidation
        transferlength = 0x60
        sectorsWritten = 0
        self.sectorsToWrite = 3*self.__fwConfigData.slcMBSize
	self.writtenLbasList=[]
        
        while sectorsWritten < self.sectorsToWrite:
            if startLba + transferlength >= self.globalVarsObj.maxLba:
                startLba = 0
	    try:
		self.ccmObj.Write(startLba, transferlength)
	    except:
		if self.globalVarsObj.readOnlyMode:
		    ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		    ErrorManager.ClearAllErrors()		    
		    self.logger.Info(self.globalVarsObj.TAG, "Card is in Read Only mode")
		    
	    self.writtenLbasList.append(startLba)
            startLba = self.globalVarsObj.randomObj.randint(0, self.globalVarsObj.maxLba)
            sectorsWritten += transferlength
	    

	#Reading back written LBA's
	for readLba in self.writtenLbasList: 
	    self.ccmObj.Read(readLba, transferlength)
    
	if self.SB2DecodeFailed:
	    self.logger("", "UECC dectected but not injected on blocks: %s" % self.UECCDetectedBlockList)
	    return False
	else:
	    self.logger.Info("", "UECC did not occur as expected")
	    
	if self.DecodeSuccessfulInGCPhase2:
	    self.logger("", "GC Phase2 Decode triggered but not expected on Control Blocks!")
	    return False
	else:
	    self.logger.Info("", "GC Phase2 Decode did not trigger as expected on Control Blocks")

                    
        
        self.logger.Info(self.globalVarsObj.TAG, "############ GAT CECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    
       
        
        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
