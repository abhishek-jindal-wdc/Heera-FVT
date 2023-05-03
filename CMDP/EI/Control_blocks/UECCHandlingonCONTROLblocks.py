import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
from collections import defaultdict
import CMDP_History as History
import EIMediator
import FwConfig as FwConfig
import Utils as Utils

class UECChandler:
    
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
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
        self.HistoryObj = History.EpicCallbacks()
	self.__sctpUtilsObj = SctpUtils.SctpUtils()
	self.__fwConfigObj=FwConfig.FwConfig(self.globalVarsObj.vtfContainer)
        self.utilsObj       = Utils.Utils(self.vtfContainer)
	
 
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = self.globalVarsObj.WayPointObj

            self.wayPointDict = {
              
                "CONTROL_PAGE_WRITE"      : [self.OnControlPageWrite],
                "GAT_BLOCK_TRANSITION"    : [self.OnGatBlockTransition], 
                #"GAT_BLOCK_TRANSITION_AFTER" : [],
                #"GAT_BLOCK_TRANSITION_BEFORE" : [], 
                #"DLM_BAD_BLOCK_RELEASED" : [],
                #"DLM_GROWN_BAD_BLOCK_ADDED" : [],
                #"EPWR_COMPLETE" : [],
                "EPWR_START"             : [self.OnEpwrStart],       
	        "MIP_UPDATE_BEGIN"       : [self.OnMIPUpdateBegin],
	        "MIP_UPDATE_HAPPENED"    : [self.OnMIPUpdateHappened],
	        "MIP_BLOCK_TRANSITION"   : [self.OnMipBlockTransition],
	        "READ_ONLY_MODE"         : [self.OnReadOnlyMode],
	        "UECC_DETECTED"          :[self.OnUECCDetected],
	        #"MIP_BLOCK_TRANSITION_AFTER" : [self.OnMipBlockTransitionAfter], 
	        #"MIP_BLOCK_EXCHANGE"         : [self.OnMipBlockExchanged],	        
                
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
    

    def OnControlPageWrite(self,args):
		
	"""
	"BankNum","Pagetype","PgNum","MBNum","OffsetInMB","isPrimary", "Plane"         
	"""
	global ErrorPhase
	MBNum, OffsetInMB, Plane, PgNum, BankNum, pageType, isPrimary = args['MBNum'],args['OffsetInMB'], args['Plane'], args['PgNum'], args['BankNum'], args['Pagetype'],args['isPrimary']
	
	if ErrorPhase != 'DuringWriteToGATBlock':
	    self.chooseErrorPagetype=Constants.ConfigParams.BE_SPECIFIC_MIP_ID_BYTE_IN_HEADER
	if self.chooseErrorPagetype == pageType:
	    if self.InjectError and isPrimary and self.EIBLockType:
		ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		ErrorManager.ClearAllErrors()	
		self.logger.Info(self.globalVarsObj.TAG, "Error Injected On Primary 0x%x!"%(self.chooseErrorPagetype))
		
		phyAddr = self.errorInjObj.GetPhysicalAddress(MBNum, OffsetInMB)		
		self.errorInjObj.InjectUECCErrorWithSTM(errorPhyAddress=phyAddr, 
		                             isCalledFromWaypoint=True, 
		                             isForceUECC=False, 
		                             blktype='slc', 
		                             applyOnlyToPhysicalPage=False, 
		                             applyOnlyToEccPage=True, 
		                             isToBeAppliedToBlock=False)	
		self.insertPowerCycle=True
		self.InjectError=False
		
	    elif self.InjectError and isPrimary==0 and self.EIBLockType==0:
		ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		ErrorManager.ClearAllErrors()	
		self.logger.Info(self.globalVarsObj.TAG, "Error Injected On Secondary!0x%x!"%(self.chooseErrorPagetype))
		
		phyAddr = self.errorInjObj.GetPhysicalAddress(MBNum, OffsetInMB)		
		self.errorInjObj.InjectUECCErrorWithSTM(errorPhyAddress=phyAddr, 
		                             isCalledFromWaypoint=True, 
		                             isForceUECC=False, 
		                             blktype='slc', 
		                             applyOnlyToPhysicalPage=False, 
		                             applyOnlyToEccPage=True, 
		                             isToBeAppliedToBlock=False)
		self.insertPowerCycle=True
		self.InjectError=False
		
	    	  
	return
    
    
    def OnGatBlockTransition(self,argDict):
	self.GatBlockTransition = True	    
	pass    

        
    def OnMIPUpdateBegin(self,argDict): 
	self.MIPUpdatebegin=True
	pass
    def OnMIPUpdateHappened(self,args):
	pass
    def OnMipBlockTransition(self,args):
	self.MIPBlockTransitionDone=True
	pass
    def OnMipBlockTransitionAfter(self,args):	    
	pass
    def OnMipBlockExchanged(self,argDict):
	pass

    def ResetVariables(self):
	self.__randomObj           = self.globalVarsObj.randomObj
        self.writtendata = []
        self.UECCdetected = False
    
        self.InjectError=False
	self.ControlPageWrite=False
	self.EIBLockType=self.globalVarsObj.randomObj.choice([0, 1])
	
	global ErrorPhase
	self.MIPUpdatebegin=False
	self.GatBlockTransition=False
	self.ErrorInjectedMB=0
	self.MIPBlockTransitionDone=False	
	self.insertPowerCycle=False

	self.chooseErrorPagetype=self.globalVarsObj.randomObj.choice(
	[Constants.ConfigParams.CONTROL_BLOCK_GAT_DIRECTORY_PAGE_HEADER,
	Constants.ConfigParams.CONTROL_BLOCK_IGAT_PAGE_HEADER,	
	Constants.ConfigParams.CONTROL_BLOCK_RGAT_PAGE_HEADER,
	Constants.ConfigParams.CONTROL_BLOCK_RGAT_DIRECTORY_PAGE_HEADER,
	])
	
        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
	self.globalVarsObj.LivetObj.UnregisterLivetCallback(self.globalVarsObj.LivetObj.lcFlashProgramFail)
        
    
    def UECCHandlerMIP(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']
	self.wayPointHandlerObj.SetDict()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)
	
	
	self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING MIP UECC HANDLER *************')
	
	chosenCase = self.__randomObj.choice(['random', 'sequential'])
	transferLength = self.__fwConfigObj.sectorsPerLgFragment
	if chosenCase=='random':
	    self.numWrites = 5000
	if chosenCase=="sequential":
	    self.numWrites = 10000
	self.__randomLG               = self.__randomObj.randint(0, self.__fwConfigObj.lgsInCard)
	self.__startLba               = self.__randomLG * self.__fwConfigObj.sectorsPerLg  	
	#count = 0
	numOfWritesDone=0
	#self.InjectEIAtWrite=self.__randomObj.randint(0, self.numWrites/4)
	self.InjectError=True	
	while(numOfWritesDone < self.numWrites):
	    if self.__startLba + transferLength >= self.__fwConfigObj.maxLba:
		self.__startLba = 0
		
	    try:
		self.globalVarsObj.ccmObj.Write(self.__startLba, transferLength)
	    except:
		if self.globalVarsObj.readOnlyMode:
		    ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		    ErrorManager.ClearAllErrors()		    
		    self.logger.Info(self.globalVarsObj.TAG, "Card is in Read Only mode")
		
		    
	    if self.globalVarsObj.readOnlyMode:
		numOfWritesDone=self.numWrites+1
		    
	    if self.insertPowerCycle:
		self.utilsObj.PowerCycle()
		self.insertPowerCycle=False
			 
	    numOfWritesDone+=1
	    
	    if chosenCase == 'sequential':
		self.__startLba += transferLength
	    else:
		self.__randomLG = self.__randomObj.randint(0, self.__fwConfigObj.lgsInCard)
		self.__startLba = self.__randomLG * self.__fwConfigObj.sectorsPerLg
		
        
        
        if(not self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "UECC wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False
        
            
        self.logger.Info(self.globalVarsObj.TAG, "############ MIP UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
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
                    
            self.globalVarsObj.ccmObj.Write(currentLBA, self.FMU)
            
                
            self.logger.Info(self.globalVarsObj.TAG, '%d : WRITE ON LBA %d of transfer length %d'%(writeNumber , currentLBA, self.FMU))
            currentLBA += (self.FMU + gapLeft + 1)
        self.HistoryObj.HistoryObj.LastWrittenLBA = currentLBA
            
    def UECCHandlerGAT(self, Blockstate, **kwargs):
	global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	self.wayPointHandlerObj.SetDict()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)
	
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING GAT UECC HANDLER *************')
	
	
	chosenCase = self.__randomObj.choice(['random', 'sequential'])
	transferLength = self.__fwConfigObj.sectorsPerLgFragment
	if chosenCase=='random':
	    self.numWrites = 5000
	if chosenCase=="sequential":
	    self.numWrites = 10000
	self.__randomLG= self.__randomObj.randint(0, self.__fwConfigObj.lgsInCard)
	self.__startLba= self.__randomLG * self.__fwConfigObj.sectorsPerLg  	
	#count = 0
	numOfWritesDone=0
	#self.InjectEIAtWrite=self.__randomObj.randint(0, self.numWrites/4)
	self.InjectError=True
	while(numOfWritesDone < self.numWrites):
	    if self.__startLba + transferLength >= self.__fwConfigObj.maxLba:
		self.__startLba = 0
	
	    try:
		self.globalVarsObj.ccmObj.Write(self.__startLba, transferLength)
	    except:
		if self.globalVarsObj.readOnlyMode:
		    ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		    ErrorManager.ClearAllErrors()		    
		    self.logger.Info(self.globalVarsObj.TAG, "Card is in Read Only mode")
		
		    
	    if self.globalVarsObj.readOnlyMode:
		numOfWritesDone=self.numWrites+1
		    
	    numOfWritesDone+=1
	    
	    if chosenCase == 'sequential':
		self.__startLba += transferLength
	    else:
		self.__randomLG = self.__randomObj.randint(0, self.__fwConfigObj.lgsInCard)
		self.__startLba = self.__randomLG * self.__fwConfigObj.sectorsPerLg 
	    
	
        if(not self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "UECC wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "UECC wasn't detected"
                    
        
        self.logger.Info(self.globalVarsObj.TAG, "############ GAT UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    
       
        
        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
