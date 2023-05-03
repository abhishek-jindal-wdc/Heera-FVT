"""
********************************************************************************
 * MODULE     : IFSErrorInjectionLib.py
 * FUNCTION   : Common Functions Used in IFS Error Injection Test Cases
 * PROGRAMMER : Sreelekha.N
 * DATE(ORG)  : 22Apr'14
 * REMARKS    : This assumes that the hardware and framework have been set up
 * COPYRIGHT  : Copyright (C) 2014 SanDisk Corporation 
*------------------------------------------------------------------------------*
*  Revision History
*------------------------------------------------------------------------------*
* Sl.No:  Date  : Description                                 - Programmer
   ----------------------------------------------------------------------------
*   1:  22/04/2014  Programmed and Release for script testing  -  Sreelekha.N
********************************************************************************
"""
import random as random
import SctpUtils
import WaypointReg
import Utils as Utils
import Extensions.CVFImports as pyWrap

#import py_sfcl


WRITE_PATTERN=0xa5
FILEID_OFFSET = 0x00
FILE_SIZE_OFFSET = 0x04
FILE_NUM_SECTOR_OFFSET = 0x08
FILE_NUM_WRITES_OFFSET = 0x0C
ReadOnlyMode=False
def PostCommandsAfterABort():
    """
    Issuing host write file writes after Abort
    """
    global ReadOnlyMode
    try:
	sctp_opb = SctpUtils.SctpUtils()
	#wpregobj = WaypointReg.WaypointReg(livet, logger)
	##Issuing Dummy Write and read to LBA0 to avoid TimeStamp Issues
	#wayPointDict = {
	        #"FS_COMPACTION_AFTER_BLK_ALLOCATION" : [self.FS_COMPACTION_AFTER_BLK_ALLOCATIONcallback],
	#}
	#testSpace.Livet.RegisterFirmwareWaypoint("READ_ONLY_MODE",None) 
	#EventKey=testSpace.Livet.RegisterFirmwareWaypoint("READ_ONLY_MODE",ReadOnlyModeCallBackFunc)  
	#card=testSpace.GetCard()
	#Adapter=testSpace.GetAdapter()
	#livet=self.vt.Livet
	#testSpace.GetLogger().Info("Issuing Dummy Read Write After Abort Before Issuinng Diag")
	DataBuffer=pyWrap.Buffer.CreateBuffer(8, patternType=pyWrap.ALL_0, isSector=True)#(1)
	#testSpace.GetLogger().Info("Writing Dummy Write to LBA:0 TL:1")
	#card.WriteLba(0,1,DataBuffer)
	#testSpace.GetLogger().Info("Reading Dummy Read to LBA:0 TL:1")
	#card.ReadLba(0,1,DataBuffer)	    
	#testSpace.GetLogger().Info("Issuing One File Write to Trigger Compaction after WA on MAP File")
	RWFiles=sctp_opb.GetListOfRwFiles()
	fileChooseToWrite = random.choice(RWFiles)
	fileSize = sctp_opb.GetFileSize(fileChooseToWrite)
	#testSpace.GetLogger().Info("[__FileWrite] Writng File Id : 0x%x with file size : 0x%x" %(fileChooseToWrite, fileSize))
	fileBuffer=pyWrap.Buffer.CreateBuffer(8, patternType=pyWrap.ALL_0, isSector=True)#(fileSize)
	sctp_opb.ReadFileSystem(fileChooseToWrite, fileSize, fileBuffer) 
	sctp_opb.WriteFileSystem(fileChooseToWrite, fileSize,fileBuffer)
	sctp_opb.WriteFileSystem(fileChooseToWrite, fileSizefileBuffer)
	RoFilessctp_opb.GetListOfRoFiles()
	for fileId in RoFiles:
	    fileSize = card.GetFileSize(fileId)
	    fileBuffer=pyWrap.Buffer.CreateBuffer(8, patternType=pyWrap.ALL_0, isSector=True)#(fileSize)
	    card.ReadFile(fileBuffer, fileId, fileSize) 	    
    except:
	if ReadOnlyMode==True:
	    ReadOnlyMode=False
	    #import Validation.ValidationError as ValidationError
	    raise ValidationError.ReadOnlyModeError("Card has entered read only mode due to error injections")
	#elif Adapter.GetLastCommandStatus()== (int(livet.hcsPowerFail)):
	    #pass
	    #testSpace.GetLogger().Info("Read/Write Failed because of PowerFail")
	else:
	    raise
    return    
    
