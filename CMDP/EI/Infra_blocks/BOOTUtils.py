import random 
import CTFServiceWrapper
import ScsiCmdWrapper as pyWrap
import ConfigParser
import FileData
import SctpUtils
import Core.SctpInterface as SCTPcls
import CommonCodeManager
import EIMediator
import ScsiCmdWrapper
import SCSIGlobalVars, Constants
import Extensions.CVFImports as pyWrap
import EIMediator
WRITE_PATTERN=0xa5
FILEID_OFFSET = 0x00
FILE_SIZE_OFFSET = 0x04
FILE_NUM_SECTOR_OFFSET = 0x08
FILE_NUM_WRITES_OFFSET = 0x0C	
#Maximum file writes to trigger BOOT UPDATE
MAX_FILE_WRITE_BOOT_UPDATE = 50000000

class BootUtils(object):
    """
    Provides API to trigger Boot block update and File System Update
    The functionality in the class are as follows
    
    1. File System Writes to Non- existent files to trigger compaction
    2. UECC Injection to Trigger FS compaction and Boot block update
    """
    IFS_LARGE_FILE_START_NUMBER=240
    TRIGGER_BLOCK_FULL = 0x00
    TRIGGER_UECC       = 0x01
    __MAX_FS_FILES=70
    
    
    cls_logger = None
    ERROR_OCCURRED = False
    cls_livet = None
    errorType = None
    errorAddress = None
    EraseAddress = None
    global errorUtils
    
    def __init__(self,  fwConfigData ,objApplicationRunAttributes=None):
        """
        """
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()

        self.vtfContainer = self.globalVarsObj
        #self.__randomSeed       = randomSeed
        #self.__testSpace        = testSpace
	self.__optionValues = objApplicationRunAttributes
	#random.        = random.Random(randomSeed)
	self.__nonExistingFiles = range(1,self.IFS_LARGE_FILE_START_NUMBER)
	self.__logger           = self.globalVarsObj.logger
	self.__fwConfigData     = fwConfigData
        #self.__cardRawOperations= cardRawOperation
	self.SCTPObj = SCTPcls.SctpInterface()
	self.__eiObj = EIMediator.ErrorInjectionClass()
	self.scsiwrap = ScsiCmdWrapper 
	global errorUtils
	errorUtils = EIMediator.ErrorInjectionClass(self.globalVarsObj)
	
	self.__iniReaderObj = ConfigParser.ConfigParser()
	#self.__iniReaderObj.read(self.fileName)	
	#self.__sectionNames = self.__iniReaderObj.sections()	
	
	self.__sectorSize=512
	self.__sctpObj = SctpUtils.SctpUtils()
	self.__ccmObj = CommonCodeManager.CommonCodeManager()
        self.__fileSizeRange=None
        self.__maxFileWrites=100#self.__optionValues.maxFileWrites
        self.__numFileWrites = 200#self.__optionValues.filesPerCycle
	
	BootUtils.errorType = 'PF' #has to take from csv
	
        self.__FilesToWrite=range(1,self.IFS_LARGE_FILE_START_NUMBER+1)
	self.__ListOfCorruptedFiles=[]
	
	self.vtfContainer = self.globalVarsObj.vtfContainer
	self.livet = self.vtfContainer._livet		
	self.__livet     = self.vtfContainer._livet
	BootUtils.cls_livet   = self.vtfContainer._livet
	
	
	self.__livet.UnregisterLivetCallback(self.__livet.lcFlashProgramFail)
	self.__livet.UnregisterLivetCallback(self.__livet.lcPreProgramAbort)  
	self.__livet.UnregisterLivetCallback(self.__livet.lcPostProgramAbort)
	self.__livet.UnregisterLivetCallback(self.__livet.lcFlashProgramAbort)
	self.__livet.UnregisterLivetCallback(self.__livet.lcFlashEraseFail)
	self.__livet.UnregisterLivetCallback(self.__livet.lcFlashEraseAbort)

	
	self.__livet.RegisterLivetCallback(self.__livet.lcFlashProgramFail,OnProgramFailure)
	
	self.__logger.Info("","Registered callback for Program Failure")  
	
	self.__livet.RegisterLivetCallback(self.__livet.lcPreProgramAbort,OnProgramAbort)  
	self.__livet.RegisterLivetCallback(self.__livet.lcPostProgramAbort,OnProgramAbort)
	self.__livet.RegisterLivetCallback(self.__livet.lcFlashProgramAbort,OnProgramAbort)
	self.__logger.Info("","Registered callback for Program Abort")  
	
	self.__livet.RegisterLivetCallback(self.__livet.lcFlashEraseFail, OnEraseFailure)
	self.__logger.Info("","Registered callback for Erase Failure")
	
	self.__livet.RegisterLivetCallback(self.__livet.lcFlashEraseAbort, OnEraseAbort)
	self.__logger.Info("","Registered callback for Erase Failure")
	
	
	
	self.__objApplicationRunAttributesObj = objApplicationRunAttributes
	
	totalTestDurationInsec = 10*60*60 #EF and EA take about 10 min per Error.  
	
	#self.__objApplicationRunAttributesObj.UpdateTestDuration(totalTestDurationInsec)  
	
	#BootUtils.cls_logger = self.__logger
	
    
    def TriggerFSCompaction(self, errorType=None):
	"""
	Do operations to trigger FS update
	"""
	
	if(errorType.lower() == 'ef' or errorType.lower() == 'ea'):
	    self.__TriggerEraseOperation()
	    
	else:
	    #BootUtils.errorType='WA'
	    self.__TriggerFSCompactionByWritingToFS()
	
	    	
	
    def __TriggerFSCompactionByWritingToFS(self):
	"""
	Write to non existent FS to 
	"""
	self.__logger.Info("","issuing repeated non existing file writes to trigger compaction" )
	compactionTriggered=False
	BootUtils.ERROR_OCCURRED = False
	priSFSListOfMBPlane,secSFSListOfMBPlane=self.__sctpObj.CheckSFS()
	
	
	while(self.__numFileWrites and compactionTriggered==False):# and self.__objApplicationRunAttributesObj.GetRemainingTimeInSeconds()!=0):
	    self.__FileWrite1()
	    if(BootUtils.ERROR_OCCURRED == True):
		self.globalVarsObj.injectedErrorOccurred=True		
		break 
	   
	    priSFSListOfMBPlane_AftrWrites,secSFSListOfMBPlane_AftrWrites=self.__sctpObj.CheckSFS() 
	    if (priSFSListOfMBPlane!=priSFSListOfMBPlane_AftrWrites) and (secSFSListOfMBPlane!=secSFSListOfMBPlane_AftrWrites):
		self.__logger.Info("**************Compaction is  Triggered************")
		compactionTriggered=True
		break
	
	
	if(BootUtils.ERROR_OCCURRED == False and self.__objApplicationRunAttributesObj.GetRemainingTimeInSeconds()==0): 
	    raise ValidationError.TestFailError("BOOTUtil","Halting the test as it ran longer than expected!!!")
	#if(self.__optionValues.powCycleEnable):
	    ## Randomly choose whether to do power cycle or not
	    #if(random.randint(0,1)):
		#self.livet.GetCmdGenerator().PowerOff(0)
		#self.livet.GetCmdGenerator().PowerOn()
	
	
    def __TriggerEraseOperation(self):
	"""
	Write until Erase Occurs 
	"""
	BootUtils.ERROR_OCCURRED = False
	numOfFileWrite = 0
	while BootUtils.ERROR_OCCURRED == False and numOfFileWrite < MAX_FILE_WRITE_BOOT_UPDATE:	    
	    self.__FileWrite1()
	    numOfFileWrite += 1
	if BootUtils.ERROR_OCCURRED:
	    self.globalVarsObj.injectedErrorOccurred=True
	if(BootUtils.ERROR_OCCURRED == False and numOfFileWrite >= MAX_FILE_WRITE_BOOT_UPDATE): 
	    raise ValidationError.TestFailError("BOOTUtil","Halting the test as it ran longer than expected!!!")	
	
	self.__logger.Info("","***********************Validation Summary**************************")	
	self.__logger.Info("","%s injected and occurred on Boot block %s"%(BootUtils.errorType , str(BootUtils.EraseAddress)))
	self.__logger.Info("","*******************************************************************")
	    
    def __FileWrite1(self):
	"""
	Description:
	Writes the non-existant File with specifed Sector tag      
	"""
	#self.S
	RWFiles=self.__sctpObj.GetListOfRwFiles()
	fileChooseToWrite = random.choice(RWFiles)
	#TODO: 
	fileSize = self.__sctpObj.GetFileSize(fileChooseToWrite)
	fileSize = 0x20  # filesize - 0x20 as per the Jira - ZRPG-1074
	self.__logger.Info("","[__FileWrite] Writng File Id :0x%x with file size :0x%x" %(fileChooseToWrite, fileSize))
	fileBuffer=pyWrap.Buffer.CreateBuffer(fileSize, patternType=pyWrap.ALL_1, isSector=True)
	fileBuffer = self.__sctpObj.ReadFileSystem(fileChooseToWrite, fileSize) 
	
	self.__sctpObj.WriteFileSystem( fileChooseToWrite, fileSize,fileBuffer) 
	
	return  
    
	    
    def __InjectUECCToTriggerCompaction(self):
	"""
	"""
	compactionTriggered=False
	SFSEnabled,priSFSMetaBlockAddr1,priSFSMetaBlockAddr2,\
                    secSFSMetaBlockAddr1,secSFSMetaBlockAddr2=DiagnosticLib.CheckSFS(self.__testSpace) 
	self.__logger.Info("","Injecting UECC to either of the blocks to trigger Compaction")
	
	FSBlocks=["Pri","Sec"]
	compactionToTrigger=random.choice(FSBlocks)
	while(2):
	    compactionTriggered=False
	    while(compactionTriggered==False):
		if compactionToTrigger=="Pri": #Primary Copy(=0) or Secondary Copy(=1)
		    self.__InjectUECC(location=0)
		    location=0
		    self.__logger.Info("","injecting UECC to location:Primary")
		    #TODO:
		    #FileIdLocatn=py_sfcl.FileCopy.PrimaryCopy
		elif compactionToTrigger=="Sec":    
		    self.__InjectUECC(location=1)
		    location=1
		    self.__logger.Info("","injecting UECC to location:secondary")
		    #TODO:
		    #FileIdLocatn=py_sfcl.FileCopy.SECONDARY_COPY
		
		for ID in  self.__ListOfCorruptedFiles:
		    try:
			FileSize=self.__sctpObj.GetFileSize(ID)
			rdFileBuff==pyWrap.Buffer.CreateBuffer(FileSize, patternType=pyWrap.ALL_1, isSector=True)#Buffer.Buffer(FileSize)
			self.__logger.Info("Reading the corrupted File of location:%d"%location)
			self.__sctpObj.ReadFile(rdFileBuff,ID,FileSize,FileIdLocatn)
		    except:
			self.__logger.Info("","expected failure as we injected UECC")		    
		##Do some random Host Writes
		wrbuf=pyWrap.Buffer.CreateBuffer(10, patternType=pyWrap.ALL_1, isSector=True)#Buffer.Buffer(10)
		rdbuf=pyWrap.Buffer.CreateBuffer(10, patternType=pyWrap.ALL_1, isSector=True)#(10)
		count=1
		lba=0
		self.__logger.Info("","Issuing Random Host Writes")
		while(count<=10):
		    self.__logger.Info("","Issued Writes to Lba:0x%x with TL:0x10"%lba)
		    self.__ccmObj.Write(lba,10,wrbuf)
		    self.__logger.Info("","Issued Read to Lba:0x%x with TL:0x10"%lba)
		    self.__ccmObj.Read(lba,10,rdbuf)
		    lba=lba+10
		    count=count+1
		
		fileCBSAddr1,sectorPositionInEccPage1 = self.__sctpObj.GetFilePhysicalLocation(self.__testSpace, 
	                                                                                    self.__ListOfCorruptedFiles[0], 
	                                                                                    location, 
	                                                                                    self.__fwConfigData)
		SFSEnabled,priSFSMetaBlockAddr1_AftrWrites,priSFSMetaBlockAddr2__AftrWrites,\
	                                   secSFSMetaBlockAddr1_AftrWrites,secSFSMetaBlockAddr2_AftrWrites=DiagnosticLib.CheckSFS(self.__testSpace) 
		if (priSFSMetaBlockAddr1!=priSFSMetaBlockAddr1_AftrWrites) or (secSFSMetaBlockAddr1!=secSFSMetaBlockAddr1_AftrWrites):
		    self.__logger.Info("**************Compaction is  Triggered For Location:%s************"%location)
		    compactionTriggered=True
		    FSBlocks.remove(compactionToTrigger)
		    if FSBlocks!=[]:
			compactionToTrigger=FSBlocks.pop()
		else:
		    raise ValidationError.TestFailError("BOOTUtil","Compaction is not Triggered for the File System though we corrupted on the RW File")
	    self.__ListOfCorruptedFiles=[]	
    
    def GetFileList(self):
	"""
	"""
	return self.__GetSelectedFileList()
    
    def __GetSelectedFileList(self):
	"""
	Return the selected randomly among the Non -existant Files
	"""
	import random
	fileIdsSelectedList=[]
	compactionTriggered=False
	randomlyPickNumOfFiles=random.randrange(5,10)#No reason why i chose in range (5,10)
	validFileList=self.__sctpObj.GetListOfAllFiles()
	ROFiles=self.__sctpObj.GetListOfRoFiles()
	RWFiles=self.__sctpObj.GetListOfRwFiles()
	FileRemovalFileList=[1,14,33,50,226,232, 239, 42,21,242,80,101,234]
	
	# Files from 1 to 239 are small files, these files occupy one File ID space each in file 1
	# Files from 240 onwards occupy 2 file ID space in file 1, hence we need to consider that while calculating existing files
	# See chorus common files document - File 1 for more info
	validFileListCount = len(validFileList)
	for i in validFileList:
	    if i>=240:
		validFileListCount = validFileListCount + 1  
		
		
	for FileId in validFileList:
	    if ((FileId in ROFiles) or (FileId in RWFiles) or  (FileId in FileRemovalFileList)):
		if FileId in self.__FilesToWrite:#To avoid the Files which is above 240 File index
		    self.__FilesToWrite.remove(FileId)	
	
	# Form a list of 10 or less non-existent file IDs so that the total number of existing file IDs and 
	# the chosen file IDs is <= the max allowed number of files in the FS
	#max FS files is 70 ,my filewrites to nonexisting files should not go beyond the file s/m capcpity
	#numOfFiles=10
	numOfAllowedFiles=(self.__MAX_FS_FILES- validFileListCount)
	if numOfAllowedFiles>0 and numOfAllowedFiles<randomlyPickNumOfFiles:
	    randomlyPickNumOfFiles=numOfAllowedFiles
	elif numOfAllowedFiles<randomlyPickNumOfFiles:
	    RWFileCount=(self.__MAX_FS_FILES- len(RWFiles))
	    if RWFileCount==0:
		self.__logger.Info("","The number of existing files in the FS is %d (= the max number files that are allowed in the FS)\
	        \nThere are no free file IDs to write to.\nThe test cannot be run"%self.__MAX_FS_FILES)
		raise ValidationError.TestFailError("BOOTUtil","The number of existing files in the FS is %d (= the max number files that are allowed in the FS)\
	        \nThere are no free file IDs to write to.\nThe test cannot be run"%self.__MAX_FS_FILES)	
	    else:
		self.__logger.Info("","Issuing Writes to RW Files ")
		self.__FilesToWrite=RWFiles
		for fl in FileRemovalFileList:
		    if fl in self.__FilesToWrite:
			self.__FilesToWrite.remove(fl)
		
    
	#Among nonexistant files,pick the files randomly 
	FileList=self.__FilesToWrite#random.choice(self.__FilesToWrite, randomlyPickNumOfFiles)
	for fil in FileList:
	    fileIdsSelectedList.append([fil,random.randrange(self.__fileSizeRange[0], self.__fileSizeRange[1]),0])#[fileId,fileSize,numOfWrites]
	
	return fileIdsSelectedList	

    
    
    def __CreateFileBuffer(self,fileID, fileSize, fileWriteCount) :
        """
        
	Description:
	    Creates a Buffer with given configuration for a file      
        
        """  

        fileBuffer = pyWrap.Buffer.CreateBuffer(fileSize, patternType=WRITE_PATTERN, isSector=True)
        
        for sector in range(fileSize):     
            fileBuffer.SetFourBytes(FILEID_OFFSET + self.__sectorSize*sector, fileID)
            fileBuffer.SetFourBytes(FILE_SIZE_OFFSET +  self.__sectorSize*sector, fileSize)
            fileBuffer.SetFourBytes(FILE_NUM_SECTOR_OFFSET +  self.__sectorSize*sector, sector+1)
            fileBuffer.SetFourBytes(FILE_NUM_WRITES_OFFSET +  self.__sectorSize*sector, fileWriteCount)
             
             
        return fileBuffer  
    
    
    def __InjectUECC(self,location):
	"""
	Description: Inject UECC to the File ID chosen Randomly among RW Files to the Copy which is passed
	"""
	errorType="UECC"
	
	validFileList=self.__sctpObj.GetListOfRwFiles()
	#for fileListIndex in range(len(ValidFileList)):   
	CorruptFileID = validFileList[random.randint(0, len(validFileList))] 
	
	#Get exact physical location from Meta block address. 
	fileCBSAddr,sectorPositionInEccPage = __sctpObj.GetFilePhysicalLocation(   CorruptFileID, 
                                                                                   location, 
                                                                                   self.__fwConfigData)
	self.__logger.Info("","\n Before Inject ErrorType:%s into File Id:%d ,location:%d \n"%(errorType, CorruptFileID,location))
	if self.__fwConfigData.isBiCS:
	    self.__logger.Info("","[IFS01] Initial Phy address: chip=%d, die=%d, plane=%d, block=%d, wordLine=%d, string=%d, mlcLevel=%d ,eccPage=%d, sector=%d"\
                 %(fileCBSAddr.chip, fileCBSAddr.die, fileCBSAddr.plane, fileCBSAddr.block, 
	           fileCBSAddr.wordLine,fileCBSAddr.string,fileCBSAddr.mlcLevel, fileCBSAddr.eccPage, fileCBSAddr.sector))	    
	else:
	    self.__logger.Info("","[IFS01] Initial Phy address: chip=%d, die=%d, plane=%d, block=%d, wordLine=%d, mlcLevel=%d ,eccPage=%d, sector=%d"\
			     %(fileCBSAddr.chip, fileCBSAddr.die, fileCBSAddr.plane, fileCBSAddr.block, 
			       fileCBSAddr.wordLine,fileCBSAddr.mlcLevel, fileCBSAddr.eccPage, fileCBSAddr.sector))		    
	      
	fileCBSAddr.isTrueBinaryBlock = True
	try:
	    #TODO:
	    self.__eiObj.InjectUECCErrorWithSTM(fileCBSAddr)
	    #self.__cardRawOperations.ECCInject(fileCBSAddr, 1)
	    self.__ListOfCorruptedFiles.append(CorruptFileID)
	except :
	    raise ValidationError.TestFailError("BOOTUtil","The Existing error count is more than the Correctable ECC Limit. Hence, unable to inject CECC error")
	self.__logger.Info("","\n After Injected ErrorType:%s into the File Id:%d \n"%(errorType, CorruptFileID))	
	return  
    
    def FileWrite(self, fileSelectedList):
	"""
	"""
	return self.__FileWrite(fileSelectedList)
    
    def __FileWrite(self,fileSelectedList):
	"""
	 Description:
	     Writes the non-existant File with specifed Sector tag      
	"""
	
	fileSel = random.choice(fileSelectedList)
	fileChooseToWrite = fileSel[0]
	fileSize = fileSel[1]
	fileSel[2] = fileSel[2]+1    #incrementing the file Write Count
	self.__logger.Info("","[__FileWrite] Writng File Id : %s with file size : %s" %(fileChooseToWrite, fileSize))
	fileBuffer = self.__CreateFileBuffer(fileChooseToWrite, fileSize, fileSel[2])
	try:
	    self.__sctpObj.WriteFileSystem( fileChooseToWrite, fileSize,fileBuffer,) 
	except:
	    if(int(self.__livet.hcsPowerFail) != self.scsiwrap.GetLastCommandStatus()):
		raise	 
	return fileChooseToWrite
    
    
    
    def __FileReadandverify(self,fileIdsSelectedList):
	"""
	Description:Read files and ensure they can be read 
	"""
	
	RWFiles=self.__sctpObj.GetListOfRwFiles()
	fileChooseToWrite = random.choice(RWFiles)
	fileSize = self.FileData.GetFileSize(fileChooseToWrite)
	self.__logger.Info("[__FileReadandverify] Read File Id :0x%x with file size :0x%x" %(fileChooseToWrite, fileSize))
	fileBuffer=pyWrap.Buffer.CreateBuffer(fileSize, patternType=pyWrap.ALL_1, isSector=True)
	self.__sctpObj.ReadFile(fileBuffer, fileChooseToWrite, fileSize) 	
    
    
    
    

