import ErrorInjectorLib
import SDUtils
import random
import SCSIGlobalVars
import WaypointReg
import FwConfig as FwConfig
import SctpUtils
import Utils as Utils
import Extensions.CVFImports as pyWrap
import Core.ValidationError  as ValidationError
import AddressTranslation
import AddressTypes
import SDFS
import ConfigParser
import LDPCUtils
import ScsiCmdWrapper as scsiWrap
from Constants import LDPCREH as LDPCConstants
import ControlBlockInfo
import BOOTUtils as FSBootLib
import EIMediator


#globals
g_UnCorrectableECC=0x01
g_CorrectableECC = 0x00
g_ErrorByte=0x20
g_PrimaryCopy = 0
g_SecondaryCopy = 1
g_ALL_ZEROS = 0x00

"""CONSTANTS"""
CORRUPT = 1
DONT_CORRUPT = 0
RAND_COUNT1 = 10
DELETE_LATEST_BOOT_PAGE = 0
DONT_DELETE_LATEST_BOOT_PAGE = 1


class UECChandler:
    
    __staticUECCObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not UECChandler.__staticUECCObj:
            UECChandler.__staticUECCObj = super(UECChandler,cls).__new__(cls, *args, **kwargs)

        return UECChandler.__staticUECCObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
	self.vtfContainer=self.globalVarsObj.vtfContainer

        self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
        self.__ccmObj         = self.globalVarsObj.ccmObj
        self.WaypointRegObj = self.globalVarsObj.WayPointObj
        self.utilsObj       = Utils.Utils()
        self.sctpUtilsObj = SctpUtils.SctpUtils()
        self.randomSeedObj = self.globalVarsObj.randomObj
        self.ldpcObj = LDPCUtils.LDPCUtils(self.vtfContainer)
        self.__fwConfigData=FwConfig.FwConfig(self.vtfContainer)
        self.__iniObj = ConfigParser.ConfigParser()
        self.__addrTranslatnObj=AddressTranslation.AddressTranslator(self.vtfContainer)
        self.__sdfsObj = SDFS.SDFS(self.__fwConfigData, self.__addrTranslatnObj) 
	self.__addTransObj=AddressTranslation.AddressTranslator( self.vtfContainer)
        
	self.eiObj = EIMediator.ErrorInjectionClass()        
        
        self.wayPointDict = {
            "LDPC_BES_START"          : [],
            "LDPC_BES_END"            : [],
            "LDPC_BER"                : [],
            "LDPC_HB_DECODE_START"    : [],
            "LDPC_HB_DECODE_END"      : [],
            "LDPC_SB_DECODE_START"    : [],
            "LDPC_SB_DECODE_END"      : [],
            "LDPC_DECODE_SUCCESS"     : [],		   
            "FILE_WRITE"              : [],
            "READ_FILE_SYSTEM"        : [],
            "UECC_DETECTED"           : [self.OnUECCDetected],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict)
	
        self.__testRunObj=self.vtfContainer.cmd_line_args
	self.__applicationRunAttributesObj = self.vtfContainer.cmd_line_args
	self.__livet     = self.vtfContainer._livet	
	
	self.__errorType  = self.vtfContainer.cmd_line_args.errorType
	self.SECTORS_PER_PAGE = self.__fwConfigData.sectorsPerPage


        self.ResetVariables()
    
        
    def ResetVariables(self):
        self.__logger= self.logger 
        self.__FSBlockCopy_Inverse = 6 #py.Secondary#by default reading from secondary
        self.__randomObj   = self.globalVarsObj.randomObj 
        
        self.Bes7CoarseApplied = False
        self.Bes7FineApplied = False
        self.SB1DecodeStart = False
        self.SB2DecodeStart = False
        self.UECCDetected = False
        self.BEREstApplied = False
        self.ReadDecodeState = None
        self.phyAddr = None
        self.applyHBFailSTM = False
        self.FailHBAtBes7FineLevel = False
        self.clearError = False   
	
	self.__cycleCount = 0 # internal Cycle Count used odd = Do Power cycle and Check. Even= Do FileWriteso that Boot Block Upate Occurs and then do Power Cycle
	self.__commandCount = 10	
        
    

    
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
        
    def UECCHandlerIFS(self, Blockstate, **kwargs):
        self.__logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS UECC HANDLER *************')
	try:
	    self.DeregisterAllWaypoint() 
	except:
	    pass	
        #Registering waypoints
	self.WaypointRegObj.SetDict()
        self.WaypointRegObj.RegisterWP(self.wayPointDict)
	
	if self.globalVarsObj.randomObj.choice([0,1]):
	    self.__logger.Info("", "Injecting UECC to Primary FS block alone")         
	    self.__FSBlockCorruptionTest( CORRUPT,DONT_CORRUPT, g_CorrectableECC,None )
	    
	else:
	    self.__logger.Info("", "Injecting UECC to Secondary FS block alone")
	    self.__FSBlockCorruptionTest(DONT_CORRUPT, CORRUPT, None, g_CorrectableECC)
	    
	if not self.UECCDetected:
	    self.ResetVariables()
	    self.DeregisterAllWaypoint()		
	    self.logger.Info("", "Injected UECC wasnt Detected.") 
	    return False
   
            
        
        self.logger.Info(self.globalVarsObj.TAG, "############ IFS UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def __FSBlockCorruptionTest( self,corruptPrimary, 
                                corruptSecondary, primaryErrorType, secondaryErrorType):
       """
       Name       :   __FSBlockCorruptionTest
       Description:   Performs the FS block corruption test for different test scenario
           2. Get the meta block address of the FS block.
           3. Get the latest primary and secondary addresses of the FSBS sector.
           4. Inject the data corruption to the last FS sector in chosen FSblock copy and specified error type.
           5. Power cycle the card and check whether card boots up or not.
           6. Restore the previous state of the card by downloading.

       Arguments  :          

          corruptPrimary      : Check whether to corrupt the primary FS block or not
                                      0-Dont Corrupt
                                      1-Corrupt
          corruptSecondary    : Check whether to corrupt the Secondary FS block or not
                                      0-Dont Corrupt
                                      1-Corrupt
          primaryErrorType    : type of error to be injected in primary FS block
                                      0-correctable ECC error
                                      1-Uncorrectable ECC error
          secondaryErrorType  : type of error to be injected in secondary FS block
                                      0-correctable ECC error
                                      1-Uncorrectable ECC error

       Returns:        None

       """
       moduleName = "__FSBlockCorruptionTest"           

       #the following steps are taken care in the function
       #Step 2. Get the meta block address of the FS block 
       #Step 3. Get the latest primary and secondary addresses of the FS sector.
       #Step 4. Inject the data corruption to the FS sector as selected by user
       self.__logger.Info(self.globalVarsObj.TAG, "Executing steps 2 to 4 of the algorithm")
       corruptWholeFS=self.__randomObj.choice([True,False])

       #Corrupting either of the FS blocks
       #corrupting primary FS block
       if (corruptPrimary):
           if primaryErrorType ==g_CorrectableECC:
               self.__CorruptSingleFSBlock(g_PrimaryCopy,g_CorrectableECC,corruptWholeFS)
           elif primaryErrorType == g_UnCorrectableECC:
               self.__CorruptSingleFSBlock(g_PrimaryCopy,g_UnCorrectableECC,corruptWholeFS) 
               self.__FSBlockCopy_Inverse = 4

       #corrupting secondary FS block         
       if (corruptSecondary):
           if secondaryErrorType ==g_CorrectableECC:
               self.__CorruptSingleFSBlock(g_SecondaryCopy,g_CorrectableECC,corruptWholeFS)
           elif secondaryErrorType == g_UnCorrectableECC:
               self.__CorruptSingleFSBlock(g_SecondaryCopy,g_UnCorrectableECC,corruptWholeFS)
               self.__FSBlockCopy_Inverse = 2
               
       #Do a power cycle and verify the bootability of the card
       self.__logger.Info(self.globalVarsObj.TAG, "[%s]Step 5. Power cycle the card"%moduleName)
       try:
           random_count = self.__randomObj.randint(0,10)
           #doing a powercycle between writes and reads for specified time duration
           numberOfWrites = 10	    
           while (numberOfWrites > 0 ):
               numberOfWrites = numberOfWrites - 1
               random_Sector_List = []
               lbaToWrite_List = []		
               for count1 in range(0,random_count):
                   sectorCount = self.__randomObj.randint(1,self.__fwConfigData.sectorsPerLgFragment)
                   random_Sector_List.append(sectorCount)
                   lbaToWrite = self.__randomObj.randint(0,self.__fwConfigData.maxLba-sectorCount)
                   lbaToWrite_List.append(lbaToWrite)
                   self.__ccmObj.Write(lbaToWrite, sectorCount)
               try:  
                   #Utils.PowerCycle()
                   self.livet.GetCmdGenerator().PowerOff(0)
                   self.livet.GetCmdGenerator().PowerOn()
                   self.__logger.Info(self.globalVarsObj.TAG, "[%s] The card recovered properly after a powercycle"%moduleName)
               except:
                   self.__logger.Info(self.globalVarsObj.TAG, "[%s] The card did not recover properly after a powercycle"%moduleName)
                   raise 
               for count2 in range(len(lbaToWrite_List)):
                   #Read LBA with Data Integrity Check.
                   self.__ccmObj.Read(lbaToWrite_List[count2], random_Sector_List[count2]) 
       except:
           pass
       self.__logger.Info(self.globalVarsObj.TAG, "[%s] Power cycling the card -SUCCESSFUL."%moduleName)



       ########################################################################
       for fileListCount1 in range(len(self.__corruptFileList)):	 
           #Now issue ReadFile (from targetted FS) to read that file and get the data.	   
           fileIdChosen1 = self.__corruptFileList[fileListCount1]
           self.__logger.Info(self.globalVarsObj.TAG, " Reading the Inverse file(other copy) after corrupting it...FileId: %d "%(fileIdChosen1))
           fileSize1 = self.sctpUtilsObj.GetFileSize(fileIdChosen1)
           changedFileBuf1 = pyWrap.Buffer.CreateBuffer(fileSize1, patternType=pyWrap.ALL_0, isSector=True)#(fileSize1,0)
           try:
               if corruptPrimary:
                   self.sctpUtilsObj.ReadFileSystem(fileIdChosen1,fileSize1,changedFileBuf1,2) # Option=2 : Primary
               if corruptSecondary:
                   self.sctpUtilsObj.ReadFileSystem(fileIdChosen1,fileSize1,changedFileBuf1,4) # Option=4 : Secondary
           except:
               self.__logger.Info(self.globalVarsObj.TAG, "Read Failure for file :0x%x"%fileIdChosen1)
               raise ValidationError.TestFailError("","Read Failure for file :0x%x"%fileIdChosen1)

       self.__logger.Info(self.globalVarsObj.TAG, "Step 5: Restore the previous state of the card by downloading")

       self.__logger.Info(self.globalVarsObj.TAG, " Restoring the card configuration")

       try:
           self.vtfContainer.DoProduction()
           self.__logger.Info(self.globalVarsObj.TAG, "[%s] Bot file download is successful"%moduleName)
           self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
           self.WaypointRegObj.RegisterWP(self.wayPointDict)            
       except:
           self.__logger.Info(self.globalVarsObj.TAG, "[%s] Error while downloading the bot file"%moduleName)
           raise ValidationError.TestFailError("","Error while downloading the bot file")	
       self.__logger.Info(self.globalVarsObj.TAG, "Test Passed ")     
       #end of __FSBlockCorruptionTest	


    #----------------------------------------------------------------------
    def __CorruptSingleFSBlock(self, FSBlockCopy, errorType, corruptWholeFSFlag):
        """
        Name        : __CorruptSingleFSBlock
        Description : Corrupt the Single FS block by executing the following steps
            #Step 2. Get the meta block address of the FS block 
            #Step 3. Get the latest primary and secondary addresses of the FS sector.
            #Step 4. Inject the data corruption to the FS sector as selected by user

        Arguments   :
           FSBlockCopy                : The copy of the File System block
           errorType                  : The type of error to be injected
                                           0 - Correctable ECC
                                           1 - Uncorrecable ECC  
           corruptImportantFileFlag   : To corrupt the important files or not
                                           0 - Don't Corrupt important file's except MAP file
                                           1 - Corrupt All important files.         
        Returns    :   None   
        """
        moduleName = "__CorruptSingleFSBlock"

        # Injecting UECC into the selected file corruptedFileId
        self.__logger.Info(self.globalVarsObj.TAG, "[%s] The FS copy chosen to CORRUPT is %d (0-Primary and 1-Secondary)\n"%(moduleName,FSBlockCopy))

        self.__corruptFileList = self.sctpUtilsObj.GetListOfRwFiles()

        if 239 in self.__corruptFileList:
            self.__corruptFileList.remove(239)#Excluding File 239 as it holds System Partition Table
        if 33 in self.__corruptFileList:
            self.__corruptFileList.remove(33)#Excluding File 33 as it holds USB Config
            
        CorruptFileID = self.__randomObj.choice(self.__corruptFileList)
                      
        #Get exact physical location from Meta block address. 
        self.fileCBSAddr,sectorPositionInEccPage = self.__sdfsObj.GetFilePhysLocation(CorruptFileID, Copy = FSBlockCopy)
        self.__logger.Info("", "Injecting error on File %d" % (CorruptFileID))
        #Step 4. Inject the data corruption to the FS sector as selected by user           
        self.fileCBSAddr.isTrueBinaryBlock = True
        
        self.phyAddr = self.ldpcObj.ApplyUECCSTM(PhyAddr=self.fileCBSAddr, Page="SLC")
        return    
   
    def OnUECCDetected(self, args):
        self.UECCDetected = True
        return
    

    def FileWrite(self):
	"""
	Name       :    FileWrite
	Description:    Do some random number of writing file This would lead to Boot Block updation 
  
	Arguments  :    
	   randomObj     :    Random object.  
	Return     :    None
	"""
       
	moduleName = "BOOTEI02_ECCTest"
	
	listOfRwFiles =  self.__fsbootLib.GetFileList()
    
	randomNumber = self.__randomObj.randint(1, RAND_COUNT1)
	for count2 in range(randomNumber):
	    self.__fsbootLib.FileWrite(listOfRwFiles)
	    
    def BootBlockCorruptionTest( self,  corruptPrimary, corruptSecondary, 
                                  primaryErrorType, secondaryErrorType, corruptAllBootPages):
	"""
	Name       :   BootBlockCorruptionTest
	Description:   Performs the boot block corruption test for different test scenario
			2. Get boot block(either primary or secondary) and the type of errors to inject (correctable or uncorrectable) from user
			3. Get the meta block address of the boot block 
			4. Get the latest primary and secondary addresses of the FSBS sector.
			5. Inject the data corruption to the last FSBS sector in chosen bootblock copy and specified error type
			   Power cycle the card and check whether card boots up or not
			   Restore the previous state of the card by downloading
	Arguments  :          
	   randomObj           : randomObj      
	   corruptPrimary      : Check whether to corrupt the primary boot block or not
				       0-Dont Corrupt
				       1-Corrupt
	   corruptSecondary    : Check whether to corrupt the Secondary boot block or not
				       0-Dont Corrupt
				       1-Corrupt
	   primaryErrorType    : type of error to be injected in primary boot block
				       0-correctable ECC error
				       1-Uncorrectable ECC error
	   secondaryErrorType  : type of error to be injected in secondary boot block
				       0-correctable ECC error
				       1-Uncorrectable ECC error
	   botFilename         : The bot file has to download
	   corruptAllBootPages    : Corrupt the first obselete boot page to the latest boot page with the Primary and secondary error type. 
	Returns:        None
  
	"""
	#the following steps are taken care in the function
	#Step 2. Get boot block(either primary or secondary) and the type of errors to inject (correctable or uncorrectable) from user
	#Step 3. Get the meta block address of the boot block 
	#Step 4. Get the latest primary and secondary addresses of the FSBS sector.
	#Step 5. Inject the data corruption to the FSBS sector as selected by user
	self.__logger.Info(self.globalVarsObj.TAG, "Executing steps 2 to 5 of the algorithm")
	#Corrupting both the boot blocks except a single copy of Latest boot block(Either from primary or secondary)
	if corruptAllBootPages:
	    if corruptPrimary: #Corrupt the whole primary boot and partial Secondary boot
		self.CorruptSingleBootBlock( g_PrimaryCopy, primaryErrorType, CORRUPT, DELETE_LATEST_BOOT_PAGE)
		self.CorruptSingleBootBlock( g_SecondaryCopy, secondaryErrorType, CORRUPT, DONT_DELETE_LATEST_BOOT_PAGE)
	    elif corruptSecondary:#Corrupt the partial primary boot and Whole Secondary boot
		self.CorruptSingleBootBlock( g_PrimaryCopy, primaryErrorType, CORRUPT, DONT_DELETE_LATEST_BOOT_PAGE)
		self.CorruptSingleBootBlock( g_SecondaryCopy, secondaryErrorType, CORRUPT, DELETE_LATEST_BOOT_PAGE)
	elif not corruptAllBootPages:      
	   #Corrupting either of the boot blocks
	   #corrupting primary boot block
	    if ((corruptPrimary) and (not corruptSecondary)):
		if primaryErrorType ==g_CorrectableECC:
		    self.CorruptSingleBootBlock( g_PrimaryCopy, g_CorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		elif primaryErrorType == g_UnCorrectableECC:
		    self.CorruptSingleBootBlock( g_PrimaryCopy, g_UnCorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
  
	   #corrupting secondary boot block         
	    elif ((not corruptPrimary) and (corruptSecondary)):
		if secondaryErrorType ==g_CorrectableECC:
		    self.CorruptSingleBootBlock( g_SecondaryCopy, g_CorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		elif secondaryErrorType == g_UnCorrectableECC:
		    self.CorruptSingleBootBlock( g_SecondaryCopy, g_UnCorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
	   
	    elif corruptPrimary and corruptSecondary:#Corrupting both the boot blocks
		if primaryErrorType == g_CorrectableECC and secondaryErrorType == g_UnCorrectableECC:
		    self.CorruptSingleBootBlock( g_PrimaryCopy, g_CorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		    self.CorruptSingleBootBlock( g_SecondaryCopy, g_UnCorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		elif primaryErrorType == g_UnCorrectableECC and secondaryErrorType == g_CorrectableECC:
		    self.CorruptSingleBootBlock( g_PrimaryCopy, g_UnCorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		    self.CorruptSingleBootBlock( g_SecondaryCopy, g_CorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		elif primaryErrorType == g_CorrectableECC and secondaryErrorType == g_CorrectableECC:
		    self.CorruptSingleBootBlock( g_PrimaryCopy, g_CorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		    self.CorruptSingleBootBlock( g_SecondaryCopy,g_CorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		elif primaryErrorType == g_UnCorrectableECC and secondaryErrorType == g_UnCorrectableECC:
		    self.CorruptSingleBootBlock( g_PrimaryCopy, g_UnCorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		    self.CorruptSingleBootBlock( g_SecondaryCopy, g_UnCorrectableECC, DONT_CORRUPT, DELETE_LATEST_BOOT_PAGE)
		else:
		    self.__logger.Info(self.globalVarsObj.TAG, "[BOOTEI02_ECC] ECC error not injected because of invalid input arguments !!!")
  
	#Do a power cycle and verify the bootability of the card
	self.__logger.Info(self.globalVarsObj.TAG, "Step 5. Power cycle the card")

	
	try:  
	    self.livet.GetCmdGenerator().PowerOff(0)
	    self.livet.GetCmdGenerator().PowerOn() 
	    self.FileWrite()# added 
	    self.__logger.Info(self.globalVarsObj.TAG, "[BOOTEI02_ECC] The card recovered properly after a powercycle")
	except:
	    self.__logger.Info(self.globalVarsObj.TAG, "[BOOTEI02_ECC] The card did not recover properly after a powercycle")
	    return False  
	   
	#except Exception as exc:
	    #self.__logger.Info(self.globalVarsObj.TAG, "[BOOTEI02_ECC] Got CardCommandError exception: %s" % exc)
	    #raise ValidationError.TestFailError("","The Card was not able to boot,after corruting a FileSystem Boot sector in the boot block ,though the redundant copy is present")
	#except:
	    #self.__logger.Info(self.globalVarsObj.TAG, "The Card was not able to boot,after corrupting a FileSystem Boot sector in the boot block ,though the redundant copy is present")
	    #raise
	self.__logger.Info(self.globalVarsObj.TAG, "[BOOTEI02_ECC] Power cycling the card -SUCCESSFUL.")
	return True

	

    def CorruptSingleBootBlock(self, bootBlockCopy, errorType, 
                               corruptAllBootPages, LatestBootPageCorruptFlag):
	"""
	Name        : CorruptSingleBootBlock
	Description : Corrupt the Single boot block either from the first obselete boot page to the latest 
		      boot page based on the following
	   if (corruptAllBootPages is enable and LatestBootPageCorruptFlag was disabled)
	       - Corrupt from the first obselete boot page to the latest boot page. 
	   else if (corruptAllBootPages is enable and LatestBootPageCorruptFlag was enable)    
	       - Corrupt from the first obselete boot page to except latest boot page.
	   else if (corruptAllBootPages is disable and LatestBootPageCorruptFlag was enable)  
	       - Corrupt the first obselete boot page and middle boot page.
	   else if (corruptAllBootPages is disable and LatestBootPageCorruptFlag was disable)  
	       - Corrupt the first obselete boot page, middle boot page and the latest boot page. 
	Arguments   :
	   bootBlockCopy         : The copy of the boot block
	   errorType             : The type of error to be injected
				       0 - Correctable ECC
				       1 - Uncorrecable ECC  
	   corruptAllBootPages   : To corrupt the entier boot or not
				       0 - Don't Corrupt the first obselete boot page to the latest boot page.
				       1 - Corrupt the first obselete boot page to the latest boot page 
					   if LatestBootPageCorruptFlag-bit is set to 0.
	   LatestBootPageCorruptFlag  : Condition to corrupt the Latest boot page.
				       0 - corrupt the Latest boot page also.
				       1 - Except the latest boot page(Last Boot).
	Returns    :   None   
	"""
	moduleName = "CorruptSingleBootBlock"          
 
	ctrlBlockInfo = ControlBlockInfo.ControlBlocksInfo(self.vtfContainer)
       
	self.__logger.Info(self.globalVarsObj.TAG, "[CorruptSingleBootBlock] Finding the latest FSBS entry in BootBlock %d Copy "%bootBlockCopy)
	if bootBlockCopy == g_PrimaryCopy:
	    primaryCopy = True
	    latestBootPageAddress = ctrlBlockInfo.GetLatestPriFsbsAddr() #self.__sdfsObj.GetBootPageAdddress(primaryCopy) #To get the latest boot page address.
	else:
	    primaryCopy = False
	    latestBootPageAddress = ctrlBlockInfo.GetLatestSecFSBSAddr()
       
	startBootAddress = latestBootPageAddress & 0xffff0000 # To Extract the starting boot block address.
	middleBootPage =  int (latestBootPageAddress/2)             
	self.__logger.Info(self.globalVarsObj.TAG, "[CorruptSingleBootBlock] The last Boot Page entry in BootBlock %d Copy is 0x%X "%(bootBlockCopy,latestBootPageAddress))
	for CurrentBootPageAddr in range(startBootAddress,latestBootPageAddress+self.SECTORS_PER_PAGE,self.SECTORS_PER_PAGE):
	    if ( (CurrentBootPageAddr == latestBootPageAddress)or(corruptAllBootPages) ):
		if(not ((CurrentBootPageAddr == startBootAddress) and (corruptAllBootPages) and (not LatestBootPageCorruptFlag) )):
		    continue
		if(CurrentBootPageAddr == latestBootPageAddress):
		    if(LatestBootPageCorruptFlag):
			break
	    if (CurrentBootPageAddr == 0x00):
		continue

	self.__logger.Info(self.globalVarsObj.TAG, "\n")  
	self.__logger.Info(self.globalVarsObj.TAG, "[CorruptSingleBootBlock]Step 3. The FSBS in BootBlock %d Copy is 0x%X "%(bootBlockCopy,CurrentBootPageAddr))
	fsbsCBSAddr,sectorPositionInEccPage = self.sctpUtilsObj.TranslateMetaToPhysical( CurrentBootPageAddr,0,self.__fwConfigData)     
	self.__logger.Info(self.globalVarsObj.TAG, "[CorruptSingleBootBlock]Step 4. Injecting  ECC errors in the FSBS in BootBlock %d Copy "%bootBlockCopy)
	self.__logger.Info(self.globalVarsObj.TAG, "\n") 
	 #Inject Uncorrectable error into the physical location
	fsbsCBSAddr.isTrueBinaryBlock = True
	if errorType==g_CorrectableECC:
	    self.eiObj.InjectCECCErrorWithSTM(errorPhyAddress=fsbsCBSAddr, 
	                                     isCalledFromWaypoint=False, 
	                                     mode=None, 
	                                     blktype='slc', 
	                                     entireBlock=None, 
	                                     applyOnlyToPhysicalPage=False, 
	                                     applyOnlyToEccPage=False)
	elif errorType == g_UnCorrectableECC:
	    self.eiObj.InjectUECCErrorWithSTM(errorPhyAddress=fsbsCBSAddr, 
	                                     isCalledFromWaypoint=False, 
	                                     isForceUECC=False, 
	                                     blktype='slc',
	                                     applyOnlyToPhysicalPage=False, 
	                                     applyOnlyToEccPage=False, 
	                                     isToBeAppliedToBlock=False)
    def UECCHandlerBOOT(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING BOOT UECC HANDLER *************')
	self.__fsbootLib = FSBootLib.BootUtils( self.__fwConfigData, 
	                                               self.__applicationRunAttributesObj)	
	self.__ctrlBlockInfo = ControlBlockInfo.ControlBlocksInfo(self.vtfContainer)
	#Step 1: Do Random Writes
	moduleName = "BOOTEI02_ECCTest"
	self.__commandCount = self.__randomObj.randint(100, 400) # random Choice.
	start_lba = 0	
	for i in range(0,self.__commandCount):
	    txLen = random.randrange(0x10,0x70)
	    self.__ccmObj.Write(start_lba,txLen)
	    start_lba += txLen       
	 #Step:2 to Step:7                  
         #Corrupting either one of the boot blocks(Primary or Secondary)
         
	self.__logger.Info(self.globalVarsObj.TAG, "[%s]Step: 2.2 Injecting UECC to Primary Boot block alone"%moduleName)
	self.FileWrite()
	self.BootBlockCorruptionTest(  CORRUPT,DONT_CORRUPT,g_UnCorrectableECC,None , DONT_CORRUPT)
         
	self.__logger.Info(self.globalVarsObj.TAG, "[%s]Step: 2.3 Injecting UECC to Secondary Boot block alone"%moduleName)
	self.FileWrite()
	self.BootBlockCorruptionTest(  DONT_CORRUPT, CORRUPT,None,g_UnCorrectableECC , DONT_CORRUPT)
	

	self.__logger.Info(self.globalVarsObj.TAG, "[%s]Step: 2.7 Injecting UECC into the Primary Boot block except the latest Boot page and to all the written pages of Secondary Boot block."%moduleName)
	self.FileWrite()
	self.BootBlockCorruptionTest( DONT_CORRUPT, CORRUPT,g_CorrectableECC,g_UnCorrectableECC , CORRUPT)
         
         
        self.__logger.Info(self.globalVarsObj.TAG, "[%s]Step: 2.8 Injecting UECC into all the written pages of the Primary Boot block  and to all the written pages of Secondary Boot block except the latest Boot page."%moduleName)
	self.FileWrite()
	self.BootBlockCorruptionTest( CORRUPT, DONT_CORRUPT, g_UnCorrectableECC,g_CorrectableECC , CORRUPT)

	
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()	                    
        
        self.logger.Info(self.globalVarsObj.TAG, "############ BOOT UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