def ReadAllValidFiles(copy="PRI"):
    """
    Read to all ReadWriteFiles
    """
    #card=testSpace.GetCard()
    
    #SCTPoBJ = SctpUtils.SctpUtils()
    #if copy=="PRI":
	#copyToRead=py_sfcl.FileCopy.PRIMARY_COPY
    #elif copy=="SEC":
	#copyToRead=py_sfcl.FileCopy.SECONDARY_COPY
    
    SCTPoBJ = SctpUtils.SctpUtils()
    ValidFiles = SCTPoBJ.GetListOfRwFiles()
    for fil in ValidFiles:
	fileSize = SCTPoBJ.GetFileSize(fil)
	#logger.Info("[__FileRead] Reading File Id : %s with file size : %s" %(fil, fileSize))
	fileBuffer=pyWrap.Buffer.CreateBuffer(8, patternType=pyWrap.ALL_0, isSector=True)#(fileSize)
	try:
	    ##By default it reads Primry
            if RoFile!=226:
                SCTPoBJ.ReadFileSystem(fil,fileSize,fileBuffer)
	    #card.ReadFile(fileBuffer, fil, fileSize) 
	except:
	    #try:
		#card.ReadFile(fileBuffer, fil, fileSize,py_sfcl.FileCopy.SECONDARY_COPY) 
	    #except:
		#testSpace.GetLogger().Info("Read Failed unexpectedly for File:%d"%fil)
	    raise Exception (("Read Failed unexpectedly for FileID:%d"%fil),fil)
    return  
def InjectPFOnPhysicalLocation(livetobj , logger, Package,PhyAddr,pErrorPersistence=None,pSkipCount=0,pDelayToOccurence=0,pDelayToRecovery=1,pByteOffset=0,pByteMask=0):
    """
    Name: InjectPFOnPhysicalLocation 
    Description: Inject PF On Physical Location 
    Arguments:
       Package        : Package on which PF to Inject       
       PhyAddr        : PhyAddr on which PF to inject
       pErrorPersistence: Error persistence
       pSkipCount  : Skip count for error injection 
       pDelayToOccurence: Delay to occurence
       pDelayToRecovery:  Delay to Recovery
       pByteOffset : Byte offset within the Lba
       pByteMask   : Byte Mask to use
    Returns        : None
    """
    livet=livetobj
    livetFlash=livet.GetFlash()    
    flashOperation=livet.foProgram
    errorType=livet.etProgramError
    if pErrorPersistence is None:
	errorPersistence = livet.epSoft
    else:
	errorPersistence = pErrorPersistence  
    
    errorDescription = (errorType,errorPersistence,pDelayToOccurence,pDelayToRecovery,pByteOffset,pByteMask)
    logger.Info("","Injecting %s to physical Address:%s"%("PF",PhyAddr))
    livetFlash.InjectError(Package,PhyAddr,errorDescription)
    
    return
