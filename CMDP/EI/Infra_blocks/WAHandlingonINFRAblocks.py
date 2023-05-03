import Constants
import Core.ValidationError as ValidationError
import SctpUtils
import SDUtils
import Extensions.CVFImports as pyWrap
import CMDP_History as History
global WAOccured,BlmGrownBadBlockArgs,FSCompaction
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
#import py_sfcl
import IFSErrorInjectionLib as IFSErrorInjectionLib
import SDFS
FSCompaction=False
WAOccured=False
BlmGrownBadBlockArgs=None
g_logger = None



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
	self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars()
	self.__ccmObj         = self.globalVarsObj.ccmObj	
	self.__fwConfigData=FwConfig.FwConfig(self.globalVarsObj.vtfContainer)
	self.__addrTranslatnObj=AddressTranslation.AddressTranslator(self.globalVarsObj.vtfContainer)	
	self.WaypointRegObj = self.globalVarsObj.WayPointObj
	self.utilsObj       = Utils.Utils()    
	self.sctpUtilsObj = SctpUtils.SctpUtils()
	self.SCTPObj = SCTPcls.SctpInterface()
	self.__threshold=IFSErrorInjectionLib.GetThresholdToInjectError(self.__fwConfigData,self.globalVarsObj.vtfContainer)
	self.__sdfsObj = SDFS.SDFS(self.__fwConfigData,self.globalVarsObj.vtfContainer)
	self.__applicationRunAttributesObj = "WA"
	self.__fsbootLib = FSBootLib.BootUtils(self.__fwConfigData,self.__applicationRunAttributesObj)
	self.__eObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)	
	self.PhyAddr =  AddressTypes.PhysicalAddress()

        self.ResetVariables()      

        
        
    def ResetVariables(self):
        self.__logger = self.globalVarsObj.logger 
	
	self.vtfContainer = self.globalVarsObj.vtfContainer	
	self.__randomObj   = self.globalVarsObj.randomObj   
	self.__livet     = self.vtfContainer._livet
	self.__errorType  = self.vtfContainer.cmd_line_args.errorType
	
	self.errorInjected = False
	self.romode = False
	self.primaryMB = None
	self.secondaryMB = None	
	self.FSCompaction = False
	self.waInjected = False
		
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()		
	
	
    def waypointRegistering(self,BlockState):
	if self.RegisterBootWaypoints:  
	    self.wayPointDict = {
	        "READ_ONLY_MODE"         : [self.ReadOnlyModeCallBackFunc],
	    }	    
	else:
	    self.wayPointDict = {
	        "BLM_GROWN_BAD_BLOCK_ADDED" : [self.BLM_GROWN_BAD_BLOCK_ADDED_Funct],
	        "READ_ONLY_MODE"            : [self.ReadOnlyModeCallBackFunc],
	        "FS_COMPACTION_AFTER_BLK_ALLOCATION_SP" : [self.FS_COMPACTION_AFTER_BLK_ALLOCATIONcallback],
	        "FILE_WRITE"                : [self.OnFileWrite],
	        "SP_CONTROL_BLOCK_WRITE"    : [self.OnspFileWrite],
	        "UECC_DETECTED"             : [],
	    }
			    
	self.WaypointRegObj.RegisterWP(self.wayPointDict)
	    
    def OnspFileWrite(self,argDict):
	   pass	 
	 
    def OnFileWrite(self,args):
	#"fileType","mba0","mba1", "writePtr0","writePtr1"
	planeno0 = args[1] >> 26
	block0 = args[1] & 0xFFFFFF
	planeno1 = args[2] >> 26
	block1 = args[2] & 0xFFFFFF
	#Choose either prim or sec block to inject error
	shifInWordline=8
	self.EIBLockType=self.globalVarsObj.randomObj.choice([0, 1])
	if self.EIBLockType:
	    if self.primaryMB == None:
		self.__logger.Info("","Injecting Error On Primary FS BLOCK")
		self.primaryMB = (block0,planeno0)
		self.PhyAddr.block=self.primaryMB[0]
		self.PhyAddr.plane=self.primaryMB[1]
		self.PhyAddr.wordLine =  self.__randomObj.randint(shifInWordline+1, self.__fwConfigData.wordLinesPerPhysicalBlock-1)
		if self.PhyAddr.plane >1 :
		    self.PhyAddr.plane = self.primaryMB[1] % 2 
		    self.PhyAddr.die = self.primaryMB[1] /2 
	else:
	    if self.secondaryMB == None:
		self.__logger.Info("","Injecting Error On Secondary FS BLOCK")
		self.secondaryMB = (block1,planeno1)
		self.PhyAddr.block=self.secondaryMB[0]
		self.PhyAddr.plane=self.secondaryMB[1]
		self.PhyAddr.wordLine =  self.__randomObj.randint(0, self.__fwConfigData.wordLinesPerPhysicalBlock-shifInWordline-1)
		if self.PhyAddr.plane >1 :
		    self.PhyAddr.plane = self.secondaryMB[1] % 2
		    self.PhyAddr.die = self.secondaryMB[1] /2 
	
	self.__logger.Info("","ON_FILE_WRITE planenum:0x%X blocknum:0x%X planenum1: 0x%X blocknum1 0x%X" %(planeno0,block0,planeno1,block1))
	if not self.waInjected:
	    choosen = self.globalVarsObj.randomObj.choice(["wrab","prwa","powa"])
	    self.__eObj.InjectWriteAbortError(errorType=choosen,errorLba=None, errorPhyAddress=self.PhyAddr, 
	                                      skipCount=0, 
	                                      errorDescription=(), 
	                                      callbackFunction=None)
	    self.waInjected = True
	    self.__eObj.isWATriggered = True    
	return   
    
    def FS_COMPACTION_AFTER_BLK_ALLOCATIONcallback(self, args):
	self.FSCompaction=True
	return
    
    def OnFSCompactionBefore(self,args):
	return     


        
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
	
    def OnWriteAbort(self,Package,Addr):
	global WAOccured
	WAOccured = True
	#self.globalVarsObj.APEI =True
	return
    
    def OnPreWriteAbort(self,Package,Addr):
	global WAOccured
	WAOccured = True
	#self.globalVarsObj.APEI =True

	return	
    def OnPostWriteAbort(self,Package,Addr):
	global WAOccured
	WAOccured = True
	#self.globalVarsObj.APEI =True
	return	
    
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
            
    def WAHandlerIFS(self, Blockstate, **kwargs):
        self.__logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS WA HANDLER *************')
	try:
	    self.DeregisterAllWaypoint()
	except:
	    pass	
	self.__logger.Info(self.globalVarsObj.TAG,  "Test objective: WA Error Injection On FileSystem(Pri or sec) on a random WL ") 
	self.WaypointRegObj.SetNoDict()

	"""
        Exceutes the test.
        """ 
	global WAOccured,BlmGrownBadBlockArgs
	self.RegisterBootWaypoints=False
	self.waypointRegistering(self.RegisterBootWaypoints)	
	self.__eObj.RegisterWriteAbortCallback(self.OnWriteAbort)
	self.__eObj.RegisterPreWriteAbortCallback(self.OnPreWriteAbort)
	self.__eObj.RegisterPostWriteAbortCallback(self.OnPostWriteAbort)
	Flag=False
	FlagToGetRange=False
	FlagToCheckLastWL=False
	RandomChosenWL = None
	    
	(primaryRWFsMbAddr,secondaryRWFsMbAddr)=self.__sdfsObj.GetRWFSMetablockAddress()
	assert primaryRWFsMbAddr!=[] and secondaryRWFsMbAddr!=[],"RW FS Metablock address returned by Diag is none "	
	CopyChoice="PRI"#self.__randomObj.choice(["PRI","SEC"])
	self.__FileWrite()	
	if CopyChoice=="PRI":
	    PrimaryFsMbAddr=primaryRWFsMbAddr
	    PhyAddr=self.sctpUtilsObj.TranslateMetaToPhysical(PrimaryFsMbAddr[0],True,self.__fwConfigData)[0]
	elif CopyChoice=="SEC":
	    SecondaryFsMbAddr=secondaryRWFsMbAddr
	    PhyAddr=self.sctpUtilsObj.TranslateMetaToPhysical(SecondaryFsMbAddr[0],True,self.__fwConfigData,)[0]
			

	
	RandomChosenWL = None
	RandomChosenString = self.__randomObj.randint(0,4)
	
	self.__logger.Info(self.globalVarsObj.TAG, "Current physical address of File System:%s"%str(self.PhyAddr))	
	RandomChosenWL = self.__randomObj.randint(0, self.__threshold)
	self.__logger.Info(self.globalVarsObj.TAG, "Changing the  wordline of FS to %d"%RandomChosenWL)
	self.__logger.Info(self.globalVarsObj.TAG, "Changing the  string of FS to %d"%RandomChosenString)
	if self.__fwConfigData.isBiCS:
	    self.__logger.Info(self.globalVarsObj.TAG, "Changing the  String of FS to %d"%RandomChosenString)	
	#address = (self.PhyAddr.die,self.PhyAddr.plane,self.PhyAddr.block, RandomChosenWL,RandomChosenString,0,0)
	self.PhyAddr.wordLine = RandomChosenWL
	self.PhyAddr.string = RandomChosenString
	self.PhyAddr.wordLine =  self.__randomObj.randint(9, self.__fwConfigData.wordLinesPerPhysicalBlock)
	if not self.waInjected:
	    self.__eObj.InjectWriteAbortError(errorType="wrab",errorLba=None, errorPhyAddress=self.PhyAddr, 
	                                      skipCount=0, 
	                                      errorDescription=(), 
	                                      callbackFunction=None)

	try:
	    while WAOccured==False:# and self.__testRunObj.GetRemainingTimeInSeconds()!=0:
		self.__FileWrite()
	    if WAOccured==False:# and self.__testRunObj.GetRemainingTimeInSeconds()==0:
		raise TestError.TestFailError("","Halting the test as it ran longer than expected!!!")	
	    IFSErrorInjectionLib.ReadAllValidFiles()
	    RandWrites=self.__randomObj.randint(10,50)
	    self.__logger.Info(self.globalVarsObj.TAG, "Issuing Random  Host Writes")
	    #self.__ccmObj.DoRandomWrites(RandWrites,randomObj=self.__randomObj)
	    startlba = 0
	    txlen = 0x30
	    for i in range(0,RandWrites):
		self.__ccmObj.Write(startlba , txlen)
		startlba += self.__randomObj.randint(10,50)
		txlen = self.__randomObj.randint(10,50)
	    # Converting metablock number to physical address for Multi Metaplane
	    
	    if not self.__fwConfigData.isBiCS:
		if ((self.__fwConfigData.MMP) and (BlmGrownBadBlockArgs!=None)):
		    metaBlockNumber = BlmGrownBadBlockArgs[1]
		    MBAddress=self.__addrTranslatnObj.TranslateMBNumtoMBA(metaBlockNumber)
		    badBlockPhysicalAddress = (self.__addrTranslatnObj.TranslateMetaToPhy(MBAddress)[0])
		    BlmGrownBadBlockArgs = list(BlmGrownBadBlockArgs)
		    BlmGrownBadBlockArgs[1] = badBlockPhysicalAddress.block
		    BlmGrownBadBlockArgs = tuple(BlmGrownBadBlockArgs) 		
		if (BlmGrownBadBlockArgs==None) or ( self.PhyAddr.block!=BlmGrownBadBlockArgs[1]):
		    raise TestError.TestFailError("","PF affected Block :0x%x not added to  File 226"%self.PhyAddr.block)	       
	except:
	    if self.romode:
		self.__logger.Info(self.globalVarsObj.TAG, "Card is in Read Only mode")
		x = self.__livet.GetPowerManager()
		x.PowerCycle(0,0,100)
		
		ErrorManager = self.vtfContainer.device_session.GetErrorManager()
		self.vtfContainer.cmd_mgr.ClearExceptionNotification()
		ErrorManager.ClearAllErrors() 	    		

	    elif not WAOccured:
		return ("WA was injected but did not occur")
	    else:
		self.__logger.Info("IFSEI02","WA was occucred")
		
	WAOccured=False
	self.FSCompaction=False
	#TODO
	#self.__livetFlash.ClearErrors(True)
	BlmGrownBadBlockArgs=None	
	self.__eObj.isWATriggered = True	
	 	
        
        self.__logger.Info(self.globalVarsObj.TAG, "############ IFS WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def __FileWrite(self):
	    """
	    Description:
	    ReWrite the Data of RW Files
	    """
	    global WAOccured
	    RWFiles=self.sctpUtilsObj.GetListOfRwFiles()
	    fileChooseToWrite = self.__randomObj.choice(RWFiles)
	    fileSize = self.sctpUtilsObj.GetFileSize(fileChooseToWrite)
	    self.__logger.Info(self.globalVarsObj.TAG, "[__FileWrite] Writng File Id : 0x%x with file size : 0x%x" %(fileChooseToWrite, fileSize))
	    fileBuffer=pyWrap.Buffer.CreateBuffer(fileSize, patternType=pyWrap.ALL_1, isSector=True)#(fileSize)
	    self.sctpUtilsObj.ReadFileSystem(fileChooseToWrite, fileSize,fileBuffer) 
	    self.sctpUtilsObj.WriteFileSystem(fileChooseToWrite, fileSize,fileBuffer) 
	    if WAOccured==True:
		self.__logger.Info(self.globalVarsObj.TAG, "Reading the File which lead to PF")
		self.sctpUtilsObj.ReadFileSystem( fileChooseToWrite, fileSize,fileBuffer) 
		
	    return  
	
     
    def BLM_GROWN_BAD_BLOCK_ADDED_Funct(self,  args ):
	global BlmGrownBadBlockArgs
	self.__logger.Info(self.globalVarsObj.TAG, "BLM_GROWN_BAD_BLOCK_ADDED BankNum:0x%X BlockNum:0x%x"%(args[0],args[1]))
	BlmGrownBadBlockArgs=args
	return
       
    def FS_COMPACTION_AFTER_BLK_ALLOCATIONcallback(self, args):
	self.FSCompaction=True
	return        

    
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
	    self.dataTracking = self.__livet.GetDataTracking()
	    self.dataTracking.UpdatePattern(startLba,txlen, self.__livet.dpUnpredictable)
		
       
    def __InjectError(self,ErrorTypeChoosen):
	#utils =  ErrorInjectionLib.ErrorInjectionUtils.ErrorInjectionUtils(1234)
	controlDataLBADict =  self.__eObj.GetHypotheticalLbaDict()
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
	elif(ErrorTypeChoosen == "WriteAbort"):
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
	

    
    def WAHandlerBOOT(self, Blockstate, **kwargs):
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
            self.__logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.__logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "WA wasn't detected"
        
           
        
        self.__logger.Info(self.globalVarsObj.TAG, "############ BOOT WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    
    

          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
