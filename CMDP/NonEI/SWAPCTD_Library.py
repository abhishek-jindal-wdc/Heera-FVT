##
#***********************************************************************************************
# @file            : SWAPCTD_Library.py
# @brief           : This is a library meant for all CTD related methods, such as those related to read/write/erase/error injections/handling
# @author          : Adarsh 
# @date(ORG)       : 28 Jan 19
# @copyright       : Copyright (C) 2018 SanDisk Corporation
#***********************************************************************************************

##
# @detail Internal Generic Validation libraries here
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import WayPointHandler
import Utils as Utils 
import FwConfig

# @detail Internal Module Specific libraries here
#import VBAToPBA_AddressTranslator as VBAToPBA
#from collections import OrderedDict

##
# @brief  The Library class
# @detail Some of the groups of methods present in this class are
#         Writes(Sequential, Random, Overlapped) 
#         Reads(Sequential, Random, Overlapped)
#         Ensuring Safe Lbas and Transfer Lengths are picked
#         Reading written data and cleaning up variables at the end of a test
# TODO    Must fail if is invoked explicitly, as this only a library and not a standalone test in itself
class SWAPCTD_Library():
    ##
    # @brief   This will initialize some basic variables to be used frequently by the test 
    # @details Most of the variables are to be kept private to ensure data encapsulation
    #          They must not be accesible by tests who use this library
    #          They are all class attributes so that they can be accessed by all class methods 
    # @param   None
    # @return  None        
    def __init__(self, vtfContainer):
        # Utils & Global Vars
        self.vtfContainer = vtfContainer
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()    
        self.ccmObj = self.globalVarsObj.ccmObj
        self.sctpUtilsObj = self.globalVarsObj.sctpUtilsObj
        self.utilsObj       = Utils.Utils()
        #self.eiLibObj = ErrorInjectorLib.ErrorInjectorLib(self.globalVarsObj.vtfContainer, self.globalVarsObj.logger)
        #self.dstObj = DSTBase.DST_Base(self.globalVarsObj.logger, self.globalVarsObj.vtfContainer)
        #self.addrTranslatorObj = VBAToPBA.VBAToPBA_AddressTranslator()
        # Other frequently used objects
        self.logger = self.globalVarsObj.logger       
        self.randomObj = self.ccmObj.randObj
        self.tag = self.globalVarsObj.TAG
        self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)
        # other initialisations
        self.InitialiseFWConfigVariables()
        self.InitialiseTestVariables()
        if self.globalVarsObj.vtfContainer.systemCfg.isModel:
            self.wayPointLibObj = WayPointHandler.WayPointHandler(self.globalVarsObj.vtfContainer._livet, self.globalVarsObj.logger, globalVarsObj=self.globalVarsObj)            
            self.RegisterWaypoints()
        self.RegisterRSWaypoints()
        
    def InitialiseFWConfigVariables(self):
        # TODO Must remove hardcoded values and take from Constants/globalVarsObj
        #if self.globalVarsObj.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe":
        #self.sctpUtilsObj.IdentifyDrive()
        #self.ccmObj.GetFeatureVWC()          
        self.__currentLba = 0
        self.__numberOfDies = self.__fwConfigObj.diesPerChip * self.__fwConfigObj.numChips
        self.__sectorsInADiePage = self.__fwConfigObj.sectorsPerPage * self.__numberOfDies#64
        self.__sectorsIn4KChunk = self.__fwConfigObj.sectorsPerLgFragment 
        self.__numberOfFIMs = 1
        self.__numberOfMetaDies = 1
        self.__numberOfStrings = 4
        self.__maxLba = self.globalVarsObj.maxLba
        self.__numberOfWordlines = self.__fwConfigObj.wordLinesPerPhysicalBlock_BiCS
        self.__pagesInABlock = self.__numberOfWordlines * 4
        self.__mlcLevel = 3
        self.__planesInADie = 2
        self.__chipCount = 4
        self.__sectorsPerSLCMB   = self.__fwConfigObj.slcMBSize 
        self.__sectorsPerTLCMB   = self.__fwConfigObj.mlcMBSize
        self.__txLenThresholdForRandomStream = 128
        self.__physicalBlocksPerJB = 8
        self.__sectorsIn1GigaByte = 2 * 1024 * 1024
        self.__sectorsIn10MegaByte = 2 * 1024 * 10
        return 
    
    def InitialiseTestVariables(self):
        # Test related variables
        # this variable is mainly used in the No EI scenario: it will be set to true once the required number of writes are performed as specified in the .ini file
        self.isWritesToBeStopped = False
        # this dictionary is to be filled with every write so that in the end when reads are to be performed this can be referenced
        self.__dictOfWrites = dict()
        # this variable is mainly used in the EI scenario; writes will keep happening until this is set to true, i.e. once we encounter an error
        self.isErrorPhaseHit = False
        # this test is to keep track of writes issued for the current test, as we have to issue power cycle at regular command frequencies
        self.__currentTestWriteCount = 0        
        #   
        #self.isSLCToTLCRelocationStart = False
        #self.isTLCToSLCRelocationStart = False
        #self.injectErrorInRLCDestBlock = False
        #self.injectErrorDuringDST = False
        #self.injectErrorDuringBootBlockUpdate = False
        #self.injectErrorDuringXORBlockFlush = True
        # ASIC/NAND Tempaerature, with default setting of 25C
        #self.current_asic_temp = 25
        #self.current_nand_temp = 25
        ## keeping track of which mode we are in
        #self.isInitToPCIeMode = False
        #self.isInitToSDMode = False
        return 
    
    def RegisterWaypoints(self):
        if self.globalVarsObj.vtfContainer.systemCfg.isModel:
            self.wayPointLibObj.RegisterWP({
                #"WP_FTL_OBM_JUMBO_BLOCK_ALLOC":['PrintArguments', self.WP_FTL_OBM_JUMBO_BLOCK_ALLOC_Callback],#new wp
                #"WP_FTL_OBM_JUMBO_BLOCK_WL":['PrintArguments'],
                #"WP_LOG_JUMBO_BLOCK_WL":['PrintArguments'],
                #"WP_FTL_MTM_JB_VBA":['PrintArguments'],
                #"WP_FTL_HWD_WRITE_JB_VBA":['PrintArguments', self.WP_FTL_HWD_WRITE_JB_VBA_Callback],
                #"D_MODEL_FTL_HWD_PADDING":['PrintArguments'],
                #"D_MODEL_FTL_HWD_STREAM_STATUS":['PrintArguments'],
                #"WP_FTL_MBM_METABLOCK_ERASED":['PrintArguments'], #new wp
                #"D_MODEL_FTL_HWD_START_WRITE":['PrintArguments'],
                #"WP_FTL_HWD_WRITE_JB_VBA":['PrintArguments'],
                #"WP_HOST_WRITE_COMPLETE":['PrintArguments'],
                #"D_MODEL_FTL_HWD_ROUTING_RULES":['PrintArguments'],
                #"WP_FWR_INFRA_FFU_WRITE_PARAMETERS":['PrintArguments'],
                #"WP_FTL_READONLY_TRIGGER":[self.WP_FTL_READONLY_TRIGGER_Callback],
                #"WP_MTM_GC_COMPLETE":['PrintArguments'],
                #"WP_FTL_XOR_JB_VBA":['PrintArguments'],
                #"WP_INFRA_IFS_IN_BOOTPAGE_UPDATE":['PrintArguments'],
                #"WP_FTL_RLC_RLC_START ":['PrintArguments', self.WP_FTL_RLC_RLC_START_Callback],
                #"WP_FTL_RLC_ALLOC_BRLC_BLOCK":['PrintArguments'],
                #"WP_FTL_RLC_AUTO_FREE_JB_RELEASED":['PrintArguments'],
                #"WP_FTL_RLC_SOURCE_BLOCK_RELEASED":['PrintArguments'],
                #"WP_FTL_RLC_SOURCE_BLOCK_SELECTED":['PrintArguments'],
                #"WP_FTL_RLC_TARGET_BLOCK_FULL":['PrintArguments'],
                #"WP_FTL_RLC_WRITE_JB_VBA":['PrintArguments'],
                #"WP_DST_VC_CHECK_FINISHED":['PrintArguments']
            })
        return

    # This library has been recently introduced to check whether any of the RS modules are started in SD mode
    # While this check should be present in RS/REH test groups, since SWAP involves lot of access patterns there
    # are higher chances of corner cases getting triggered
    def RegisterRSWaypoints(self):
        #self.wayPointLibObj.RegisterWP({
            #"WP_PS_RS_ACTIVE_SCAN_START":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_ADD_BLOCK_TO_RSCQ":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_ATTEMPT_ADD_TO_RSCQ_LIST":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_BLOCK_SENT_TO_RLC":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_HIGH_BER_EVENT":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_PROCESS_BLOCK_FROM_REH":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_RANDOM_SCAN_START":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_REMOVE_BLOCK_FROM_RSCQ":['PrintArguments', self.WP_PS_RS_Callback],
            #"WP_PS_RS_SKIP_SCAN_BLK_NOT_VALID":['PrintArguments', self.WP_PS_RS_Callback]
        #})
        return

    # @brief   This is to be called by the main test for each row to be executed in the sheet, by sending relevant details
    # @param   combinationForCurrentTest This dictionary has all user configurations stored, as per ini
    #          We can change logic as per user's choice
    # @param   userConfigurations This dictionary has all test attribute values stored
    #          We should call methods as per values present
    # @details This searches for particulars of the tests, and calls specific methods accordingly to attain desired functionality
    # @return  None     
    def ExecuteTest(self, combinationForCurrentTest, userConfigurations):
        self.__init__(self.vtfContainer)
        if combinationForCurrentTest == None:
            raise ValidationError.VtfGeneralError("SWAPCTD_Library.ExecuteTest", "Parameter combinationForCurrentTest cannot be None")
        else:
            self.__combinationForCurrentTest = combinationForCurrentTest
        if userConfigurations == None:
            raise ValidationError.VtfGeneralError("SWAPCTD_Library.ExecuteTest", "Parameter combinationForCurrentTest cannot be None")
        self.__userConfigurations = userConfigurations
        # this is for the init as required by the test
        
        #Set default temp values
        #self.SetThermalParameters(asic_temp_to_set=25, nand_temp_to_set=25)
        # Carry out writes
        self.HandleWrites()          
        # check if the specified number of writes are hit
        if self.isWritesToBeStopped:
            # only then perform init in the same/other mode
            self.__init__(self.vtfContainer)
        else:
            self.logger.Info(self.tag, "Writes not fully completed as asked. continue ")
            # check if this scenario is ever hit
            return 
    
    # @brief      Calls Write method, but performs related check
    # @brief      Note that these scenarios are avoided during choosing lba txLen, this is just a fail-safe mechanism
    # @details    Some of the checks required are
    #             1) Max lba check - ensure lba+txLen < maxLba
    #             2) Out of range check 
    #             3) Max Transfer Length check
    # @exception  If either of the above checks fail, throws exception
    # @return     None    
    def PerformWrite(self, lba, txLen):
        if ((lba < 0) or (lba >= self.globalVarsObj.maxLba)):
            module = 'SWAPCTD_Library.PerformWrite'
            baseErrorDescription = 'lba value "{}" not in range {}..{}'.format((lba+txLen), 0, self.globalVarsObj.maxLba)
            extraErrorDescription = 'Given Lba was beyond maxLba, so resetting it to 0'
            self.logger.Info(self.globalVarsObj.TAG, baseErrorDescription)
            self.logger.Info(self.globalVarsObj.TAG, extraErrorDescription)
            self.__currentLba = 0
            #raise ValidationError.VtfGeneralError(module, baseErrorDescription, extraErrorDescription)
        elif txLen < 0 or txLen > self.__fwConfigObj.mlcMBSize:
            module = 'SWAPCTD_Library.PerformWrite'
            baseErrorDescription = 'txLen value "{}" not in range {}..{}'.format(txLen, 0, self.globalVarsObj.MDTS)
            extraErrorDescription = 'Transfer Length is beyond maximum permissible length'
            raise ValidationError.VtfGeneralError(module, baseErrorDescription, extraErrorDescription)
        elif (lba + txLen) > self.globalVarsObj.maxLba:
            module = 'SWAPCTD_Library.PerformWrite'
            baseErrorDescription = 'lba value "{}" not in range {}..{}'.format((lba+txLen), 0, self.globalVarsObj.maxLba)
            extraErrorDescription = 'Given Lba was beyond maxLba, so resetting it to 0'
            self.logger.Info(self.globalVarsObj.TAG, baseErrorDescription)
            self.logger.Info(self.globalVarsObj.TAG, extraErrorDescription)
            self.__currentLba = 0
            #raise ValidationError.VtfGeneralError(module, baseErrorDescription, extraErrorDescription)
        else:
            # make note of the write in the dictionary
            self.__dictOfWrites[lba] = txLen
            try:
                # Issue the write command - try catch is present for writes and reads
                self.ccmObj.Write(lba, txLen)
            except:
                raise ValidationError.TestFailError("SWAPCTD_Library.PerformWrite", "write failed to lba %d with txLen %d"%(lba, txLen))
            # increment write command count for this test  
            # TODO Make powercycle occur for both read and write cmds, i.e. maintain both counts per test
            self.__currentTestWriteCount += 1
            # this is to check whether EI is to be used or not
            # TODO Come up with a better solution, than checking after every write
            # short circuit mechanism: skips checking the second condition if the first condition itself is false
            if ((self.__userConfigurations['WritesAndReads']['UseEI']=='No') and (self.__currentTestWriteCount >= int(self.__userConfigurations['WritesAndReads']['NumberOfWriteCommands']))):
                self.isWritesToBeStopped = True
            # although this method is out of place and should not be called here, for now, this is fine
            self.CheckAndIssuePowerCycle()
        #self.CheckAndIssueTempIncrease()
        return 
    
    # @brief   Performs reads for all the lbas and txLen stored in the list
    # @details This is to ensure written data is read back properly 
    # @param   None
    # @return  None    
    def PerformReads(self):
        for startLba, txLen in self.__dictOfWrites.iteritems():
            try:
                self.ccmObj.Read(startLba, txLen)
            except ValidationError.CVFExceptionTypes , exc:
                self.logger.Info(self.globalVarsObj.TAG,  "RLBA: {0} FAILED TLen: {1}".format(hex(startLba), hex(txLen)))
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Read API in EINCTD"+ exc.GetFailureDescription())            
        self.CheckAndIssuePowerCycle()
        self.CheckAndIssueTempIncrease()
        return 
    
    # @brief   this will appropriately switch the mode as required , both before and after the switch
    # @details This searches for particulars of the tests, and calls specific methods accordingly to attain desired functionality
    # @param   mode which mode to init in, whether SD or PCIe; each init will behave differently
    #          default will be set to PCIe
    # @return  None
    def InitInMode(self, mode='PCIe'):
        if mode=='SD':
            self.logger.Info(self.tag, "Init into SD mode")
            if self.globalVarsObj.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe":
                self.isInitToPCIeMode = False
                self.isInitToSDMode   = True
                self.globalVarsObj.vtfContainer.switchProtocol()
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode=True
                # set timeouts
                self.globalVarsObj.vtfContainer._livet.GetRootObject().SetVariable('host.write_timeout', '250ms')
                self.globalVarsObj.vtfContainer._livet.GetRootObject().SetVariable('host.read_timeout', '100ms')        
        elif mode=='PCIe':
            self.logger.Info(self.tag, "Init into PCIe mode")
            if self.globalVarsObj.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe":
                self.isInitToSDMode   = False 
                self.isInitToPCIeMode = True
                #remove them when support for SD->PCIe switch is enabled
                self.globalVarsObj.vtfContainer.switchProtocol()
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode=False    
                #placeholder here for init in PCIe
        return
    
    # @brief   mimics user defined sequential patterns, i.e. chunks of data written in sequeunce
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, sets lba to current position and again chooses a different txLen in a loop
    # @param 
    # @return  None    
    # this is without the EI scenario
    def DoMeasuredSequentialWrite(self, numberOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):                        
        if numberOfWrites is not None:
            # as a first step, we get the transfer len and align lba
            txLen = self.GetTransferLength(txLenThreshold)
            self.SetLba(txLen)            
            for i in range(numberOfWrites):
                # logic same as the one within while loop, just the exit criterias are different
                self.PerformWrite(self.__currentLba, txLen)
                self.__currentLba += txLen
                txLen = self.GetTransferLength(txLenThreshold)           
        elif sectorsToBeWritten is not None:
            # initially we get the txLen 
            txLen = self.GetTransferLength(sectorsToBeWritten, txLenThreshold)
            # we set the lba - for sequential writes we set it only once
            self.SetLba(txLen)
            # then keep looping until they're exhausted
            while sectorsToBeWritten > 0:
                self.PerformWrite(self.__currentLba, txLen)  
                sectorsToBeWritten -= txLen
                txLen = self.GetTransferLength(sectorsToBeWritten, txLenThreshold)
                self.__currentLba += txLen
        else:
            # get the number of writes from the ini file
            # and supply that as a parameter to the same function call
            self.DoMeasuredSequentialWrite(numberOfWrites=int(self.__userConfigurations['WritesAndReads']['NumberOfWriteCommands']))
                        
        return 
    
    def DoConditionalSequentialWrite(self, flag=None):
        if flag == None:
            while not self.isWritesToBeStopped:
                self.PerformWrite(self.__currentLba, txLen)
                self.__currentLba += txLen
                txLen = self.GetTransferLength() 
        else:
            while flag is not True:
                self.PerformWrite(self.__currentLba, txLen)
                self.__currentLba += txLen
                txLen = self.GetTransferLength()                 
        return 
    
    # @brief   mimics user defined sequential patterns, i.e. chunks of data written in sequeunce
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, sets lba to current position and again chooses a different txLen in a loop
    # @param 
    # @return  None    
    def HandleWrites(self, numOfWrites = None, sectorsToBeWritten = None, flag=None, txLenThreshold=None):
        if self.__combinationForCurrentTest["WritePattern"]=="Sequential":
            if flag == None:
                self.DoMeasuredSequentialWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)
            else:
                self.DoConditionalSequentialWrite(flag, txLenThreshold)
        elif self.__combinationForCurrentTest["WritePattern"]=="Random":
            if flag == None:
                self.DoMeasuredRandomWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)
            else:
                self.DoConditionalRandomWrite(flag, txLenThreshold)
        elif self.__combinationForCurrentTest["WritePattern"]=="Overlapped":
            if flag == None:
                self.DoMeasuredOverlappedWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)
            else:
                self.DoConditionalOverlappedWrite(flag, txLenThreshold)
        else:
            if flag == None:
                self.DoMeasuredSequential_RandomWrite(numOfWrites, sectorsToBeWritten, txLenThreshold)         
            else:
                self.DoConditionalSequential_RandomWrite(flag, txLenThreshold)
        return 
    
    # @brief   mimics user defined sequential patterns, i.e. chunks of data written in sequeunce
    # @details 
    # @param   txLen this is to ensure sum of lba and txLen dont exceed maxLba, so range is between min and max - txLen 
    # @return  None   
    def SetLba(self, txLen):
        attributeValue = self.__combinationForCurrentTest["LogicalLBAAlignment"]
        if attributeValue=="AlignedtoDiePage":
            self.__currentLba = self.randomObj.randrange(0, self.__maxLba - txLen, self.__sectorsInADiePage)
        elif attributeValue=="Unalignedto4K":
            lba = self.randomObj.randint(1, self.globalVarsObj.maxLba - txLen) 
            while (lba % self.__sectorsIn4KChunk) == 0:
                lba = self.randomObj.randint(1, self.globalVarsObj.maxLba - txLen)
            self.__currentLba = lba
        elif attributeValue=="Alignedto4K":
            self.__currentLba = self.randomObj.randrange(0, self.__maxLba - txLen, self.__sectorsIn4KChunk)
        return
    
    # @brief   Randomly chooses a transfer length, as required by the test attribute values
    # @details Have to make sure a transfer length within MDTS is chosen 
    #          Using randrange we can choose without having to force align the txLen 
    #          The generated txLen will in multiples of the writeLength value only
    # @param 
    # @return  txLen    
    # randrange() will never choose the higher value, so 1 is added to the rhs values below so as to include them 
    def GetTransferLength(self, sectorsToBeWritten=None, maxTxLen=None):
        attributeValue = self.__combinationForCurrentTest["WriteLength"]
        assert (maxTxLen <= self.globalVarsObj.MDTS), "User Max Transfer Length %d cannot be greater than device MDTS %d"%(maxTxLen, self.globalVarsObj.MDTS) 
        if maxTxLen == None:
            maxTxLen = self.__fwConfigObj.sectorsPerSlcBlock
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
            return -1
        
    # @brief   mimics user defined random patterns, i.e. chunks of data without any order
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, again chooses a different txLen and lba in a loop
    # @param   NumberOfWrites IF we want only specific number of writes to be done in this pattern
    # @return  None      
    def DoMeasuredRandomWrite(self, numberOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):
        if numberOfWrites is not None:
            for i in range(numberOfWrites):
                # logic same as the one within while loop, just the exit criterias are different
                txLen = self.GetTransferLength(maxTxLen=txLenThreshold)
                self.SetLba(txLen)
                self.PerformWrite(self.__currentLba, txLen)
        elif sectorsToBeWritten is not None:
            # add logic here
            while sectorsToBeWritten > 0:
                # keep writing and reducing it to 0
                txLen = self.GetTransferLength(sectorsToBeWritten, maxTxLen=txLenThreshold)
                self.SetLba(txLen)
                self.PerformWrite(self.__currentLba, txLen) 
                sectorsToBeWritten -= txLen
        else:
            # get the number of writes from the ini file
            # and supply that as a parameter to the same function call
            self.DoMeasuredRandomWrite(numberOfWrites=int(self.__userConfigurations['WritesAndReads']['NumberOfWriteCommands']))            
        return
    
    def DoConditionalRandomWrite(self, flag=None):
        # check whether the parameter has been passed at all
        # keep writing until we come out while loop
        if flag == None:
            while not self.isWritesToBeStopped:
                txLen = self.GetTransferLength()
                self.SetLba(txLen)
                self.PerformWrite(self.__currentLba, txLen)
        else:
            while flag is not True:
                txLen = self.GetTransferLength()
                self.SetLba(txLen)
                self.PerformWrite(self.__currentLba, txLen)                
        return 
    
    def GetSectorsToOverlap(self, txLen):
        # how many sectors to increment now?
        lbasToIncrement = 0 # this variable will store how many to increment after each write so as to overlap 
        if self.__combinationForCurrentTest['LogicalLBAAlignment'] == 'Unalignedto4K':
            lbasToIncrement = self.randomObj.randint(0, txLen)
            # to ensure that the lba that we have picked is not aligned to 4k
            while ((self.__currentLba + lbasToIncrement) % self.__sectorsIn4KChunk == 0):
                lbasToIncrement = self.randomObj.randint(0, txLen)
        elif self.__combinationForCurrentTest['LogicalLBAAlignment'] == 'AlignedtoDiePage':
            lbasToIncrement = self.randomObj.randrange(0, txLen, self.__sectorsInADiePage)
        elif self.__combinationForCurrentTest['LogicalLBAAlignment'] == 'Alignedto4K':
            lbasToIncrement = self.randomObj.randrange(0, txLen, self.__sectorsIn4KChunk)
        self.__currentLba += lbasToIncrement       
        return lbasToIncrement
    
    # @brief   mimics user defined overlapped patterns, i.e. chunks of data written with subsequent writes overwriting part of current write
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) After each write, chooses an lba within the txLen(within written data) (making sure lba is aligned as required) and starts next write from there
    # @param 
    # @return  None    
    def DoMeasuredOverlappedWrite(self, numOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):
        if numOfWrites is not None:   
            txLen = self.GetTransferLength(txLenThreshold)
            self.SetLba(txLen)        
            for i in range(numOfWrites):
                self.PerformWrite(self.__currentLba, txLen)
                self.__currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength(txLenThreshold)
        elif sectorsToBeWritten is not None:
            txLen = self.GetTransferLength(sectorsToBeWritten=sectorsToBeWritten, maxTxLen=txLenThreshold)
            self.SetLba(txLen)
            while sectorsToBeWritten > 0:
                self.PerformWrite(self.__currentLba, txLen)
                sectorsToBeWritten -= txLen
                # how many sectors to increment now?
                self.__currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength(sectorsToBeWritten=sectorsToBeWritten, maxTxLen=txLenThreshold)            
        else:
            # default function call  
            # get the number of writes from the ini file
            # and supply that as a parameter to the same function call
            self.DoMeasuredOverlappedWrite(numOfWrites=int(self.__userConfigurations['WritesAndReads']['NumberOfWriteCommands']))        
        return 
    
    def DoConditionalOverlappedWrite(self, flag=None):
        if flag == None:
            while not self.isWritesToBeStopped:
                self.PerformWrite(self.__currentLba, txLen)
                self.__currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength()
        else:
            while flag is not True:
                self.PerformWrite(self.__currentLba, txLen)
                self.__currentLba += self.GetSectorsToOverlap(txLen)
                txLen = self.GetTransferLength()                
        return 
    
    # @brief   mimics user defined sequential_random patterns, i.e. sequential writes for some time and random writes for some time
    # @details 1) Gets the required txLen and lba is set according to the sheet
    #          2) Keeps on writing until asked to stop 
    #          3) Some number of writes in sequential, other in random
    #          4) 
    # @param 
    # @return  None    
    def DoMeasuredSequential_RandomWrite(self, numberOfWrites=None, sectorsToBeWritten=None, txLenThreshold=None):
        # if no ei is to be used then we split the number of writes into two unequal parts and call methods
        if (self.__userConfigurations['WritesAndReads']['UseEI']=='No') or (numberOfWrites is not None) :
            # as it is mentioned in the .ini file that the writes have to be a multiple of 5
            # we divide the number of writes by 5 and alternatively issue 5 writes per write pattern
            writesIssuedPerWritePattern = 5 # HARDCODED value
            numOfWrites = int(self.__userConfigurations['WritesAndReads']['NumberOfWriteCommands'])/writesIssuedPerWritePattern
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
    
    def DoConditionalSequential_RandomWrite(self, flag=None):
        numOfWritesBetweenSwitches = int(self.__userConfigurations['WritesAndReads']['NumOfWritesSeqRanPattern'])
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
    # @details TODO Reads failing now have to fix them
    # @param 
    # @return  None    
    def CheckAndIssuePowerCycle(self):
        #self.vtfContainer.cmd_line_args.powerReset = 'GSD'
        #self.logger.Info(self.tag, "Performing Power Cycle as requested by test i.e. %d number of commands completed since last power cycle "%(puthere))
        
        # If UAS Mode, Wait for Thread completion before Power Cycle
        if(self.globalVarsObj.isUASMode):
            self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762        

        if self.__combinationForCurrentTest['PowerCycle']=='NoPowerCycle':
            pass
        elif self.__combinationForCurrentTest['PowerCycle']=='Frequent_25Commands':
            #if self.__currentTestWriteCount%25==0:
            if self.globalVarsObj.totalIOCommandCount%25==0:
                self.utilsObj.PowerCycle()
                                
        elif self.__combinationForCurrentTest['PowerCycle']=='InFrequent_75Commands':
            #if self.__currentTestWriteCount%75==0:
            if self.globalVarsObj.totalIOCommandCount%75==0:
                self.utilsObj.PowerCycle()
        return
       
    
    #def CheckAndIssueTempIncrease(self, source='Write'):
    ## @brief   This is to ensure powercycle happens every now and then
    ## @details TODO Reads failing now have to fix them
    ## @param 
    ## @return  None
    ##self.sctpUtilsObj.SetThermalParam(asic_temp=set_temp_asic, nand_peak_temp=set_temp_asic)  
    #assert source in ['Read', 'Write', 'PowerCycle'], "Temp change can be made through Write/Read/PowerCycle only"
    #if (source == 'Read' and self.globalVarsObj.readCommandCount%2000 == 0 and self.globalVarsObj.readCommandCount != 0) or\
       #(source == 'Write' and self.globalVarsObj.writeCommandCount%1000 == 0 and self.globalVarsObj.writeCommandCount != 0):
        #fetched_asic_temp, fetched_nand_temp = self.GetCurrentAsicNandTemp()
        #assert fetched_asic_temp == self.current_asic_temp, 'Mismatch in fetched_asic_temp=%d and test maintained asic_temp=%d'%(fetched_asic_temp, self.current_asic_temp)
        #assert fetched_nand_temp == self.current_nand_temp, 'Mismatch in fetched_nand_temp=%d and test maintained nand_temp=%d'%(fetched_nand_temp, self.current_nand_temp)
        #self.current_asic_temp += 1
        #self.current_nand_temp += 1
        ## Handle case where too much increase takes it to shutdown
        ## For reference, in SDExpress, ASIC Shutdown is at 125C and NAND is at 95C
        #if self.current_asic_temp >= 125:
        ## Issue Powercycle to cool down
        #if self.globalVarsObj.vtfContainer.activeProtocol == 'NVMe_OF_SDPCIe':
            #self.ccmObj.GSD()
        #elif self.globalVarsObj.vtfContainer.activeProtocol == 'SD_OF_SDPCIe':
            #self.sdUtilsObj.UGSD()
        #self.ccmObj.Delay(secondsToSleep=100)
        #self.current_asic_temp = 25
        #elif self.current_nand_temp >= 95:
        ## Issue Powercycle to cool down
        #if self.globalVarsObj.vtfContainer.activeProtocol == 'NVMe_OF_SDPCIe':
            #self.ccmObj.GSD()
        #elif self.globalVarsObj.vtfContainer.activeProtocol == 'SD_OF_SDPCIe':
            #self.sdUtilsObj.UGSD()
        #self.ccmObj.Delay(secondsToSleep=100)
        #self.current_nand_temp = 25
        #self.SetThermalParameters(asic_temp_to_set=self.current_asic_temp, nand_temp_to_set=self.current_nand_temp)
    #elif source == 'PowerCycle':
        #fetched_asic_temp, fetched_nand_temp = self.GetCurrentAsicNandTemp()
        #assert fetched_asic_temp == self.current_asic_temp, 'Mismatch in fetched_asic_temp=%d and test maintained asic_temp=%d'%(fetched_asic_temp, self.current_asic_temp)
        #assert fetched_nand_temp == self.current_nand_temp, 'Mismatch in fetched_nand_temp=%d and test maintained nand_temp=%d'%(fetched_nand_temp, self.current_nand_temp)
        #self.current_asic_temp -= 10
        #self.current_nand_temp -= 10
        ## Handle case where too many powercycles will take temparature to below 0
        #if self.current_asic_temp < 0:
        #self.current_asic_temp = 25
        #if self.current_nand_temp < 0:
        #self.current_nand_temp = 25
        #self.SetThermalParameters(asic_temp_to_set=self.current_asic_temp, nand_temp_to_set=self.current_nand_temp)
    #return
    
    #def GetCurrentAsicNandTemp(self):
        #out_list = []
        #readThermal_fw_dict = OrderedDict()
        #out_list, readThermal_fw_dict = self.globalVarsObj.sctpUtilsObj.ReadThermalInfo(readOption=0)        
        #asic_temp = readThermal_fw_dict['asci_temp']
        #nand_temp = readThermal_fw_dict['peak_nand_temp']
        #self.logger.Info(self.globalVarsObj.TAG, "ASIC temp in celcius from FW variable %s" % str(asic_temp))
        #self.logger.Info(self.globalVarsObj.TAG, "NAND temp in celcius from FW variable %s" % str(nand_temp))         
        #return asic_temp, nand_temp

    #def SetThermalParameters(self, asic_temp_to_set, nand_temp_to_set):
    #self.logger.Info(self.globalVarsObj.TAG, "Setting temperature of ASIC to - %d" % (asic_temp_to_set))
    #self.logger.Info(self.globalVarsObj.TAG, "Setting temperature of NAND to - %d" % (nand_temp_to_set))
    ## Set ASIC temp through Livet API - Commented as FW internally sets the value again
    ## self.globalVarsObj.vtfContainer._livet.GetController().SetTemperature(asic_temp_to_set)
    ## Give some delay so that livet updates fw values / vice versa
    ## self.ccmObj.Delay(secondsToSleep=1)  
    ## Set temp in FW through Diag
    #self.sctpUtilsObj.SetThermalParam(asic_temp=asic_temp_to_set, nand_peak_temp=nand_temp_to_set)
    ## Give some delay so that livet updates fw values / vice versa
    #self.ccmObj.Delay(secondsToSleep=1)
    ## Query again
    #asic_temp_new, nand_temp_new = self.GetCurrentAsicNandTemp()
    #assert asic_temp_new == asic_temp_to_set, 'Asic temp = %d not set to %d after diag'%(asic_temp_new, asic_temp_to_set)
    #assert nand_temp_new == nand_temp_to_set, 'NAND temp = %d not set to %d after diag'%(nand_temp_new, nand_temp_to_set)
    #self.current_asic_temp = asic_temp_new
    #self.current_nand_temp = nand_temp_new
    #return
    
    # @brief   
    # @details 
    # @param   None
    # @return  None       
    def ClearTestData(self):
        self.logger.Info(self.tag, "clearing test logs")
        self.__dictOfWrites.clear()
        self.__currentTestWriteCount = 0
        self.isWritesToBeStopped = False
        return

    # Straightaway fail if any of the RS waypoints are hit in SD mode
    def WP_PS_RS_Callback(self, eventKeys, args, processorID):
        assert (self.globalVarsObj.vtfContainer.getActiveProtocol() == 'SD_OF_SDPCIe' and self.isInitToSDMode) is False, 'Waypoint %s hit in SD mode'%(self.wayPointLibObj._WayPointHandler__activeWayPoints[eventKeys])
        return