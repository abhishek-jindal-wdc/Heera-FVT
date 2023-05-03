##
#***********************************************************************************************
# @file            : EINCTD_Library.py
# @brief           : This is a library meant for all CTD related methods, such as those related to read/write/erase/error injections/handling
# @author          : Adarsh 
# @date(ORG)       : 28 Jan 19
# @copyright       : Copyright (C) 2018 SanDisk Corporation
#***********************************************************************************************

##
# @detail Internal Generic Validation libraries here
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import WaypointReg
import Utils
import CMDP_SCSIFE_Library
import Extensions.CVFImports as pyWrap
# @detail Internal Module Specific libraries here
import FwConfig as FwConfig
import CMDP_Router
# @detail External libraries here
import CMDP_History as History
#import Precondition

##
# @brief  The Library class
# @detail Some of the groups of methods present in this class are
#         Writes(Sequential, Random, Overlapped) 
#         Reads(Sequential, Random, Overlapped)
#         Ensuring Safe Lbas and Transfer Lengths are picked
#         Reading written data and cleaning up variables at the end of a test
# TODO    Must fail if is invoked explicitly, as this only a library and not a standalone test in itself
class EINCTD_Library(object):
    __staticEINCTDObj = None
    __staticEINCTDObjCreated   = False
    def __new__(cls, *args, **kwargs):

        if not EINCTD_Library.__staticEINCTDObj:
            EINCTD_Library.__staticEINCTDObj = super(EINCTD_Library,cls).__new__(cls, *args, **kwargs)

        return EINCTD_Library.__staticEINCTDObj
    ##
    # @brief   This will initialize some basic variables to be used frequently by the test 
    # @details Most of the variables are to be kept private to ensure data encapsulation
    #          They must not be accesible by tests who use this library
    #          They are all class attributes so that they can be accessed by all class methods 
    # @param   None
    # @return  None
    def __init__(self, vtfContainer):
        if EINCTD_Library.__staticEINCTDObjCreated:
            return
        EINCTD_Library.__staticEINCTDObjCreated = True
        super(EINCTD_Library, self).__init__()	
        # Utils & Global Vars
        self.vtfContainer = vtfContainer
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()    
        self.ccmObj = self.globalVarsObj.ccmObj
        self.sctpUtilsObj = self.globalVarsObj.sctpUtilsObj
        self.utilsObj = Utils.Utils()
	self.livetObj = self.vtfContainer._livet
	self.__livetFlash = self.livetObj.GetFlash() 
        self.__livetFlash.TraceOn("data_write")
	self.__livetFlash.TraceOn("data_read")
        self.__livetFlash.TraceOn('error_injected')
        self.__livetFlash.TraceOn('error_occurred') 	
	self.epwrBlocks = list()
	self.errorAffectedLbaUECC = list()
	self.UECCInjectionList = list()
        self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)
        #Precondition.DoPreconditioning() # Inject bad blocks
        # Other frequently used objects
        self.randomObj = self.globalVarsObj.randomObj
        self.tag = self.globalVarsObj.TAG
        self.logger = self.globalVarsObj.logger
        self.cmdpRouterLib = CMDP_Router.Router()
        # other initialisations
        self.InitialiseFWConfigVariables()
        self.InitialiseTestVariables()
        self.HistoryObj = History.EpicCallbacks()
        # FE Libraries
        self.cmdpScsiFeLib = CMDP_SCSIFE_Library.CMDP_SCSIFE_Library(self)

        #--------------------------------------------------------------------------------------------------
        # Model Check
        if self.globalVarsObj.vtfContainer.systemCfg.isModel:
            self.wayPointLibObj = WaypointReg.WaypointReg(self.globalVarsObj.vtfContainer._livet, self.globalVarsObj.logger, globalVarsObj=self.globalVarsObj)            
            self.RegisterWaypoints()

    ##
    # @brief   This will initialize some config related variables
    def InitialiseFWConfigVariables(self):
        #self.sctpUtilsObj.IdentifyDrive()
        #self.ccmObj.GetFeatureVWC()          
        self._currentLba        = 0
        self.__sectorsInADiePage = self.__fwConfigObj.sectorsPerPage #self.globalVarObj.lbasInPhyPage
        self.__sectorsIn4KChunk  = self.__fwConfigObj.sectorsPerLgFragment #Constants.XFERLENGTH_4K_IN_SECTORS
        self.__maxLba            = self.globalVarsObj.maxLba
        self.__numberOfFIMs      = self.__fwConfigObj.numChips
        # flash ID will be in the format flash=FV_BiCS4_96L_4ST_X3_256G_2P_1D
        self.__numberOfDies      = self.globalVarsObj.Model_ini_Die_Interleave
        self.__planesInADie      = self.globalVarsObj.Model_ini_Plane_Interleave
        self.__mlcLevel          = self.globalVarsObj.Model_ini_BitsPerCell
        self.__numberOfStrings   = self.__fwConfigObj.stringsPerBlock
        self.__numberOfWordlines = self.__fwConfigObj.wordLinesPerPhysicalBlock
        #self._numberOfMetaDies  = 4
        self.__sectorsInAPhyPage = self.__fwConfigObj.sectorsPerPage
        self.__sectorsPerSLCMB   = self.__fwConfigObj.slcMBSize
        self.__sectorsPerTLCMB   = self.__fwConfigObj.mlcMBSize
        self.__sectorsIn1GigaByte  = 2 * 1024 * 1024
        self.__sectorsIn10MegaByte = 2 * 1024 * 10
        return 

    ##
    # @brief   This will initialize some basic flags to be used frequently by the test    
    def InitialiseTestVariables(self):
        # Test related variables
        # this variable is mainly used in the No EI scenario: it will be set to true once the required number of writes are performed as specified in the .ini file
        self.isWritesToBeStopped = False
        # this list is to be filled with every write so that in the end when reads are to be performed this can be referenced
        self._listOfWrites = list()	
        # this variable is mainly used in the EI scenario; writes will keep happening until this is set to true, i.e. once we encounter an error
        self.isErrorPhaseHit = False
        # this test is to keep track of writes issued for the current test, as we have to issue power cycle at regular command frequencies
        self._currentTestWriteCount = 0        
        # RLC related counters
        self.isSLCToTLCRelocationStart = False
        self.isTLCToSLCRelocationStart = False
        self.injectErrorInRLCDestBlock = False
        self.injectErrorDuringDST = False
        self.injectErrorDuringBootBlockUpdate = False
        self.injectErrorDuringXORBlockFlush = True
        return 

    # Currently keeping all WPs commented as it slows down execution time
    # During debugging, these can be uncommented as required
    def RegisterWaypoints(self):
        if self.globalVarsObj.vtfContainer.systemCfg.isModel:
              #self.wayPointLibObj = WaypointReg.WaypointReg(self.livetObj, self.logger, self.globalVarsObj)
            self.wayPointDict = {
                        "UM_READ"                    : [],
                        "UM_WRITE"                   : [],
                        "EPWR_START"                 : [self.OnEPWRStart],
	                #"SLC_COMPACTION_DATA_TRANSFER_BEGIN" : [],
	                #"MLC_COMPACTION_DATA_TRANSFER_BEGIN" : [],	                
                        "EPWR_COMPLETE"              : [],
	                #"EPWR_PHY_ADDRESS"           : [],
	                #"LDPC_HDR_UECC"              : [],
                        #"GCC_SRC_SELECT"             : [],
                        #"GCC_GOING_TO_WRITE"         : [],
	                #"GCC_GOING_TO_READ"         : []
                        }
                        
            self.wayPointLibObj.RegisterWP(self.wayPointDict)
            return 

    # @brief   This is to be called by the main test for each row to be executed in the sheet, by sending relevant details
    # @param   combinationForCurrentTest This dictionary has all user configurations stored, as per ini
    #          We can change logic as per user's choice
    # @param   userConfigurations : This dictionary has all test attribute values stored
    #          We should call methods as per values present
    # @details This searches for particulars of the tests, and calls specific methods accordingly to attain desired functionality
    # @return  None     
    def ExecuteTest(self, combinationForCurrentTest, userConfigurations):
	self.RegisterWaypoints()
        if combinationForCurrentTest == None:
            raise ValidationError.VtfGeneralError("EINCTD_Library.ExecuteTest", "Parameter combinationForCurrentTest cannot be None")
        else:
            self._combinationForCurrentTest = combinationForCurrentTest
        if userConfigurations == None:
            raise ValidationError.VtfGeneralError("EINCTD_Library.ExecuteTest", "Parameter combinationForCurrentTest cannot be None")
        self._userConfigurations = userConfigurations
        
        #--------------------Heera doesnot support----------------------------------------------------
        # this is for the init as required by the test
        #self.InitInMode(self._combinationForCurrentTest['ModeBeforeSwitch'])
        
        # Issue some random FE operation
        self.cmdpScsiFeLib.IssueRandomOperation()

        # Perform Writes
        self.HandleWrites()
        
        # Issue some random FE operation
        self.cmdpScsiFeLib.IssueRandomOperation()
        
        
        #---------------------------------------------------------------------------------------------
        # check if the specified number of writes are hit
        if self.isWritesToBeStopped:
            # only then perform init in the same/other mode
            #self.InitInMode(self._combinationForCurrentTest['ModeAfterSwitch'])
            pass
        else:
            self.logger.Info(self.tag, "Writes not fully completed as asked. continue ")
            # check if this scenario is ever hit
        return

    # @brief      Calls Write method, but performs related check
    # @brief      Note that these scenarios are avoided during choosing lba txLen, this is just a fail-safe mechanism
    # @param lba   : Start Lba
    # @param txLen : Transfer Length
    # @details    Some of the checks required are
    #             1) Max lba check - ensure lba+txLen < maxLba
    #             2) Out of range check 
    #             3) Max Transfer Length check
    # @exception  If either of the above checks fail, throws exception
    # @return     None    
    def PerformWrite(self, lba, txLen):
        if ((lba < 0) or (lba >= self.globalVarsObj.maxLba)):
            module = 'EINCTD_Library.PerformWrite'
            baseErrorDescription = 'lba value "{}" not in range {}..{}'.format((lba+txLen), 0, self.globalVarsObj.maxLba)
            extraErrorDescription = 'Given Lba was beyond maxLba, so resetting it to 0'
            self.logger.Info(self.globalVarsObj.TAG, baseErrorDescription)
            self.logger.Info(self.globalVarsObj.TAG, extraErrorDescription)
            self._currentLba = 0
            #raise ValidationError.VtfGeneralError(module, baseErrorDescription, extraErrorDescription)
        elif txLen < 0 or txLen > self.globalVarsObj.MDTS:
            module = 'EINCTD_Library.PerformWrite'
            baseErrorDescription = 'txLen value "{}" not in range {}..{}'.format(txLen, 0, self.globalVarsObj.MDTS)
            extraErrorDescription = 'Transfer Length is beyond maximum permissible length'
            raise ValidationError.VtfGeneralError(module, baseErrorDescription, extraErrorDescription)
        elif (lba + txLen) > self.globalVarsObj.maxLba:
            module = 'EINCTD_Library.PerformWrite'
            baseErrorDescription = 'lba value "{}" not in range {}..{}'.format((lba+txLen), 0, self.globalVarsObj.maxLba)
            extraErrorDescription = 'Given Lba was beyond maxLba, so resetting it to 0'
            self.logger.Info(self.globalVarsObj.TAG, baseErrorDescription)
            self.logger.Info(self.globalVarsObj.TAG, extraErrorDescription)
            self._currentLba = 0
            #raise ValidationError.VtfGeneralError(module, baseErrorDescription, extraErrorDescription)
        else:
            # make note of the write in the list
            self._listOfWrites.append((lba, txLen))
            # Store the last written lba/txLen, so that other cmdp libraries can refer
            self.HistoryObj.HistoryObj.GlobalWriteData.append((lba, txLen))
            # Issue the write command - try catch is present for writes and reads
            self.ccmObj.Write(lba, txLen)

            #--------------------------------Heera doesnt support--------------------------------------------
            #if self.globalVarsObj.vtfContainer.getActiveProtocol() == 'NVMe_OF_SDPCIe':
                #self.ccmObj.Write(lba, txLen)
            #elif self.globalVarsObj.vtfContainer.getActiveProtocol() == 'SD_OF_SDPCIe':
                #if txLen == 1:
                    #self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'WLBA: %d TxLen: 1'%(lba))
                    #self.cmdpSdfeLib.SdCmdsCls.CMD24(lba)
                #else:
                    #self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'WLBA: %d TxLen: %d'%(lba, txLen))
                    #self.cmdpSdfeLib.SdCmdsCls.CMD25(lba, txLen)
            #-------------------------------------------------------------------------------------------------

            # increment write command count for this test  
            # TODO Make powercycle occur for both read and write cmds, i.e. maintain both counts per test
            self._currentTestWriteCount += 1
            # this is to check whether EI is to be used or not
            # TODO Come up with a better solution, than checking after every write
            # short circuit mechanism: skips checking the second condition if the first condition itself is false
            if ((self._userConfigurations['WritesAndReads']['UseEI']=='No') and (self._currentTestWriteCount >= int(self._userConfigurations['WritesAndReads']['NumberOfWriteCommands']))):
                self.isWritesToBeStopped = True
            # although this method is out of place and should not be called here, for now, this is fine
            self.CheckAndIssuePowerCycle()
        return 

    # @brief   Performs reads for all the lbas and txLen stored in the list
    # @details This is to ensure written data is read back properly 
    # @param   None
    # @return  None    
    def PerformReads(self):
        while len(self._listOfWrites) > 0:
            tupleOfWrite = self._listOfWrites.pop()
            startLba, txLen = tupleOfWrite[0], tupleOfWrite[1]
            self.ccmObj.Read(startLba, txLen)
        self.CheckAndIssuePowerCycle()        
        return 
    def OnEPWRStart(self,argDict):
	if argDict["Block"] not in self.epwrBlocks:
	    self.epwrBlocks.append(argDict["Block"])
	    #if self.blk_for_epwr == argDict["Block"]:
		#self.epwr_start_flag = True  
		
	return
    # @brief   this will appropriately switch the mode as required , both before and after the switch
    # @details This searches for particulars of the tests, and calls specific methods accordingly to attain desired functionality
    # @param   mode : which mode to init in, whether SD or PCIe; each init will behave differently
    #          default will be set to PCIe
    # @return  None
    def InitInMode(self, mode='PCIe'):
        if mode=='SD':
            if self.globalVarsObj.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe":
                self.logger.Info(self.tag, "Currently in PCIe mode, Switching to SD mode")
                type_of_switch = self.globalVarsObj.randomObj.choice(["GSD","ABORT"])
                self.logger.Info(self.tag, "Type of switch mode used : {}".format(type_of_switch))
                self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType=type_of_switch)
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode=True
                self.cmdpScsiFeLib.inLowVoltageMode = False
            elif self.globalVarsObj.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe":
                self.logger.Info(self.tag, "Currently in SD mode, Continuing in SD mode")
        elif mode=='PCIe':
            if self.globalVarsObj.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe":
                self.logger.Info(self.tag, "Currently in SD mode, Switching to PCIe mode")
                #remove them when support for SD->PCIe switch is enabled
                self.globalVarsObj.vtfContainer.switchProtocol()
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode=False
                self.cmdpScsiFeLib.inLowVoltageMode = False
            elif self.globalVarsObj.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe":
                self.logger.Info(self.tag, "Currently in PCIe mode, Continuing in PCIe mode")
        return

    # @brief   mimics user defined sequential patterns, i.e. chunks of data written in sequeunce
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, sets lba to current position and again chooses a different txLen in a loop
    # @param numberOfWrites     : Number of Writes to issue, since this is for measured writes
    # @param sectorsToBeWritten : Total sectors to be written, since this is for measured writes
    # @param txLenThreshold     : Maximum txLen that can be issued per write
    # @return  None
    def DoMeasuredSequentialWrite(self, numberOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):                        
        if numberOfWrites is not None:
            # as a first step, we get the transfer len and align lba
            txLen = self.GetTransferLength(txLenThreshold)
            self.SetLba(txLen)            
            for i in range(numberOfWrites):
                # logic same as the one within while loop, just the exit criterias are different
                self.PerformWrite(self._currentLba, txLen)
                self._currentLba += txLen
                txLen = self.GetTransferLength(txLenThreshold)           
        elif sectorsToBeWritten is not None:
            # initially we get the txLen 
            txLen = self.GetTransferLength(sectorsToBeWritten, txLenThreshold)
            # we set the lba - for sequential writes we set it only once
            self.SetLba(txLen)
            # then keep looping until they're exhausted
            while sectorsToBeWritten > 0:
                self.PerformWrite(self._currentLba, txLen)  
                sectorsToBeWritten -= txLen
                txLen = self.GetTransferLength(sectorsToBeWritten, txLenThreshold)
                self._currentLba += txLen
        else:
            # get the number of writes from the ini file
            # and supply that as a parameter to the same function call
            self.DoMeasuredSequentialWrite(numberOfWrites=int(self._userConfigurations['WritesAndReads']['NumberOfWriteCommands']))

        return 

    # @brief   Keeps issuing Sequential Writes until a condition is met
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, sets lba to current position and again chooses a different txLen in a loop
    # @param flag : Flag which until set to True will keep writing. 
    #          This could be set to True on a specific waypoint/diag value hit, such as RLC Start
    # @return  None    
    def DoConditionalSequentialWrite(self, flag=None):
        if flag == None:
            while not self.isWritesToBeStopped:
                self.PerformWrite(self._currentLba, txLen)
                self._currentLba += txLen
                txLen = self.GetTransferLength() 
        else:
            while flag is not True:
                self.PerformWrite(self._currentLba, txLen)
                self._currentLba += txLen
                txLen = self.GetTransferLength()                 
        return 

    # @brief   The master function that calls one of the write functions based on the test vector
    # @param numOfWrites        : Applies to Measured Writes.
    # @param sectorsToBeWritten : Applies to Measured Writes.
    # @param flag               : Applies to Conditional Writes
    # @param txLenThreshold     : Max txLen allowed per write
    # @return  None
    def HandleWrites(self, numOfWrites = None, sectorsToBeWritten = None, flag=None, txLenThreshold=None):
        if self._combinationForCurrentTest["WritePattern"]=="Sequential":
            if flag == None:
                self.DoMeasuredSequentialWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)
            else:
                self.DoConditionalSequentialWrite(flag, txLenThreshold)
        elif self._combinationForCurrentTest["WritePattern"]=="Random":
            if flag == None:
                self.DoMeasuredRandomWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)
            else:
                self.DoConditionalRandomWrite(flag, txLenThreshold)
        elif self._combinationForCurrentTest["WritePattern"]=="Overlapped":
            if flag == None:
                self.DoMeasuredOverlappedWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)
            else:
                self.DoConditionalOverlappedWrite(flag, txLenThreshold)
        else:
            if flag == None:
                self.DoMeasuredSequential_RandomWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)         
            else:
                self.DoConditionalSequential_RandomWrite(flag, txLenThreshold)
        # Store the last written lba, so that other cmdp libraries can refer
        self.HistoryObj.HistoryObj.LastWrittenLBA = self._currentLba
        return 

    # @brief   Sets the start Lba based on configuration/ test vector
    # @details Add if-else block here if a new config type is to be introduced
    # @param   txLen : this is to ensure sum of lba and txLen dont exceed maxLba, so range is between min and max - txLen 
    # @return  None
    def SetLba(self, txLen):
        attributeValue = self._combinationForCurrentTest["LogicalLBAAlignment"]
        if attributeValue=="AlignedtoDiePage":
            self._currentLba = self.randomObj.randrange(0, self.globalVarsObj.maxLba - txLen, self.__sectorsInADiePage)
        elif attributeValue=="Unalignedto4K":
            lba = self.randomObj.randint(1, self.globalVarsObj.maxLba - txLen) 
            while (lba % self.__sectorsIn4KChunk) == 0:
                lba = self.randomObj.randint(1, self.globalVarsObj.maxLba - txLen)
            self._currentLba = lba
        elif attributeValue=="Alignedto4K":
            self._currentLba = self.randomObj.randrange(0, self.globalVarsObj.maxLba - txLen, self.__sectorsIn4KChunk)
        return

    # @brief   Randomly chooses a transfer length, as required by the configuration/test vector
    # @details Have to make sure a transfer length within MDTS is chosen 
    #          Using randrange we can choose without having to force align the txLen 
    #          The generated txLen will in multiples of the writeLength value only
    #          Add an if-else block if a new type is introduced
    # @param sectorsToBeWritten : Applies to Measured Writes
    # @param maxTxLen           : Max txLen per write
    # @return  txLen (-1 if not match)
    # randrange() will never choose the higher value, so 1 is added to the rhs values below so as to include them 
    def GetTransferLength(self, sectorsToBeWritten=None, maxTxLen=None):
        attributeValue = self._combinationForCurrentTest["WriteLength"]
        assert (maxTxLen <= self.globalVarsObj.MDTS), "User Max Transfer Length %d cannot be greater than device MDTS %d"%(maxTxLen, self.globalVarsObj.MDTS) 

        #-----------------------------------Heera doest support----------------------------------------------------------       
        #if self.globalVarsObj.vtfContainer.getActiveProtocol() == 'NVMe_OF_SDPCIe':
            #self.globalVarsObj.MDTS = 1024
            #maxTxLen = self.globalVarsObj.MDTS
        #else:
            ## Technically, there is no hard limit of transfer limit imposed by SD Spec, 
            ## but I have set to 4k sectors to avoid very high write times otherwise for even larger writes
            #self.globalVarsObj.MDTS = 0x1000
            #maxTxLen = 0x1000
        #---------------------------------------------------------------------------------------------------------------- 

        #--------------Heera supports max chunk size 0x400---------------------------------------------------------------	
        self.globalVarsObj.MDTS = 0x400
        maxTxLen = 0x400

        if attributeValue=="DiePageAligned":
            assert (maxTxLen >= self.__sectorsInADiePage), "Die Page Aligned requires transfer lengths in multiples of %d but user defined transfer length %d is lesser"%(self.__sectorsInADiePage, maxTxLen)
            if sectorsToBeWritten == None:
                txLen = self.randomObj.randrange(self.__sectorsInADiePage, maxTxLen+1, self.__sectorsInADiePage)
            else:
                # this means measured txLen
                if sectorsToBeWritten >= maxTxLen:
                    txLen = self.randomObj.randrange(self.__sectorsInADiePage, maxTxLen+1, self.__sectorsInADiePage)
                elif sectorsToBeWritten >= self.__sectorsInADiePage:
                    txLen = self.randomObj.randrange(self.__sectorsInADiePage, sectorsToBeWritten+1, self.__sectorsInADiePage)
                elif sectorsToBeWritten < self.__sectorsInADiePage:
                    # pad remaining sectors 
                    txLen = self.__sectorsInADiePage
            return txLen
        elif attributeValue=="SingleSector":
            return 1
        elif attributeValue=="Alignedto4K":
            if sectorsToBeWritten == None:
                txLen = self.randomObj.randrange(self.__sectorsIn4KChunk, maxTxLen+1, self.__sectorsIn4KChunk)
            else:
                if sectorsToBeWritten >= maxTxLen:
                    txLen = self.randomObj.randrange(self.__sectorsIn4KChunk, maxTxLen+1, self.__sectorsIn4KChunk)
                elif sectorsToBeWritten >= self.__sectorsIn4KChunk:
                    txLen = self.randomObj.randrange(self.__sectorsIn4KChunk, sectorsToBeWritten+1, self.__sectorsIn4KChunk)
                else:
                    return self.__sectorsIn4KChunk
            return txLen
        elif attributeValue=="Unalignedto4K":
            if sectorsToBeWritten == None:
                txLen = self.randomObj.randint(1, maxTxLen)   
                while (txLen % self.__sectorsIn4KChunk) == 0:
                    txLen = self.randomObj.randint(1, maxTxLen)           
            else:
                if sectorsToBeWritten == 0 or sectorsToBeWritten == 1:
                    txLen = sectorsToBeWritten
                elif sectorsToBeWritten >= maxTxLen:
                    txLen = self.randomObj.randint(1, maxTxLen) 
                    while (txLen % self.__sectorsIn4KChunk) == 0:
                        txLen = self.randomObj.randint(1, maxTxLen)
                else:
                    txLen = self.randomObj.randint(1, sectorsToBeWritten)
                    while (txLen % self.__sectorsIn4KChunk) == 0:
                        txLen = self.randomObj.randint(1, sectorsToBeWritten)   
            return txLen
        else:
            # no match
            # Maybe raise Exception?
            return -1

    # @brief   mimics user defined random patterns, i.e. chunks of data without any order
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, again chooses a different txLen and lba in a loop
    # @param   NumberOfWrites     : If we want only specific number of writes to be done in this pattern
    # @param   sectorsToBeWritten : Total sectors to be written with this pattern
    # @param   txLenThreshold     : max txLen allowed per write
    # @return  None
    def DoMeasuredRandomWrite(self, numberOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):
        if numberOfWrites is not None:
            for i in range(numberOfWrites):
                # logic same as the one within while loop, just the exit criterias are different
                txLen = self.GetTransferLength(maxTxLen=txLenThreshold)
                self.SetLba(txLen)
                self.PerformWrite(self._currentLba, txLen)
        elif sectorsToBeWritten is not None:
            # add logic here
            while sectorsToBeWritten > 0:
                # keep writing and reducing it to 0
                txLen = self.GetTransferLength(sectorsToBeWritten, maxTxLen=txLenThreshold)
                self.SetLba(txLen)
                self.PerformWrite(self._currentLba, txLen) 
                sectorsToBeWritten -= txLen
        else:
            # get the number of writes from the ini file
            # and supply that as a parameter to the same function call
            self.DoMeasuredRandomWrite(numberOfWrites=int(self._userConfigurations['WritesAndReads']['NumberOfWriteCommands']))            
        return

    # @brief   Keeps issuing Random Writes until a condition is met
    # @details 1) Gets the required txLen and lba is set according to the config
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, sets lba to current position and again chooses a different txLen in a loop
    # @param flag : Flag which until set to True will keep writing. 
    #          This could be set to True on a specific waypoint/diag value hit, such as RLC Start
    # @return  None    
    def DoConditionalRandomWrite(self, flag=None):
        # check whether the parameter has been passed at all
        # keep writing until we come out while loop
        if flag == None:
            while not self.isWritesToBeStopped:
                txLen = self.GetTransferLength()
                self.SetLba(txLen)
                self.PerformWrite(self._currentLba, txLen)
        else:
            while flag is not True:
                txLen = self.GetTransferLength()
                self.SetLba(txLen)
                self.PerformWrite(self._currentLba, txLen)                
        return 

    # @brief   Applies to Overlapped Writes, checks how many sectors to overlap wrt previous write
    # @details 1) Checks the configuration/ test vector, and selects startLba appropriately that will overlap to the previous write
    # @param txLen : Maximum txLen that can be sent
    # @return  the startLba to issue the next write on   
    def GetSectorsToOverlap(self, txLen):
        # how many sectors to increment now?
        lbasToIncrement = 0 # this variable will store how many to increment after each write so as to overlap 
        if self._combinationForCurrentTest['LogicalLBAAlignment'] == 'Unalignedto4K':
            lbasToIncrement = self.randomObj.randint(0, txLen)
            # to ensure that the lba that we have picked is not aligned to 4k
            while ((self._currentLba + lbasToIncrement) % self.__sectorsIn4KChunk == 0):
                lbasToIncrement = self.randomObj.randint(0, txLen)
        elif self._combinationForCurrentTest['LogicalLBAAlignment'] == 'AlignedtoDiePage':
            lbasToIncrement = self.randomObj.randrange(0, txLen, self.__sectorsInADiePage)
        elif self._combinationForCurrentTest['LogicalLBAAlignment'] == 'Alignedto4K':
            lbasToIncrement = self.randomObj.randrange(0, txLen, self.__sectorsIn4KChunk)
        self._currentLba += lbasToIncrement
        return lbasToIncrement

    # @brief   mimics user defined overlapped patterns, i.e. chunks of data written with subsequent writes overwriting part of current write
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, chooses an lba within the txLen(within written data) (making sure lba is aligned as required) and starts next write from there
    # @param   NumberOfWrites     : If we want only specific number of writes to be done in this pattern
    # @param   sectorsToBeWritten : Total sectors to be written with this pattern
    # @param   txLenThreshold     : max txLen allowed per write 
    # @return  None    
    def DoMeasuredOverlappedWrite(self, numOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):
        if numOfWrites is not None:
            txLen = self.GetTransferLength(txLenThreshold)
            self.SetLba(txLen)
            for i in range(numOfWrites):
                self.PerformWrite(self._currentLba, txLen)
                self._currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength(txLenThreshold)
        elif sectorsToBeWritten is not None:
            txLen = self.GetTransferLength(sectorsToBeWritten=sectorsToBeWritten, maxTxLen=txLenThreshold)
            self.SetLba(txLen)
            while sectorsToBeWritten > 0:
                self.PerformWrite(self._currentLba, txLen)
                sectorsToBeWritten -= txLen
                # how many sectors to increment now?
                self._currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength(sectorsToBeWritten=sectorsToBeWritten, maxTxLen=txLenThreshold)     
        else:
            # default function call
            # get the number of writes from the ini file
            # and supply that as a parameter to the same function call
            self.DoMeasuredOverlappedWrite(numOfWrites=int(self._userConfigurations['WritesAndReads']['NumberOfWriteCommands'])) 
        return

    # @brief   Keeps issuing Overlapped Writes until a condition is met
    # @details 1) Gets the required txLen and lba is set according to the config
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, sets lba to current position and again chooses a different txLen in a loop
    # @param flag : Flag which until set to True will keep writing. 
    #          This could be set to True on a specific waypoint/diag value hit, such as RLC Start
    # @return  None    
    def DoConditionalOverlappedWrite(self, flag=None):
        if flag == None:
            while not self.isWritesToBeStopped:
                self.PerformWrite(self._currentLba, txLen)
                self._currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength()
        else:
            while flag is not True:
                self.PerformWrite(self._currentLba, txLen)
                self._currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength()
        return

    # @brief   applies sequential and random patterns in succession
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, again chooses a different txLen and lba in a loop
    # @param   numberOfWrites     : If we want only specific number of writes to be done in this pattern
    # @param   sectorsToBeWritten : Total sectors to be written with this pattern
    # @param   txLenThreshold     : max txLen allowed per write
    # @return  None
    def DoMeasuredSequential_RandomWrite(self, numberOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):
        # if no ei is to be used then we split the number of writes into two unequal parts and call methods
        if (self._userConfigurations['WritesAndReads']['UseEI']=='No') or (numberOfWrites is not None) :
            # as it is mentioned in the .ini file that the writes have to be a multiple of 5
            # we divide the number of writes by 5 and alternatively issue 5 writes per write pattern
            writesIssuedPerWritePattern = 5 # HARDCODED value
            numOfWrites = int(self._userConfigurations['WritesAndReads']['NumberOfWriteCommands'])/writesIssuedPerWritePattern
            writesAlreadyIssued = 0
            while writesAlreadyIssued < numOfWrites:
                self.DoMeasuredSequentialWrite(numberOfWrites=writesIssuedPerWritePattern, txLenThreshold=txLenThreshold)
                writesAlreadyIssued += writesIssuedPerWritePattern
                self.DoMeasuredRandomWrite(numberOfWrites=writesIssuedPerWritePattern, txLenThreshold=txLenThreshold)
                writesAlreadyIssued += writesIssuedPerWritePattern
        else:
            # we have to use EI
            #handle this scenario
            # split 64 sectors to sequential then 64 to random
            val = 0
            while sectorsToBeWritten > 0:
                if val == 0:
                    self.DoMeasuredSequentialWrite(sectorsToBeWritten=64)
                    sectorsToBeWritten -= 64
                    val += 1
                else:
                    self.DoMeasuredRandomWrite(sectorsToBeWritten=64)
                    sectorsToBeWritten -= 64
                    val -= 1
        return

    # @brief   Applies Sequential and Random patterns in succession
    # @details 1) Gets the required txLen and lba is set according to the config
    #          2) Keeps on writing until asked to stop
    #          3) After each write, sets lba to current position and again chooses a different txLen in a loop
    # @param flag : Flag which until set to True will keep writing.
    #          This could be set to True on a specific waypoint/diag value hit, such as RLC Start
    # @return  None
    def DoConditionalSequential_RandomWrite(self, flag=None):
        numOfWritesBetweenSwitches = int(self._userConfigurations['WritesAndReads']['NumOfWritesSeqRanPattern'])
        if flag == None:
            while not self.isWritesToBeStopped:
                self.DoMeasuredSequentialWrite(numberOfWrites=numOfWritesBetweenSwitches)
                self.DoMeasuredRandomWrite(numberOfWrites=numOfWritesBetweenSwitches)        
        else:
            while flag is not True:
                self.DoMeasuredSequentialWrite(numberOfWrites=numOfWritesBetweenSwitches)
                self.DoMeasuredRandomWrite(numberOfWrites=numOfWritesBetweenSwitches)
        return

    # @brief   This is to ensure powercycle happens every now and then
    # @details Checks the frequency of IOs to issue powercycle mentioned in config/ test vector and issues once met
    # @param   None
    # @return  None    
    def CheckAndIssuePowerCycle(self):
        if self._combinationForCurrentTest['PowerCycle']=='NoPowerCycle':
            pass
        elif self._combinationForCurrentTest['PowerCycle']=='Frequent_25Commands':
            if self.globalVarsObj.totalIOCommandCount%25==0:
                self.logger.Info(self.tag, "issuing power cycle as per frequency set")
                self.utilsObj.PowerCycle()
            else:
                pass
        elif self._combinationForCurrentTest['PowerCycle']=='InFrequent_75Commands':
            if self.globalVarsObj.totalIOCommandCount%75==0:
                self.logger.Info(self.tag, "issuing power cycle as per frequency set")
                self.utilsObj.PowerCycle()
            else:
                pass
        return

    # @brief   Performs cleanup of test data for the current config/ test vector
    # @details 
    # @param   None
    # @return  None
    def ClearTestData(self):
        self.logger.Info(self.tag, "clearing test logs")
        del self._listOfWrites[:]
        del self.HistoryObj.HistoryObj.GlobalWriteData[:]
        self._currentTestWriteCount = 0
        self.isWritesToBeStopped = False
        return

    # @brief   Check if device enters RO
    # @details This is required for Format+Production
    # @param   
    # @return  None
    def WP_FTL_READONLY_TRIGGER_Callback(self,eventKeys, arg, processorID):
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "WP_FTL_READONLY_TRIGGER appeared with arguments: %s." %(str(arg)))
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Device has gone into read only mode")
        self._readOnlyMode = True
        self.ReInit()
        return

    # @brief   Issues Production
    # @details To be called when device gone to RO
    # @param   None
    # @return  None
    def ReInit(self,eventKeys, arg, processorID):
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Checking If the device has gone into RO Mode")
        self.isWritesToBeStopped = True
        self.ccmObj.DoProduction()
        return

    # @brief Diag to get information
    def GetDeviceConfigData(self):
        # need to ask diag here
        return

    # @brief Returns Current Lba
    def GetCurrentLBA(self):
        return self._currentLba