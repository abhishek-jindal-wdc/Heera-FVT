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
	self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars() 
	self.logger = self.globalVarsObj.logger
	self.vtfContainer = self.globalVarsObj.vtfContainer
	self.livetObj = self.vtfContainer._livet
	self.sctputilsobj = SctpUtils.SctpUtils()
	self.errorInjObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
	self.HistoryObj = History.EpicCallbacks()
	self.__sctpUtilsObj = SctpUtils.SctpUtils()
	self.__fwConfigObj=FwConfig.FwConfig(self.globalVarsObj.vtfContainer) 
	self.errorInjObj.RegisterWriteAbortCallback(self.OnWriteAbort)
	self.errorInjObj.RegisterPreWriteAbortCallback(self.OnPreWriteAbort)
	self.errorInjObj.RegisterPostWriteAbortCallback(self.OnPostWriteAbort)	
        
                      
        self.HistoryObj = History.EpicCallbacks()
        
        
        
        if self.vtfContainer.isModel is True:
	    self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = self.globalVarsObj.WayPointObj

            self.wayPointDict = {
              
                "CONTROL_PAGE_WRITE"          : [self.OnControlPageWrite],
                "READ_ONLY_MODE"              : [],
                "GAT_BLOCK_TRANSITION"        : [self.OnGatBlockTransition], 
                #"GAT_BLOCK_TRANSITION_AFTER" : [],
                #"GAT_BLOCK_TRANSITION_BEFORE": [], 
                #"DLM_BAD_BLOCK_RELEASED"     : [],
                #"DLM_GROWN_BAD_BLOCK_ADDED"  : [],
                #"EPWR_COMPLETE"              : [],
                #"EPWR_START"                 : [],       
	        "MIP_UPDATE_BEGIN"            : [self.OnMIPUpdateBegin],
	        "MIP_UPDATE_HAPPENED"         : [self.OnMIPUpdateHappened],
	        "MIP_BLOCK_TRANSITION"        : [self.OnMipBlockTransition],
	        "READ_ONLY_MODE"              : [self.OnReadOnlyMode],
	        #"MIP_BLOCK_TRANSITION_AFTER" : [self.OnMipBlockTransitionAfter], 
	        #"MIP_BLOCK_EXCHANGE"         : [self.OnMipBlockExchanged],	        
                
            }
                   
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)         
        
        self.ResetVariables()
	


	
                   
    def ResetVariables(self):
       	self.__randomObj           = self.globalVarsObj.randomObj
        self.writtendata = []
        self.WAdetected = False
    
        self.InjectError=False
	self.ControlPageWrite=False
	self.EIBLockType=self.globalVarsObj.randomObj.choice([0, 1])
	
	global ErrorPhase
	self.MIPUpdatebegin=False
	self.GatBlockTransition=False
	self.ErrorInjectedMB=0
	self.MIPBlockTransitionDone=False	

	self.chooseErrorPagetype=self.globalVarsObj.randomObj.choice(
	[Constants.ConfigParams.CONTROL_BLOCK_GAT_PAGE_HEADER,
	Constants.ConfigParams.CONTROL_BLOCK_GAT_DIRECTORY_PAGE_HEADER,
	Constants.ConfigParams.CONTROL_BLOCK_IGAT_PAGE_HEADER,	
	Constants.ConfigParams.CONTROL_BLOCK_RGAT_PAGE_HEADER,
	Constants.ConfigParams.CONTROL_BLOCK_RGAT_DIRECTORY_PAGE_HEADER,
	])
	
	
	
    def OnWriteAbort(self,Package,Addr): 
	self.WAdetected=True
	self.globalVarsObj.APEI =True
	return
    def OnPreWriteAbort(self,Package,Addr):
	self.WAdetected=True
	self.globalVarsObj.APEI =True
	return	
    def OnPostWriteAbort(self,Package,Addr):
	self.WAdetected=True
	self.globalVarsObj.APEI =True
	return	
    
    def OnReadOnlyMode(self,argdict):
	self.globalVarsObj.readOnlyMode=True
	self.globalVarsObj.clearError=True
	self.__logger.Info(self.globalVarsObj.TAG, "Card in Read only mode.......")
	return     
    
    
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
		self.logger.Info(self.globalVarsObj.TAG, "Error Injected On Primary!")
		
		phyAddr = self.errorInjObj.GetPhysicalAddress(MBNum, OffsetInMB)
		choosen = self.globalVarsObj.randomObj.choice(["wrab","prwa","powa"])			
		self.errorInjObj.InjectWriteAbortError(errorType=choosen, errorPhyAddress=phyAddr)			
		self.InjectError=False
		
	    elif self.InjectError and isPrimary==0 and self.EIBLockType==0:
		ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		ErrorManager.ClearAllErrors()	
		self.logger.Info(self.globalVarsObj.TAG, "Error Injected On Secondary!")
		
		phyAddr = self.errorInjObj.GetPhysicalAddress(MBNum, OffsetInMB)
		choosen = self.globalVarsObj.randomObj.choice(["wrab","prwa","powa"])			
		self.errorInjObj.InjectWriteAbortError(errorType=choosen, errorPhyAddress=phyAddr)			
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

        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    
    def WAHandlerMIP(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']
	self.wayPointHandlerObj.SetDict()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)
	
	self.errorInjObj.RegisterWriteAbortCallback(self.OnWriteAbort)
	self.errorInjObj.RegisterPreWriteAbortCallback(self.OnPreWriteAbort)
	self.errorInjObj.RegisterPostWriteAbortCallback(self.OnPostWriteAbort)
	
	self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING MIP WA HANDLER *************')
	
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
	self.InjectEIAtWrite=self.__randomObj.randint(0, self.numWrites/4)
	
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
	    
	    if numOfWritesDone == self.InjectEIAtWrite :
		self.InjectError=True	
        
        
        if(not self.WAdetected):
            self.logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False
        
            
        self.logger.Info(self.globalVarsObj.TAG, "############ MIP WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def WAHandlerGAT(self, Blockstate, **kwargs):
        global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	self.wayPointHandlerObj.SetDict()
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)
	
	self.errorInjObj.RegisterWriteAbortCallback(self.OnWriteAbort)
	self.errorInjObj.RegisterPreWriteAbortCallback(self.OnPreWriteAbort)
	self.errorInjObj.RegisterPostWriteAbortCallback(self.OnPostWriteAbort)
	
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING GAT WA HANDLER *************')
	
	
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
	self.InjectEIAtWrite=self.__randomObj.randint(0, self.numWrites/4)
	
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
	    
	    if numOfWritesDone == self.InjectEIAtWrite :
		self.InjectError=True
	    
	
        if(not self.WAdetected):
            self.logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "PF wasn't detected"
                    
        
        self.logger.Info(self.globalVarsObj.TAG, "############ GAT WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    

        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