def InjectWLShortOnPhysicalLocation(Package,PhyAddr,pErrorPersistence=None,pSkipCount=0,pDelayToOccurence=0,pDelayToRecovery=1,pByteOffset=0,pByteMask=0):
    """
    Name: InjectPFOnPhysicalLocation 
    Description: Inject WLshort On Physical Location 
    Arguments:
       Package        : Package on which WLshort to Inject       
       PhyAddr        : PhyAddr on which WLshort to inject
       pErrorPersistence: Error persistence
       pSkipCount  : Skip count for error injection 
       pDelayToOccurence: Delay to occurence
       pDelayToRecovery:  Delay to Recovery
       pByteOffset : Byte offset within the Lba
       pByteMask   : Byte Mask to use
    Returns        : None
    """
    #livet=testSpace.Livet
    #livetFlash=livet.GetFlash()    
    #flashOperation=livet.foProgram
    #errorType=livet.etWordlineShort
    
    if pErrorPersistence is None:
	errorPersistence = livet.epPermanent
    else:
	errorPersistence = pErrorPersistence  
    
    errorDescription = (errorType,errorPersistence,pDelayToOccurence,pDelayToRecovery,pByteOffset,pByteMask)
    testSpace.GetLogger().Info("Injecting %s to physical Address:%s : with errorDescription : %s"%("WordlineShort",PhyAddr, errorDescription,))
    livetFlash.InjectError(Package,PhyAddr,errorDescription)
    
    return
def InjectEFOnPhysicalLocation(Package,PhyAddr,pErrorPersistence=None,pSkipCount=0,pDelayToOccurence=0,pDelayToRecovery=1,pByteOffset=0,pByteMask=0):
    """
    Injecting Erase Failure
    """
    #livet=testSpace.Livet
    #livetFlash=livet.GetFlash()    
    #flashOperation=livet.foErase
    #errorType=livet.etEraseError
    if pErrorPersistence is None:
	errorPersistence = livet.epPermanent
    else:
	errorPersistence = pErrorPersistence  
    
    errorDescription = (errorType,errorPersistence,pDelayToOccurence,pDelayToRecovery,pByteOffset,pByteMask)
    #testSpace.GetLogger().Info("Injecting %s to physical Address:%s"%("EF",PhyAddr))
    livetFlash.InjectError(Package,PhyAddr,errorDescription)
    
    return  

    
    
def GetNumOfWordlineToAvoidEI(vtf):
    """
    To avoid error injection on the boundary of FS threshold
    """
    import FWConfigData
    #import Validation.ValidationSpaceLib.FwConfig as FwConfig
    fwconfigdata=FWConfigData.FWConfigData(vtf)  

    sctpObj = SctpUtils.SctpUtils()
    #AS per Sparrow-282,FilesWrites are leading to cross threshold hence avoding EI to the END of threshold value
    #ex:Error injected on WL 74 where Threshold is 75 ,few file writes crosses 7/8 of the block ,FW sets it blk for compaction
    #so Error injected never occurs to avoid this below fix is done
    listofRWFiles=sctpObj.GetListOfRwFiles()    
    #card=testSpace.GetCard()
    ListOfFileSize=[]
    for File in listofRWFiles:
	FileSize=sctpObj.GetFileSize(File)
	ListOfFileSize.append(FileSize)
    MaximumFileSize=max(ListOfFileSize)
    
    #FS pages are 8k where as SLC block pages are 16k ,below calculation implies the same
    ReadConfigParams=sctpObj.ReadConfigurationParameters()
    FsPagesPerBlock=ReadConfigParams["FsPagesPerBlock"]
    pagesPerSlcBlock= fwconfigdata.ReadConfigurationParameters()["pagesPerSlcBlock"]
    sectorsPerPage=fwconfigdata.ReadConfigurationParameters()["sectorsPerPage"]#fwconfigdata.sectorsPerPage
    SectorsPerFSPage=(sectorsPerPage*pagesPerSlcBlock)/FsPagesPerBlock    
    sectorsPerMetaPage = (fwconfigdata.ReadConfigurationParameters()["phyPagesPerMetaPage"] / 2) * sectorsPerPage
    NumOfWLToAvoid= (MaximumFileSize/sectorsPerMetaPage) + 1
    
    return NumOfWLToAvoid
	
	
