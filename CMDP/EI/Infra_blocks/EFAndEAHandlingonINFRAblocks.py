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
#import py_sfcl
import IFSErrorInjectionLib as IFSErrorInjectionLib
import SDFS
import ErrorInjectorLib
import WayPointHandler

EraseOccured=False
EraseAbort=False
g_waypointObj=None
BlmGrownBadBlockArgs=[]
ListOfblocksTobeAddedToFile226=[]
g_cardEnteredInROM=False
FSCompaction=False

class EFhandler:
    
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
	self.vtfContainer=self.globalVarsObj.vtfContainer
	#self.__eiObjUtil = EIMediator.ErrorInjectionUtilsClass(self.globalVarsObj)
	self.eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
	self.__fwConfigData=FwConfig.FwConfig(self.globalVarsObj.vtfContainer)
	self.__addrTranslatnObj=AddressTranslation.AddressTranslator(self.globalVarsObj.vtfContainer)	
	
	self.WaypointRegObj = self.globalVarsObj.WayPointObj
	self.utilsObj       = Utils.Utils()    
	self.sctpUtilsObj = SctpUtils.SctpUtils()
	self.SCTPObj = SCTPcls.SctpInterface()
	
	self.eiObj.RegisterEraseFailureCallback(self.OnEraseFailure)
	self.eiObj.RegisterEraseAbortCallback(self.OnEraseAbort)
	self.eiObj.RegisterPreEraseAbortCallback(self.OnPreEraseAbort)
	self.eiObj.RegisterPostEraseAbortCallback(self.OnPostEraseAbort)

        self.ResetVariables()
    
    
    def ResetVariables(self):
	
	self.__applicationRunAttributesObj = self.vtfContainer.cmd_line_args
	self.__logger= self.globalVarsObj.logger 
	self.__fwConfigData=FwConfig.FwConfig(self.globalVarsObj.vtfContainer)
	

	self.__addrTranslatnObj=AddressTranslation.AddressTranslator(self.globalVarsObj.vtfContainer) 

	self.__testRunObj = self.globalVarsObj.vtfContainer.cmd_line_args
	self.__randomObj   = self.globalVarsObj.randomObj 
	self.__logger.Info(self.globalVarsObj.TAG,  "Test objective:  Erase Failure or Abort error injection on Primary or secondary FileSystem After Compaction or EF/Pre-EA/Post-EA During PF handling") 
	self.__livet=self.globalVarsObj.vtfContainer._livet


	self.__threshold=IFSErrorInjectionLib.GetThresholdToInjectError(self.__fwConfigData,self.globalVarsObj.vtfContainer)
	self.__errorType  = self.vtfContainer.cmd_line_args.errorType

	#Varibales neeed to use in "BLOCK_MANAGER_DEDICATED_BLOCK_ALLOCATED" callback
	self.__EraseErrorToInject     = self.globalVarsObj.randomObj.choice(["EF","EA"])
	self.__PhyAddrDedicatedFblMb0 = None
	self.__PhyAddrDedicatedFblMb1 = None
	self.__ErrorInjected          = False
	self.__ErrorOccurred          = False
	self.primaryMB                = None
	self.secondaryMB              = None

	self.__logger=self.__logger
	global g_waypointObj
	g_waypointObj=self

	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()
	
        
    def waypointRegistering(self,BlockState):
	if self.RegisterBootWaypoints:  
	    self.wayPointDict = {
	            "READ_ONLY_MODE" : [self.ReadOnlyModeCallBackFunc],
	    }	    
	else:
	    self.wayPointDict = {
	            "BLOCK_MANAGER_DEDICATED_BLOCK_ALLOCATED" : [self.BLOCK_MANAGER_DEDICATED_BLOCK_ALLOCATEDcallback],
	            "FS_COMPACTION_AFTER_BLK_ALLOCATION" : [],
	            "FILE_WRITE"     : [self.OnFileWrite],
	            "EPWR_START"     : [],
	            "EPWR_COMPLETE"  : [],	
	            "READ_ONLY_MODE" : [self.ReadOnlyModeCallBackFunc]
	            }
			    
	self.WaypointRegObj.RegisterWP(self.wayPointDict)
	
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
    def InjectEraseError(self,args):
	"""
	"""	
		    
	if self.__ErrorInjected == False and not self.__ErrorOccurred:
	    self.__logger.Info(self.globalVarsObj.TAG, "Injecting Erase Error either EF/EA error which is chosen Randomly")
	    if (not self.__PhyAddrDedicatedFblMb0==None ) and self.__PhyAddrDedicatedFblMb0.block==args[1]:
		self.__logger.Info(self.globalVarsObj.TAG, "Injecting %s to 0th block of dedicated FBL which is :0x%x"%(self.__EraseErrorToInject,self.__PhyAddrDedicatedFblMb0.block))
		PhyAddr=self.__PhyAddrDedicatedFblMb0

	    elif (not self.__PhyAddrDedicatedFblMb1==None ) and self.__PhyAddrDedicatedFblMb1.block==args[1]:
		self.__logger.Info(self.globalVarsObj.TAG, "Injecting %s to 1st block of dedicated FBL which is :0x%x"%(self.__EraseErrorToInject,self.__PhyAddrDedicatedFblMb1.block))
		PhyAddr=self.__PhyAddrDedicatedFblMb1

	    else:
		self.__logger.Info(self.globalVarsObj.TAG, "Block obtained from the BLOCK_MANAGER_DEDICATED_BLOCK_ALLOCATEDcallback waypoint is not same as in Dedicated FBL Diag")
		PhysicalBlocks=self.__livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(args[1] & 0x1FFF,args[0])
		(chip,die,plane,block)=self.__randomObj.choice(list(PhysicalBlocks))
		PhyAddr=AddressTypes.PhysicalAddress()
		if self.__fwConfigData.isBiCS:
		    (PhyAddr.chip,PhyAddr.die,PhyAddr.plane,PhyAddr.block,PhyAddr.wordLine,PhyAddr.string,PhyAddr.mlcLevel,PhyAddr.eccPage) = (chip,die,plane,block,0,0,0,0)
		else:
		    (PhyAddr.chip,PhyAddr.die,PhyAddr.plane,PhyAddr.block,PhyAddr.wordLine,PhyAddr.mlcLevel,PhyAddr.eccPage) = (chip,die,plane,block,0,0,0)

	    if self.__fwConfigData.isBiCS:
		address = (PhyAddr.die,PhyAddr.plane,PhyAddr.block, PhyAddr.wordLine, PhyAddr.string, PhyAddr.mlcLevel,PhyAddr.eccPage)
	    else:
		address = (PhyAddr.die,PhyAddr.plane,PhyAddr.block, PhyAddr.wordLine, PhyAddr.mlcLevel,PhyAddr.eccPage)
	    if self.__EraseErrorToInject=="EF":
		#IFSErrorInjectionLib.InjectEFOnPhysicalLocation(PhyAddr.chip,address)
		self.eiObj.InjectEraseFailureError(errorLba=None, errorPhyAddress=PhyAddr, 
		                                   skipCount=0, 
		                                   errorDescription=(), 
		                                   callbackFunction=None)
	    else:
		errorType=self.__randomObj.choice([self.__livet.etEraseAbort,self.__livet.etPreEraseAbort,self.__livet.etPostEraseAbort])
		#IFSErrorInjectionLib.InjectEAOnPhysicalLocation(errorType,PhyAddr.chip,address)
		self.eiObj.InjectEraseAbortError(errorType="erab", errorLba=None, 
		                                 errorPhyAddress=PhyAddr, 
		                                 skipCount=0, 
		                                 errorDescription=(), 
		                                 callbackFunction=None)
	    self.__ErrorInjected=True
	return


    def BLOCK_MANAGER_DEDICATED_BLOCK_ALLOCATEDcallback(self, args):
	"""
	"""
	global g_waypointObj
	#self.__logger.Info(self.globalVarsObj.TAG, "BLOCK_MANAGER_DEDICATED_BLOCK_ALLOCATED Waypoint hit BankNum:0x%x,MBNum:0x%x"%(args[0],args[1]))
	self.InjectEraseError(args)
	return 0	    

    def OnFileWrite(self,args):
	planeno0 = args[1] >> 26
	block0 = args[1] & 0xFFFFFF
	planeno1 = args[2] >> 26
	block1 = args[2] & 0xFFFFFF
	if self.primaryMB == None:
	    self.primaryMB = (block0,planeno0)
	if self.secondaryMB == None:
	    self.secondaryMB = (block1,planeno1)
	self.__logger.Info("","ON_FILE_WRITE planenum:0x%X blocknum:0x%X planenum1: 0x%X blocknum1 0x%X" %(planeno0,block0,planeno1,block1))
	return    

    def OnEraseFailure(self, package,addr):
	"""
	Model Call Back Function for Program Failure
	"""
	global EraseOccured,ListOfblocksTobeAddedToFile226
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")
	self.__logger.Info(self.globalVarsObj.TAG, "--- %s -- event occured at ->Package = [0x%X], Address = %s"%("Erase_Failure",package,addr))
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")  
	EraseOccured = True
	ListOfblocksTobeAddedToFile226.append(addr[2])
	return 0

    def OnEraseAbort(self, package,addr):
	"""
	Model Call Back Function for Program Failure
	"""
	global EraseOccured,EraseAbort
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")
	self.__logger.Info(self.globalVarsObj.TAG, "--- %s -- event occured at ->Package = [0x%X], Address = %s"%("Erase_Abort",package,addr))
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")  
	EraseOccured = True
	self.__ErrorOccurred = True
	EraseAbort=True
    #Record the test event: 
	return 0

    def OnPreEraseAbort(self, package,addr):
	"""
	Model Call Back Function for Program Failure
	"""
	global EraseOccured,EraseAbort
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")
	self.__logger.Info(self.globalVarsObj.TAG, "--- %s -- event occured at ->Package = [0x%X], Address = %s"%("PreErase_Abort",package,addr))
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")  
	EraseOccured = True
	EraseAbort=True
	#Record the test event: 
	return 0
    def OnPostEraseAbort(self, package,addr):
	"""
	Model Call Back Function for Program Failure
	"""
	global EraseOccured,EraseAbort
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")
	self.__logger.Info(self.globalVarsObj.TAG, "--- %s -- event occured at ->Package = [0x%X], Address = %s"%("PostErase_Abort",package,addr))
	self.__logger.Info(self.globalVarsObj.TAG, "#################################################################################")  
	EraseOccured = True
	EraseAbort=True
	#Record the test event: 
	return 0
	

        
    def EFAndEAHandlerIFS(self, Blockstate, **kwargs):
	self.__logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS EF/EA HANDLER *************')
        try:
            self.DeregisterAllWaypoint()
	    
	    
        except:
            pass
	
	self.RegisterBootWaypoints=False
	#self.livetObj.UnregisterLivetCallback(self.livetObj.lcFlashProgramFail)
	self.waypointRegistering(self.RegisterBootWaypoints)
	self.eiObj.RegisterEraseFailureCallback(self.OnEraseFailure)
	self.eiObj.RegisterEraseAbortCallback(self.OnEraseAbort)
	self.eiObj.RegisterPreEraseAbortCallback(self.OnPreEraseAbort)
	self.eiObj.RegisterPostEraseAbortCallback(self.OnPostEraseAbort)	
	
	
	
	global EraseOccured,BlmGrownBadBlockArgs,ListOfblocksTobeAddedToFile226,EraseAbort,g_cardEnteredInROM,FSCompaction
	self.WaypointRegObj.SetNoDict()
	totalSpareBlockCount, listOfSLCMetaBlocksInFBL, listOfMLCMetaBlocksInFBL, self.listOfDedicatedFBLMetaBlocks = self.sctpUtilsObj.GetSpareBlockListInfo()

	RandChoice=self.__randomObj.choice(["EraseError_AfterCompaction","EraseError_AfterPF"])
	if RandChoice=="EraseError_AfterCompaction":
	    self.__logger.Info(self.globalVarsObj.TAG, "Erase Error After Compaction of the Block")
	else:
	    self.__logger.Info(self.globalVarsObj.TAG, "Injecting Erase Error in the PF Handling")
	    Flag=False

	    FlagToGetRange=False
	    FlagToCheckLastWL=False



	try:
	    while EraseOccured==False :
		totalSpareBlockCount, listOfSLCMetaBlocksInFBL, listOfMLCMetaBlocksInFBL, self.listOfDedicatedFBLMetaBlocks = self.sctpUtilsObj.GetSpareBlockListInfo()
		self.__FileWrite()
		totalSpareBlockCount, listOfSLCMetaBlocksInFBL, listOfMLCMetaBlocksInFBL, self.listOfDedicatedFBLMetaBlocks = self.sctpUtilsObj.GetSpareBlockListInfo()
		
	except:
	    LastCommandStatusABort=False


	if EraseOccured==False and True==0:
	    raise ValidationError.TestFailError("","Halting the test as it ran longer than expected waiting for Erase Error injected on physical address:%s !!!"%PhyAddr)


	if not self.__fwConfigData.isBiCS:
	    if ((self.__fwConfigData.MMP) and (len(BlmGrownBadBlockArgs))):
		for index in range(0,len(ListOfblocksTobeAddedToFile226)):
		    metaBlockNumber = BlmGrownBadBlockArgs.pop(0)
		    MBAddress=self.__addrTranslatnObj.TranslateMBNumtoMBA(metaBlockNumber)
		    badBlockPhysicalAddress = (self.__addrTranslatnObj.TranslateMetaToPhy(MBAddress)[0])	
		    BlmGrownBadBlockArgs.append(badBlockPhysicalAddress.block)

	    for Blk in ListOfblocksTobeAddedToFile226:
		if (BlmGrownBadBlockArgs==[] or (not Blk in BlmGrownBadBlockArgs)) and (EraseAbort==False) and g_cardEnteredInROM==False:
		    raise ValidationError.TestFailError("","PF/EF Affected FS block :0x%x not added to GBB File "%Blk)
	EraseOccured=False
	EraseAbort=False
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()
	BlmGrownBadBlockArgs=[]
	ListOfblocksTobeAddedToFile226=[]
	self.__ErrorInjected=False
	self.__PhyAddrDedicatedFblMb0=None
	self.__PhyAddrDedicatedFblMb1=None
	g_cardEnteredInROM=False
	FSCompaction=False
		    
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
	self.logger.Info(self.globalVarsObj.TAG, "Card in Read only mode.......")
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
	   controlDataLBADict =  self.eiObj.GetHypotheticalLbaDict()
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
	   

    def EFAndEAHandlerBOOT(self, Blockstate, **kwargs):
	self.RegisterBootWaypoints=True
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	self.__fsbootLib = FSBootLib.BootUtils(self.__fwConfigData,self.__applicationRunAttributesObj)
	#self.WaypointRegObj.RegisterWP(self.wayPointDict)
	self.waypointRegistering(self.RegisterBootWaypoints)               
	self.__logger.Info(self.globalVarsObj.TAG, '************* ENTERING Boot PF HANDLER *************')	
	try:
	    self.__doRandomHostWrites()
	    ErrorTypeChoosen=self.globalVarsObj.randomObj.choice(['ef', 'ea'])
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
            self.__logger.Info(self.globalVarsObj.TAG, "EF/EA wasn't detected")
            self.__logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "EF/EA wasn't detected"
        
           
        
        self.__logger.Info(self.globalVarsObj.TAG, "############ BOOT EF/EA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')  
	


        