def OnProgramFailure(Package,Addr):
    """
    
    """
    
    """
    Model Call Back Function for Program Failure
    """
    global errorUtils #using one since we use this class only for logging LBA whicih does not neeed randomization
    #ValidationTestEventsObj = ValidationTestEvents.ValidationTestEvents(BootUtils.cls_logger)
    #ValidationTestEventsObj.RecordTestEvent('EI_TE_NumberOfProgramFailures')    
    #BootUtils.cls_logger("","#################################################################################")
    ##BootUtils.cls_logger.Warning("","#################################################################################")
    #BootUtils.cls_logger.Warning("","--- PROGRAM_Failure -- event occured at ->Package = [0x%x], Address = %s"%(Package,Addr))
    #BootUtils.cls_logger.Warning("","#################################################################################")
       
    if BootUtils.errorType == 'PF':
	BootUtils.ERROR_OCCURRED = True
	
	
	#BootUtils.globalVarsObj.injectedErrorOccurred=True	
    BootUtils.errorAddress = Addr
    wordLineLbas = BootUtils.cls_livet.GetFlash().GetWordlineLBAs(Package,Addr)
    
    errorUtils.LogWordLineLbas(Package, Addr, wordLineLbas, 
                                                 headerString="", 
                                                 logLbasOnlyForLowerPage=False)   
    
    return 0


