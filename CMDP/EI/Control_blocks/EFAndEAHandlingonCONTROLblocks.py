import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import SctpUtils
import WaypointReg
import Extensions.CVFImports as pyWrap
from collections import defaultdict
import CMDP_History as History
import EIMediator
import FwConfig as FwConfig
import Utils as Utils
import ValidationLib.AddressTypes as AddressTypes
import CommonCodeManager as CCM
import FWConfigData as FWConfigData
import ConfigParser
from argparse import Namespace
import FileData
import random
import os
from struct import unpack, pack


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
	self.__globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
	self.__optionValues = self.__globalVarsObj.vtfContainer.cmd_line_args	
	self.__randomObj = self.__globalVarsObj.randomObj	
	self.__fwConfigObj = FwConfig.FwConfig(self.__globalVarsObj.vtfContainer)
	#if self.__globalVarsObj.ccmObj.vtfContainer.isModel:
	#Root = self.livet.GetRootObject()
	self.vtfContainer=self.__globalVarsObj.vtfContainer
	#Livet initializations
	self.__livetObj = self.vtfContainer._livet
	self.__livetFlash = self.__livetObj.GetFlash() 	
	
	# Library modules initializations
	self.__optionValues.transferLengthRange = [1, self.__fwConfigObj.slcMBSize] 
	self.__file21Object = FileData.ConfigurationFile21Data(self.__globalVarsObj.vtfContainer)
	self.__fileObject = FileData.FileData(self.__globalVarsObj.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()
	self.__waypointRegObj = self.__globalVarsObj.WayPointObj#WaypointReg.WaypointReg(self.__livetObj, self.logger, self.__globalVarsObj)
	self.__eiObj = EIMediator.ErrorInjectionClass()	
	self.__paddedWLs = 8
	
	self.__logger = self.__globalVarsObj.logger
	self.__ccmObj = self.__globalVarsObj.ccmObj
	self.__sctpUtilsObj = SctpUtils.SctpUtils()	
	#if self.currCfg.system.isModel:
	#Add required waypoints below and its call back
	self.__wayPointDict = {
                    "READ_ONLY_MODE"        : [self.OnReadOnlyMode],
                    "MIP_BLOCK_TRANSITION"  : [self.OnMipBlockTransition],
                    "MB_ADDED_RETIRED_LIST" : [self.OnMBAddedRetiredList],
                    #"GATBLOCKVFCZERO"      : [self.OnGatBlockVfcZero]
                    "GAT_BEFORE_ERASE_OF_ALLOCATED_BLOCK" : [self.OnGATBeforeEraseOfAllocatedBlk],
                    "GAT_BLOCK_TRANSITION"  : [self.OnGATBlockTransition],
	            "MIP_BLOCK_TRANSITION_AFTER"        : [self.OnMipBlockTransitionAfter], 
	            "MIP_BLOCK_TRANSITION_BEFORE"       : [self.OnMipBlockTransitionBefore],
         }
	
	self.__waypointRegObj.RegisterWP(self.__wayPointDict)  

        self.ResetVariables()
	
	
        
    def ResetVariables(self):
	# Variable initialization  
	self.__numGATBlocks = self.__file14Object['numOfGATBlocks']	
	self.dataTracking = self.__livetObj.GetDataTracking()	 
		 
	self.__maxLba = self.__fwConfigObj.maxLba	# Max LBA 	
	self.__sectorsPerMetaBlock = self.__fwConfigObj.slcMBSize # MB size
	self.__metPageSize = self.__fwConfigObj.metaPageSize # Meta page size
	self.__wordLineSize = self.__metPageSize * self.__fwConfigObj.stringsPerBlock # Word line size
	self.__sizeOfLG = self.__fwConfigObj.sectorsPerLg  # LG size	
	self.__maxWrites = self.__sectorsPerMetaBlock/ self.__wordLineSize
	self.__numOfLgs = self.__maxLba/self.__fwConfigObj.sectorsPerLg # Num of LGs in card	
	self.__wordLineSize = self.__fwConfigObj.metaPageSize * self.__fwConfigObj.stringsPerBlock	
	self.__ROModeReason  = None
	self.__ROModePayload = None	
	self.__ReadOnlyMode  = False	
	self.__errorOccurred = False
	self.__numberOfSecWritten = 0
	self.__gatBlockExchange =  False
	self.__mipBlockExchanged = False
	self.__errorInjected = False
	self.__errorBlock = []	
	self.__efOccurred = False 	
	self.__errorCode = 0
	self.__eraseRequestedBlock = []	
	self.__errorWordLineList = {'begin_of_block':0 , 'end_of_block' :self.__fwConfigObj.wordLinesPerPhysicalBlock-1,\
		                                            'random': self.__randomObj.randint(1,self.__fwConfigObj.wordLinesPerPhysicalBlock-2)}	
	self.__errorWordLine =  self.__errorWordLineList[self.__randomObj.choice(["begin_of_block","end_of_block","random"])]	
	self.__errorType = self.__randomObj.choice(["EA", "EF"])
	self.__retiredBlockList = []
	self.__errorInjected = False	
	self.__startLba = 0
	self.__transferLength = 0
	self.MIPBlockTransitionHappen=False
		
	
	# Register model error call back 
	self.__eiObj.RegisterEraseFailureCallback(self.OnEraseFailure)
	self.__eiObj.RegisterEraseAbortCallback(self.OnEraseAbort)
	self.__eiObj.RegisterPreEraseAbortCallback(self.OnEraseAbort)
	self.__eiObj.RegisterPostEraseAbortCallback(self.OnEraseAbort)	
	
	
    def OnReadOnlyMode(self,argDict):
	"""
	"""
	self.__globalVarsObj.readOnlyMode=True
	self.__globalVarsObj.clearError=True
	self.__logger.Info(self.__globalVarsObj.TAG, "Card in Read only mode.......")
	#if len(argDict) < 3:
	    #return True

	self.__ReadOnlyMode = True
	##self.vtfContainer.DoProduction()
	#self.__ROModeReason = argDict["Reason"]
	#self.__ROModePayload =argDict["Payload"]
	    
	return True 
    
    def OnGATBlockTransition(self,argsDict):  
        """
	Waypoint call back function to notify MIP BLOCK TRANSITION
	""" 	
	return
    
    def OnMipBlockTransitionAfter(self,argsDict):  
        """
	Waypoint call back function to notify MIP BLOCK TRANSITION
	""" 	
	return True 
    
    def OnMipBlockTransitionBefore(self,argsDict):  
        """
	Waypoint call back function to notify MIP BLOCK TRANSITION
	""" 	
	global ErrorPhase
	if ErrorPhase == 'DuringWriteToMIPBlock':
	    self.MIPBlockTransitionHappen=True
	return True 
    
    def OnGATBeforeEraseOfAllocatedBlk(self,args):
	#"""	
	#"""
	global ErrorPhase
	if ErrorPhase == 'DuringWriteToMIPBlock'and self.MIPBlockTransitionHappen:
	    self.__eraseRequestedBlock = [args['SrcMB'],args['DestSectorOffset']]
	    if args['SrcVFC'] == 0x1 and self.__errorInjected == False:
		self.__InjectErrorOnControlBlock(metaBlock = args['SrcMB'],errorType=self.__errorType,wordLine=self.__errorWordLine)
		self.__errorBlock.append(self.__eraseRequestedBlock)
		self.__errorInjected=True
	    self.MIPBlockTransitionHappen=False
	if ErrorPhase != 'DuringWriteToMIPBlock':
	    self.__eraseRequestedBlock = [args['SrcMB'],args['DestSectorOffset']]
	    if args['SrcVFC'] == 0x1 and self.__errorInjected == False:
		self.__InjectErrorOnControlBlock(metaBlock = args['SrcMB'],errorType=self.__errorType,wordLine=self.__errorWordLine)
		self.__errorBlock.append(self.__eraseRequestedBlock)
		
	return True   
    
    def OnMBAddedRetiredList(self,argDict):
	"""
	 ["MBAddr","PlaneNum"]
	""" 
	self.__retiredBlockList.append([argDict["MBAddr"],argDict["PlaneNum"]])
	
	return True 
    
    def OnMipBlockTransition(self,argDict):
    
	"""    
	"""   
	self.__mipBlockExchanged = True 
	
    def __InjectErrorOnControlBlock(self,metaBlock,wordLine = None,secOff = None,errorType=None, blockType=None):
	    """
	    """
	    self.__phyAdd =  AddressTypes.PhysicalAddress()
	    phyAddrList = self.__livetObj.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(metaBlock,0)        
	    for phyAdd in phyAddrList:	          		
		self.__phyAdd.plane = phyAdd[2]
		self.__phyAdd.die = phyAdd[1]
		self.__phyAdd.chip = phyAdd[0]           
		self.__phyAdd.block = phyAdd[3]
		self.__phyAdd.wordLine = wordLine       
       
		#self.__eiObj = EIMediator.ErrorInjectionClass()
		if errorType == 'EF':
		    self.__eiObj.InjectEraseFailureError(errorPhyAddress=self.__phyAdd) 
		elif errorType == 'EA':
		    abortType = self.__randomObj.choice(['erab','poea','prea'])
		    self.__eiObj.InjectEraseAbortError(errorType=abortType,errorPhyAddress=self.__phyAdd)
       
	    self.__errorInjected = True
	    if self.__errorInjected:
		self.dataTracking = self.__livetObj.GetDataTracking()
		self.dataTracking.RequestDataPatternControl(True)				    
		self.dataTracking.UpdatePattern(self.__startLba,self.__transferLength, self.__livetObj.dpUnpredictable)	
		self.markAsUnpredictable=True	
	    
	    return True 
	
	
	
    def OnEraseAbort(self, package,addr):
	"""
	"""
	self.__efOccurred=True
	
	planeNum = (addr[0] * self.__fwConfigObj.planeInterleave ) + addr[1] 
	errorOccurredBlock = [addr[2],planeNum]
	if errorOccurredBlock in self.__errorBlock :
	    if errorOccurredBlock != self.__eraseRequestedBlock:
		self.__logger.Info("","Error on block :%s but erase not requested"%(errorOccurredBlock))	
		self.__logger.Info("","Unexpected erase operation on plane %s"%errorOccurredBlock)
		self.__errorCode = 1
	self.__eiObj.UpdateMap(package,addr)
	#self.__errorInjected = False
				
	return False 
	
    def OnEraseFailure(self, package,addr):
	"""
	"""
	self.__efOccurred=True
	planeNum = (addr[0] * self.__fwConfigObj.planeInterleave ) + addr[1] 
	errorOccurredBlock = [addr[2],planeNum]
	if errorOccurredBlock in self.__errorBlock :
	    if errorOccurredBlock != self.__eraseRequestedBlock:
		self.__logger.Info("","Error on block :%s but erase not requested"%(errorOccurredBlock))	
		self.__logger.Info("","Unexpected erase operation on plane %s"%errorOccurredBlock)
		self.__errorCode = 1
	     
	return False     
	
  
     
   
   
       


	



    def __PerformRandomWrites(self):

	#Step 1: Test for various LBA ranges
	for currentLbaRange in self.__lbaRanges:
	    self.logger.Info(self.globalVarsObj.TAG, "LBA range [ 0x%08X , 0x%08X ]"%(currentLbaRange[0],currentLbaRange[1]))
	    #Step 2: Randomly select the following parameter:
			      #a)numOfReadWrite :  Number of iterations per cycle
	    numOfReadWrite  =self.__randomObj.randint( self.__totalCommandsPerCycle[0] , self.__totalCommandsPerCycle[1] )
	    self.logger.Info(self.globalVarsObj.TAG, "Number of Simultaneous Read/Write : 0x%08X  "%numOfReadWrite)
	    
	    self.logger.Info(self.globalVarsObj.TAG, "Writing Random Data..")
	    for count in xrange(0,numOfReadWrite):
	    #Step 3: Do Write with data length and Lba address are choosen randomely and fill buffer with different pattern.
		startLbaAddress  = self.__randomObj.randrange(currentLbaRange[0],currentLbaRange[1])                
		self.logger.Info(self.globalVarsObj.TAG, "start LbaAddress : 0x%08X  "%startLbaAddress)
    
		transferLength =  self.__randomObj.randint(self.__dataLengthRange[0],self.__dataLengthRange[1] )
		#check data length should not go beyond the LBA range
		transferLength = self.__gatCompactionEIObj.FitTransferLengthToRange(transferLength, startLbaAddress, currentLbaRange[1])
		self.logger.Info(self.globalVarsObj.TAG, "Data Length : 0x%04X  "%transferLength)
		#do write
		self.__startLba = startLbaAddress
		self.__transferLength = transferLength
		self.__ccmObj.Write(startLbaAddress ,transferLength)
		if self.OnAbortOccured:		    
		    self.__eiObj.UpdateMapForUnPredictableUECCPattern(startLbaAddress,transferLength) 
		    self.logger.Info(self.globalVarsObj.TAG, "-"*80)
		    self.logger.Info(self.globalVarsObj.TAG, "OnAbort - LBAs of range (0x%x - 0x%x) have been marked with UnPredictableUECCPattern" %(startLbaAddress,startLbaAddress+transferLength))
		    self.logger.Info(self.globalVarsObj.TAG, "-"*80)		    
		    self.OnAbortOccured = False		
         
	return

    def DeregisterAllWaypoint(self):
        self.__waypointRegObj.UnRegisterWP(self.__wayPointDict)
	#self.globalVarsObj.LivetObj.UnregisterLivetCallback(self.globalVarsObj.LivetObj.lcFlashProgramFail)
        
    
    def EFAndEAHandlerGAT(self, Blockstate, **kwargs):
	global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']	
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	self.__waypointRegObj.RegisterWP(self.__wayPointDict)  
	
	self.__ccmObj.SetLbaTracker()
	self.__waypointRegObj.SetDict()
	self.__chosenCase = 'Random'#self.__randomObj.choice(['Sequential','Random']) 
	self.__logger.Info("","Choosen write pattern : %s"%self.__chosenCase)
	self.__transferLength = self.__wordLineSize
	   
	self.__startLba = 0 
	self.__retiredBlockList = []
	self.__errorWordLineList = {'begin_of_block':0 , 'end_of_block' :self.__fwConfigObj.wordLinesPerPhysicalBlock-1,\
			                    'random': self.__randomObj.randint(1,self.__fwConfigObj.wordLinesPerPhysicalBlock-2)}
	#Perform Writes to trigger GAT and MIP writes 
	if self.__chosenCase == 'Sequential':
	    #Write one LG to open sequential stream
	    if self.__startLba + self.__sizeOfLG < self.__fwConfigObj.maxLba:
		self.__ccmObj.Write(self.__startLba, self.__sizeOfLG)
		self.__startLba += self.__sizeOfLG		
	    self.__transferLength = self.__fwConfigObj.slcMBSize
	else:
	    self.__transferLength = self.__fwConfigObj.sectorsPerPage - 1 
	
	
	#self.__logger.Info("","%s  %s %d " %(sectionName,self.__errorType,self.__errorWordLine))
	#if self.__ReadOnlyMode:
	    #ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	    #self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	    #ErrorManager.ClearAllErrors()		
	    #self.vtfContainer.DoProduction()
	    #self.__waypointRegObj.UnRegisterWP(self.__wayPointDict)
	    #self.__waypointRegObj.RegisterWP(self.__wayPointDict)
	    #self.__ReadOnlyMode=False	
	    
	while  self.__mipBlockExchanged == False or self.__errorInjected == False:
	    if (self.__startLba + self.__transferLength < self.__fwConfigObj.maxLba) :
		try :
		    
		    self.__ccmObj.Write(self.__startLba, self.__transferLength)
		    if self.__errorCode == 1 :
			raise ValidationError.TestFailError("","Unexpected erase operation")
		except Exception, e:
		    if self.__errorCode == 1 :
			raise ValidationError.TestFailError("","Unexpected erase operation")
		    #Check if card is in RO mode due to STATUS_NO_BLOCKS
		    if self.__ReadOnlyMode and (self.__ROModeReason == Utils.ReadOnlyModeReason.RO_Reason_BEThread_CallMMLFailed  or \
		           self.__ROModeReason == Utils.ReadOnlyModeReason.RO_Reason_MML_PostInitFailed ) and self.__ROModePayload == Utils.CallMMLFailed_Payload.STATUS_NO_BLOCKS:
			if self.__sectionNames.index(sectionName) < len(self.__sectionNames)-1:				
			    self.__logger.Info("","FW switched card into RO mode as no blocks to operate") 
			    self.__logger.Info("","Re-initiating the model setup to continue test") 
			    self.__validationSpace.DoDownLoadAndFormat()
			    self.__init__(self.__randomSeed)
			    self.__InitVariables()
			break 
		    elif self.__ReadOnlyMode :
			raise ValidationError.TestFailError("","Card switched to RO mode")
		    else:
			raise Exception(str(e))	
	    else:
		self.__startLba = 0 	
	    if self.__ReadOnlyMode :
		break
	    self.__numberOfSecWritten += self.__transferLength
	    if self.__chosenCase == 'Sequential':
		self.__startLba += self.__transferLength
	    else:
		self.__startLba = self.__randomObj.randint(0, self.__fwConfigObj.maxLba-self.__sizeOfLG)
		
	
	self.__livetFlash.ClearErrors(True)
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors() 		    
	

        if(not self.__efOccurred):
            self.__logger.Info(self.__globalVarsObj.TAG, "EF or EA wasn't detected")
            self.__logger.Info(self.__globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "EF or EA wasn't detected"	

        self.__logger.Info(self.__globalVarsObj.TAG, "############ GAT EF OR EA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True

            
    def EFAndEAHandlerMIP(self, Blockstate, **kwargs):
	global ErrorPhase
	ErrorPhase=kwargs['combination_']['ErrorPhase']
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
	self.__waypointRegObj.SetDict()
        self.__waypointRegObj.RegisterWP(self.__wayPointDict)
	
        self.__logger.Info(self.__globalVarsObj.TAG, '************* ENTERING GAT PF HANDLER *************')
	
	
	chosenCase = 'random'#self.__randomObj.choice(['random', 'sequential'])
	transferLength = self.__fwConfigObj.sectorsPerLgFragment
	self.numWrites = 5000
	self.__randomLG= self.__randomObj.randint(0, self.__fwConfigObj.lgsInCard)
	self.__startLba= self.__randomLG * self.__fwConfigObj.sectorsPerLg  	
	#count = 0
	numOfWritesDone=0
	self.InjectEIAtWrite=self.__randomObj.randint(0, self.numWrites/4)
	
	while(numOfWritesDone < self.numWrites):
	    if self.__startLba + transferLength >= self.__fwConfigObj.maxLba:
		self.__startLba = 0
	
	    self.__globalVarsObj.ccmObj.Write(self.__startLba, transferLength)
	    numOfWritesDone+=1
	    #self.__startLba = startLbaAddress
	    self.__transferLength = transferLength	    
	    
	    if chosenCase == 'sequential':
		self.__startLba += transferLength
	    else:
		self.__randomLG = self.__randomObj.randint(0, self.__fwConfigObj.lgsInCard)
		self.__startLba = self.__randomLG * self.__fwConfigObj.sectorsPerLg 	    
	
        if(not self.__efOccurred):
            self.__logger.Info(self.__globalVarsObj.TAG, "EF or EA wasn't detected")
            self.__logger.Info(self.__globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "EF or EA wasn't detected"
                    
        
        self.__logger.Info(self.__globalVarsObj.TAG, "############ GAT PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
    
       
        
        
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        