def InjectEAOnPhysicalLocation(ErrorType,Package,PhyAddr,pErrorPersistence=None,pSkipCount=0,pDelayToOccurence=0,pDelayToRecovery=1,pByteOffset=0,pByteMask=0):
    """
    Injecting Erase Failure
    """
    #livet=testSpace.Livet
    #livetFlash=livet.GetFlash()      
    #flashOperation=livet.foErase
    #errorType=ErrorType
    if pErrorPersistence is None:
	errorPersistence = livet.epSoft
    else:
	errorPersistence = pErrorPersistence  
    errorDescription = (errorType,errorPersistence,pDelayToOccurence,pDelayToRecovery,pByteOffset,pByteMask)
    #testSpace.GetLogger().Info("Injecting %s to physical Address:%s"%("EA",PhyAddr))
    livetFlash.InjectError(Package,PhyAddr,errorDescription)
    return

def InjectWAOnPhysicalLocation(livetObj, logger,Package,PhyAddr,pErrorPersistence=None,pSkipCount=0,pDelayToOccurence=0,pDelayToRecovery=1,pByteOffset=0,pByteMask=0,ErrorType=None):
    """
    Name: __InjectWAOnPhysicalLocation 
    Description: Injects logical trigger PF on Lba 
    Arguments:
       PhyAddr        : Physical Address on which PF to inject
       ErrorType      : Type of WA(pre or post or WA) to inject
       pErrorPersistence: Error persistence
       pSkipCount  : Skip count for error injection 
       pDelayToOccurence: Delay to occurence
       pDelayToRecovery:  Delay to Recovery
       pByteOffset : Byte offset within the Lba
       pByteMask   : Byte Mask to use
    Returns        : None
    """
    livet=livetObj
    livetFlash=livet.GetFlash()
    if ErrorType==None:
	ErrorType=random.choice(["PRE_WA","POST_WA","WA"])
    
    flashOperation=livet.foProgram
    if ErrorType=="PRE_WA":
	logger.Info("","Injecting PRE-WA Error")
	errorType=livet.etPreProgramAbort
    elif ErrorType=="POST_WA":
	logger.Info("","Injecting POST-WA Error")
	errorType=livet.etPostProgramAbort
    else:
	logger.Info("","Injecting WA Error")
	errorType=livet.etProgramAbort
       
    if pErrorPersistence is None:
	errorPersistence = livet.epHard
    else:
	errorPersistence = pErrorPersistence 
	
   
    errorDescription = (errorType,errorPersistence,pDelayToOccurence,pDelayToRecovery,pByteOffset,pByteMask)
  
    logger.Info("","Injecting error:%s on PhysicalAddress:%s\n"%(ErrorType,PhyAddr))
    livetFlash.InjectError(Package,PhyAddr,errorDescription)
    
    return
def GetThresholdToInjectError(fwConfigData,vtf):
    """
    """
    sctpObj=SctpUtils.SctpUtils()
    ReadConfigParams = sctpObj.ReadConfigurationParameters()
    assert ReadConfigParams["FsPagesPerBlock"]>0,"Fs pages Per block returned by Diag is none"
    FSCompactionThresold=ReadConfigParams["FsPagesPerBlock"]>>3
    SDFSComapactionThresold=(ReadConfigParams["FsPagesPerBlock"]-FSCompactionThresold)
    #SDFSComapactionThresold=((ReadConfigParams["FsPagesPerBlock"]-FSCompactionThresold)*\
                                    #(ReadConfigParams["FsMetablock"]/ReadConfigParams["RsNumOfCopies"]))
    assert SDFSComapactionThresold>0,"SDFS compaction theresold is none"
    SECTOR_PER_FS_PAGE=16
    totalSectorsPerSDFS = SECTOR_PER_FS_PAGE * SDFSComapactionThresold
    
    sectorsPerMetaPage = (fwConfigData.phyPagesPerMetaPage / 2) * fwConfigData.sectorsPerPage
    thresholdInWL = totalSectorsPerSDFS/sectorsPerMetaPage
    #threshold=(SDFSComapactionThresold*fwConfigData.pagesPerSlcBlock)/ReadConfigParams["FsPagesPerBlock"] 
    if fwConfigData.isBiCS:
	thresholdInWL=thresholdInWL/fwConfigData.stringsPerBlock
    NumofWLToAvoidEI=GetNumOfWordlineToAvoidEI(vtf)
    threshold=thresholdInWL-NumofWLToAvoidEI
    return threshold

