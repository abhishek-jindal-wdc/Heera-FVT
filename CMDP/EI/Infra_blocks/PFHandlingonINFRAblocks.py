import Constants
import Core.ValidationError as ValidationError
import SctpUtils
import SDUtils
import Extensions.CVFImports as pyWrap
import CMDP_History as History
global PFOccured,BlmGrownBadBlockArgs,FSCompaction
import SCSIGlobalVars
import WaypointReg
import FwConfig as FwConfig
import Utils as Utils
import BOOTUtils as FSBootLib
import ConfigParser
import AddressTranslation
import EIMediator
import Core.ValidationError as TestError
import Core.SctpInterface as SCTPcls
import AddressTypes
import AddressTranslation
#import py_sfcl
import IFSErrorInjectionLib as IFSErrorInjectionLib
import SDFS
FSCompaction=False
PFOccured=False
BlmGrownBadBlockArgs=None
g_logger = None

class PFhandler:
    
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
	self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars()
	self.__ccmObj         = self.globalVarsObj.ccmObj
	#self.__eiObjUtil = EIMediator.ErrorInjectionUtilsClass(self.globalVarsObj)
	self.__eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
	self.__fwConfigData=FwConfig.FwConfig(self.globalVarsObj.vtfContainer)
	self.__addrTranslatnObj=AddressTranslation.AddressTranslator(self.globalVarsObj.vtfContainer)	
	
	self.WaypointRegObj = self.globalVarsObj.WayPointObj
	self.utilsObj       = Utils.Utils()    
	self.sctpUtilsObj = SctpUtils.SctpUtils()
	self.SCTPObj = SCTPcls.SctpInterface()
	self.PhyAddr =  AddressTypes.PhysicalAddress()
		    
        #self.HistoryObj = History.EpicCallbacks()
        
        self.ResetVariables()
    
    
    def ResetVariables(self):
	self.__logger = self.globalVarsObj.logger 
		
	self.__applicationRunAttributesObj = "PF"
	self.vtfContainer = self.globalVarsObj.vtfContainer
	self.livetObj = self.vtfContainer._livet	
	self.__randomObj   = self.globalVarsObj.randomObj   
	#self.__iniReaderObj = ConfigParser.ConfigParser()	
	
	self.__fsbootLib = FSBootLib.BootUtils(self.__fwConfigData,self.__applicationRunAttributesObj)
	self.__livet     = self.vtfContainer._livet
	#self.__logger.Info(self.globalVarsObj.TAG,  "Test Objective: Boot Block Tests") 
	self.__errorType  = self.vtfContainer.cmd_line_args.errorType#--->
	
	self.__eObj = EIMediator.ErrorInjectionClass()
	self.__threshold=IFSErrorInjectionLib.GetThresholdToInjectError(self.__fwConfigData,self.vtfContainer)
	self.__sdfsObj = SDFS.SDFS(self.__fwConfigData,self.vtfContainer)
	self.readonlymode = False
	self.errorInjected = False
	self.primaryMB = None
	self.secondaryMB = None	
	
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()	
	
        
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
	
    def __FileWrite(self):
	"""
	Description:
	ReWrite the Data of RW Files
	"""

	RWFiles=self.sctpUtilsObj.GetListOfRwFiles()
	fileChooseToWrite = self.__randomObj.choice(RWFiles)
	fileSize = self.sctpUtilsObj.GetFileSize(fileChooseToWrite)
	self.__logger.Info(self.globalVarsObj.TAG, "[__FileWrite] Writng File Id : 0x%x with file size : 0x%x" %(fileChooseToWrite, fileSize))
	fileBuffer=pyWrap.Buffer.CreateBuffer(fileSize, patternType=pyWrap.ALL_0, isSector=True)#(fileSize)
	self.sctpUtilsObj.ReadFileSystem( fileChooseToWrite, fileSize, fileBuffer) 
	self.sctpUtilsObj.WriteFileSystem(fileChooseToWrite, fileSize,fileBuffer) 
	return 
        
    def PFHandlerIFS(self, Blockstate, **kwargs):
	self.__logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS PF HANDLER *************')
	self.__logger.Info(self.globalVarsObj.TAG,  "Test objective: PF Error Injection On FileSystem(Pri or sec) on a random WL ") 
	self.WaypointRegObj.SetNoDict()
        try:
            self.DeregisterAllWaypoint() 
        except:
            pass
	global PFOccured,BlmGrownBadBlockArgs,FSCompaction
	self.RegisterBootWaypoints=False
	self.livetObj.UnregisterLivetCallback(self.livetObj.lcFlashProgramFail)
	self.waypointRegistering(self.RegisterBootWaypoints)
	self.livetObj.RegisterLivetCallback(self.livetObj.lcFlashProgramFail,OnProgramFailure)
	
	
	Flag=False
	FlagToGetRange=False
	FlagToCheckLastWL=False
	RandomChosenWL = None

	#self.__FileWrite()
        (primaryRWFsMbAddr,secondaryRWFsMbAddr)=self.__sdfsObj.GetRWFSMetablockAddress()
	assert primaryRWFsMbAddr!=[] and secondaryRWFsMbAddr!=[],"RW FS Metablock address returned by Diag is none "	
	CopyChoice="PRI"#self.__randomObj.choice(["PRI","SEC"])
	if CopyChoice=="PRI":
	    PrimaryFsMbAddr=primaryRWFsMbAddr
	    PhyAddr=self.sctpUtilsObj.TranslateMetaToPhysical(PrimaryFsMbAddr[0],True,self.__fwConfigData)[0]
	elif CopyChoice=="SEC":
	    SecondaryFsMbAddr=secondaryRWFsMbAddr
	    PhyAddr=self.sctpUtilsObj.TranslateMetaToPhysical(SecondaryFsMbAddr[0],True,self.__fwConfigData,)[0]
	
	    
	RandomChosenWL = None
	RandomChosenString = self.__randomObj.randint(0,4)#String value need to update
	 
	self.__logger.Info(self.globalVarsObj.TAG, "Current physical address of File System:%s"%PhyAddr)	
	RandomChosenWL = self.__randomObj.randint(0, self.__threshold)
	self.__logger.Info(self.globalVarsObj.TAG, "Changing the  wordline of FS to %d"%RandomChosenWL)
	self.__logger.Info(self.globalVarsObj.TAG, "Changing the  string of FS to %d"%RandomChosenString)
	address = (PhyAddr.die,PhyAddr.plane,PhyAddr.block, RandomChosenWL,RandomChosenString,0,0)
	PhyAddr.wordLine = RandomChosenWL
	PhyAddr.string = RandomChosenString

	try:
	    while PFOccured==False:# and self.__testRunObj.GetRemainingTimeInSeconds()!=0:
		self.__FileWrite()
		
		if self.primaryMB != None and not self.errorInjected:
		    physicalAddress = AddressTypes.PhysicalAddress()
		    physicalAddress.die = self.primaryMB[1]/self.__fwConfigData.planesPerDie
		    physicalAddress.plane = self.primaryMB[1]%self.__fwConfigData.planesPerDie
		    physicalAddress.block = self.primaryMB[0]
		    physicalAddress.wordLine = 0
		    physicalAddress.string = 0
		    for wordline in range(50,57):
			for string in range(4):
			    physicalAddress.string = string
			    physicalAddress.wordLine = wordline
			    self.__eObj.InjectProgramFailureError(errorPhyAddress=physicalAddress)
		    self.errorInjected = True
		    
	except:
	    if self.readonlymode:
		self.__logger.Info(self.globalVarsObj.TAG, "Card is in Read Only mode")
		x = self.__livet.GetPowerManager()
		x.PowerCycle(0,0,100)
		#self.__validationSpace.DoDownLoadAndFormat()
		#self.__init__(self.currCfg.variation.randomSeed,self.__testRunObj)
	    elif not PFOccured:
		raise TestError.TestFailError("IFSEI01","PF was injected but did not occur")
	    else:
		raise TestError.TestFailError("IFSEI01","Test failed with exception")
	#raise
	PFOccured=False
	FSCompaction=False
	#TODO
	#self.__livetFlash.ClearErrors(True)
	BlmGrownBadBlockArgs=None
        
        self.__logger.Info(self.globalVarsObj.TAG, "############ IFS PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    

    def ReadOnlyModeCallBackFunc(self,  args ): 
	"""
	This callback is called when card enters Read Only mode waypoint fires.
	"""
	self.globalVarsObj.readOnlyMode=True
	self.globalVarsObj.clearError=True
	self.__logger.Info(self.globalVarsObj.TAG, "Card in Read only mode.......")

	return True 

    def __doRandomHostWrites(self):
	    """
	    
	    """
	    import random
	    startLba = random.randrange(100,10000)
	    txlen = random.randrange(0x100,0x2000)
	    try:
		commandParam = [0,0]	    
		x = self.__ccmObj.Write(random.randrange(100,10000), txlen) #, commandParam= commandParam)
		
	    except:  # handle Write Abort in case  host.checkpowerfail=1
		#if(int(self.__livet.hcsPowerFail) != self.__sc.GetLastCommandStatus()):
		    #raise
		#else: #WA occurred update Card MAP sc
		    #self.__rwcObj.UpdateMapForUnPredictablePattern(commandParam[0],commandParam[1])
		self.dataTracking = self.__livet.GetDataTracking()
		self.dataTracking.UpdatePattern(startLba,txlen, self.__livet.dpUnpredictable)
		    
    
    def __InjectError(self,ErrorTypeChoosen):
	"""
	"""
	#TODO
	#utils =  ErrorInjectionLib.ErrorInjectionUtils.ErrorInjectionUtils(1234)
	controlDataLBADict =  self.__eiObj.GetHypotheticalLbaDict()
	errorLba =  controlDataLBADict['boot']
	flashOperation=self.__livet.foProgram
	if ErrorTypeChoosen == 'ef':
	    errorType=self.__livet.etEraseError 
	    flashOperation = self.__livet.foErase
	elif(ErrorTypeChoosen == "ea"):
	    errorType = self.__livet.etEraseAbort
	    flashOperation = self.__livet.foErase
	elif(ErrorTypeChoosen == 'ProgramFailure'):
	    errorType=self.__livet.etProgramError
	elif(ErrorTypeChoosen == "wa"):
	    errorType=self.__randomObj.choice([self.__livet.etPreProgramAbort, self.__livet.etPostProgramAbort, self.__livet.etProgramAbort])  
	    
	
	
	errorPersistence=self.__livet.epPermanent
	delayToOccurence= 0
	delayToRecovery=1 
	skipCount= self.__randomObj.choice([0,4])
	errorByteOffset =0
	errorByteMask =0
	self.__logger.Info(self.globalVarsObj.TAG, "[ERROR_INJECTION] : Setting logical trigger on Boot sector LBA 0x%X"%errorLba)
	errorDescription=(errorType,errorPersistence,delayToOccurence,delayToRecovery,errorByteOffset,errorByteMask)	
	self.__livet.GetFlash().SetLogicalTrigger(errorLba,flashOperation,skipCount,errorDescription)
	self.__logger.Info(self.globalVarsObj.TAG, "Error Injected on %s Boot Block"%((skipCount ==4 and  ["Primary"] or ["Secondary"])[0]))
	
	    

    def waypointRegistering(self,BlockState):
	if self.RegisterBootWaypoints:  
	    self.wayPointDict = {
	            "READ_ONLY_MODE" : [self.ReadOnlyModeCallBackFunc],
	    }	    
	else:
	    self.wayPointDict = {
	            "BLM_GROWN_BAD_BLOCK_ADDED" : [self.BLM_GROWN_BAD_BLOCK_ADDED_Funct],
	            #"FS_COMPACTION_AFTER_BLK_ALLOCATION" : [self.FS_COMPACTION_AFTER_BLK_ALLOCATIONcallback],
	            "READ_ONLY_MODE"          : [self.OnReadOnlyMode],
	            "FS_COMPACTION_BEFORE_BLK_ALLOCATION_SP" : [self.OnFSCompactionBefore],
	            "FS_COMPACTION_AFTER_BLK_ALLOCATION_SP" : [self.FS_COMPACTION_AFTER_BLK_ALLOCATIONcallback],
	            "FILE_WRITE"  : [self.OnFileWrite],
	            "SP_CONTROL_BLOCK_WRITE" : [self.OnFileWrite],
	            "READ_ONLY_MODE" : [self.ReadOnlyModeCallBackFunc],
	    }
			    
	self.WaypointRegObj.RegisterWP(self.wayPointDict)
	    
	    
    def OnReadOnlyMode(self,argdict):
	self.readonlymode = True
	pass    
	    
    def BLM_GROWN_BAD_BLOCK_ADDED_Funct(self,  args ):
	    """
	    Waypoint Call Back Function for Grown Bad blocks
	    """
	    global BlmGrownBadBlockArgs
	    self.__logger.Info(self.globalVarsObj.TAG, "BLM_GROWN_BAD_BLOCK_ADDED BankNum:0x%X BlockNum:0x%x"%(args[0],args[1]))
	    BlmGrownBadBlockArgs=args
	    return 0
    def OnFSCompactionBefore(self,args):
	return 
   
    
    def FS_COMPACTION_AFTER_BLK_ALLOCATIONcallback(self, args):
	    """
	    """
	    global FSCompaction
	    FSCompaction=True
	    physicalAddress = AddressTypes.PhysicalAddress()
	    physicalAddress.die = 0
	    #physicalAddress.plane = args[2]
	    physicalAddress.wordLine = 0
	    physicalAddress.string = 0
	    #physicalAddress.block = args[1]
	    if not self.errorInjected:
		for string in range(4):
		    physicalAddress.string = string
		    self.__eObj.InjectProgramFailureError(errorPhyAddress=physicalAddress)
		    self.errorInjected = True	
	    #self.__logger.Info("","FS_COMPACTION_AFTER_BLK_ALLOCATION_SP : bank:0x%X sourceMBA:0x%X destinationMBA:0x%X destinationPlane:0x%X" %(args[0],args[1],args[2],args[3]))
	    return 0     
    def OnFileWrite(self,args):
	
	planeno0 = args[1] >> 26
	block0 = args[1] & 0xFFFFFF
	planeno1 = args[2] >> 26
	block1 = args[2] & 0xFFFFFF
	shiftInWordline=8
	self.__logger.Info("","ON_FILE_WRITE planenum:0x%X blocknum:0x%X planenum1: 0x%X blocknum1 0x%X" %(planeno0,block0,planeno1,block1))
	self.EIBLockType=1#self.globalVarsObj.randomObj.choice([0, 1])
	if self.EIBLockType:
	    if self.primaryMB == None:
		self.__logger.Info("","Injecting Error On Primary FS BLOCK")
		self.primaryMB = (block0,planeno0)
		self.PhyAddr.block=self.primaryMB[0]
		self.PhyAddr.plane=self.primaryMB[1]
		self.PhyAddr.wordLine =  self.__randomObj.randint(shiftInWordline, self.__threshold)
		if self.PhyAddr.plane >1 :
		    self.PhyAddr.plane = self.primaryMB[1] % 2 
		    self.PhyAddr.die = self.primaryMB[1] /2 
	else:
	    if self.secondaryMB == None:
		self.__logger.Info("","Injecting Error On Secondary FS BLOCK")
		self.secondaryMB = (block1,planeno1)
		self.PhyAddr.block=self.secondaryMB[0]
		self.PhyAddr.plane=self.secondaryMB[1]
		self.PhyAddr.wordLine =  self.__randomObj.randint(0, self.__threshold)
		if self.PhyAddr.plane >1 :
		    self.PhyAddr.plane = self.secondaryMB[1] % 2
		    self.PhyAddr.die = self.secondaryMB[1] /2 
	
	self.__logger.Info("","ON_FILE_WRITE planenum:0x%X blocknum:0x%X planenum1: 0x%X blocknum1 0x%X" %(planeno0,block0,planeno1,block1))
	if not self.errorInjected:
	    self.__eObj.InjectProgramFailureError(errorPhyAddress=self.PhyAddr, 
	                                      skipCount=0, 
	                                      errorDescription=(), 
	                                      callbackFunction=None)
	    self.errorInjected = True	    
	
	return
    
    def PFHandlerBOOT(self, Blockstate, **kwargs):
	self.RegisterBootWaypoints=True
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	self.waypointRegistering(self.RegisterBootWaypoints)               
	self.__logger.Info(self.globalVarsObj.TAG, '************* ENTERING Boot PF HANDLER *************')	
	try:
	    self.__doRandomHostWrites()
	    ErrorTypeChoosen=kwargs['combination_']['ErrorType']
	    self.__InjectError(ErrorTypeChoosen)
	    try:
		self.__fsbootLib.TriggerFSCompaction( ErrorTypeChoosen)#utils.GetHypotheticalLbaDict
	    except:
		pass
	
	except:
	    #if(TestProcedure.cls_readOnlyMode):
		#raise Error.ReadOnlyModeError("Card Entered Read only mode due to Error Injections")
	    #else:
	    raise 
       
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()    	
      
        
        if(not self.globalVarsObj.injectedErrorOccurred):
            self.__logger.Info(self.globalVarsObj.TAG, "PF wasn't detected")
            self.__logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "PF wasn't detected"
        
        startLba=0
	txlen=0x8
	for i in range(0,10):
	    try:
		self.__ccmObj.Write(startLba, txlen)
	    except:
		self.globalVarsObj.readOnlyMode=True
	    startLba+=txlen
        
        self.__logger.Info(self.globalVarsObj.TAG, "############ BOOT PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')  
	
def OnProgramFailure(Package,addr):
    """
    Model Call Back Function for Program Failure
    """
    global PFOccured
    PFOccured = True
    #Record the test event: 
    return 0 
	

        