def OnProgramAbort(Package,Addr):
    """
    """
    #ValidationTestEventsObj = ValidationTestEvents.ValidationTestEvents(BootUtils.cls_logger)
    #ValidationTestEventsObj.RecordTestEvent(' EI_TE_NumberOfAbort')    
    #BootUtils.cls_logger.Warning("#################################################################################")
    #BootUtils.cls_logger.Warning("--- PROGRAM_ABORT -- event occured at ->Package = [0x%x], Address = %s"%(Package,Addr))
    #BootUtils.cls_logger.Warning("#################################################################################")    
    global errorUtils
    wordLineLbas = BootUtils.cls_livet.GetFlash().GetWordlineLBAs(Package,Addr)
    errorUtils.LogWordLineLbas(Package, Addr, wordLineLbas, 
                                                 headerString="", 
                                                 logLbasOnlyForLowerPage=False)    
    
    BootUtils.ERROR_OCCURRED = True
    BootUtils.errorAddress = Addr
    
    return 0


def OnEraseAbort(Package,Addr):
    """
    """  
    #BootUtils.cls_logger.Warning("#################################################################################")
    #BootUtils.cls_logger.Warning("--- ERASE_ABORT -- event occured at ->Package = [0x%x], Address = %s"%(Package,Addr))
    #BootUtils.cls_logger.Warning("#################################################################################")    
    global errorUtils
    wordLineLbas = BootUtils.cls_livet.GetFlash().GetWordlineLBAs(Package,Addr)
    errorUtils.LogWordLineLbas(Package, Addr, wordLineLbas, 
                                                 headerString="", 
                                                 logLbasOnlyForLowerPage=False)    
    
    BootUtils.ERROR_OCCURRED = True
    BootUtils.EraseAddress = Addr
    
    return 0

def OnEraseFailure(Package,Addr):
    """
    """  
    #BootUtils.cls_logger.Warning("#################################################################################")
    #BootUtils.cls_logger.Warning("--- ERASE_FAILURE -- event occured at ->Package = [0x%x], Address = %s"%(Package,Addr))
    #BootUtils.cls_logger.Warning("#################################################################################")    
    global errorUtils
    wordLineLbas = BootUtils.cls_livet.GetFlash().GetWordlineLBAs(Package,Addr)
    errorUtils.LogWordLineLbas(Package, Addr, wordLineLbas, 
                                                 headerString="", 
                                                 logLbasOnlyForLowerPage=False)    
    
    BootUtils.ERROR_OCCURRED = True
    BootUtils.EraseAddress = Addr
    
    return 0