def InjectErrorOnLba(pLba,errorType,pSkipCount,flashOperation=None,pErrorPersistence=None,pDelayToOccurence=0,pDelayToRecovery=1,pByteOffset=0,pByteMask=0):
    """
    Name: InjectErrorOnLba 
    Description: Injects logical trigger on Hypothetical FSMAP Lba 
    Arguments:
       pErrorPersistence: Error persistence
       pSkipCount  : Skip count for error injection 
       pDelayToOccurence: Delay to occurence
       pDelayToRecovery:  Delay to Recovery
       pByteOffset : Byte offset within the Lba
       pByteMask   : Byte Mask to use
    Returns        : None
    """
    
    #livet=testSpace.Livet
    #livetFlash=livet.GetFlash()     
    if flashOperation==None:
	flashOperation=livet.foProgram
  	
    if pErrorPersistence is None:
       errorPersistence = livet.epSoft
    else:
       errorPersistence = pErrorPersistence  
    #testSpace.GetLogger().Info("Injecting logical error on Hypothetical LBA:0x%x,ErrorType:%s"%(pLba,errorType))
    errorDescription = (errorType,errorPersistence,pDelayToOccurence,pDelayToRecovery,pByteOffset,pByteMask)
    livetFlash.SetLogicalTrigger(pLba,flashOperation,pSkipCount,errorDescription)
    
    return

def GetNonExistingFiles(FilesToWrite,NumOfFiles=10):
    """
    """
    import SctpUtils
    sctpUtilsObj = SctpUtils.SctpUtils()
    RWFiles=sctpUtilsObj.GetListOfRwFiles()
    validFileList=sctpUtilsObj.GetListOfAllFiles()
    ROFiles=sctpUtilsObj.GetListOfRoFiles()
    FileRemovalFileList=[1,14,50,226,232,42,21]
    
    for FileId in validFileList:
	if ((FileId in ROFiles) or (FileId in RWFiles) or  (FileId in FileRemovalFileList)):
	    if FileId in FilesToWrite:#To avoid the Files which is above 240 File index
		FilesToWrite.remove(FileId)	
		
    ChoosenNumOfFilesToWrite =(random.sample(FilesToWrite,NumOfFiles))
    return ChoosenNumOfFilesToWrite

def CreateFileBuffer(fileID, fileSize, fileWriteCount,sectorSize) :
    """
    
    Description:
	Creates a Buffer with given configuration for a file      
    
    """   
    fileBuffer = pyWrap.Buffer.CreateBuffer(8, patternType=pyWrap.ALL_0, isSector=True)#(fileSize,WRITE_PATTERN)
    
    
    for sector in range(fileSize):     
	fileBuffer.SetFourBytes(FILEID_OFFSET + sectorSize*sector, fileID)
	fileBuffer.SetFourBytes(FILE_SIZE_OFFSET + sectorSize*sector, fileSize)
	fileBuffer.SetFourBytes(FILE_NUM_SECTOR_OFFSET + sectorSize*sector, sector+1)
	fileBuffer.SetFourBytes(FILE_NUM_WRITES_OFFSET + sectorSize*sector, fileWriteCount)
	 
	 
    return fileBuffer 

def ReadOnlyModeCallBackFunc(EventKey,args,ProcessorID):
    """
    """
    global ReadOnlyMode
    ReadOnlyMode=True
    return 0

def GetPhysicalAddressFromMBAddress(livet, addList):
    """
    The check for grown bad block compares the physical address 
    from PF against MB from Grown bad bloc waypoint
    """
    tempAddList = []
    for block in addList:
	phyAddrList = livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(block, 0)
	for addr in phyAddrList:
	    tempAddList.append(addr[3])
    return tempAddList
