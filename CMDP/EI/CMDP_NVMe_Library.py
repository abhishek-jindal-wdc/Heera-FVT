##
#***********************************************************************************************
# @file            : CMDP_NVMe_Library.py
# @brief           : This is a library meant for NVMe APIs, mostly validating the frontend
# @author          : Adarsh
# @date(ORG)       : 15 Jan 21
# @copyright       : Copyright (C) 2021 SanDisk Corporation
#***********************************************************************************************
import Core.ValidationError as ValidationError
import Extensions.CVFImports as pyWrap
import Constants

# Sanitize log class 
class Sanitize(object):
    def __init__(self):
        self.SPROG = 0
        self.SSTAT = 0 
        self.SCDW10 = 0
        self.GlobalDataErased = 0
        self.NumberOfCompletedPasses = 0 #relevant for OV only! else =0
        self.lastSanitizeStatus = 0
        self.EstimatedTimeForOverwrite = 0
        self.EstimatedTimeForBlockErase = 0
        self.EstimatedTimeForCryptoErase = 0

class DST(object):
    def __init__(self):
        self.currentDeviceOperation = 0
        # test status :noSelfTestInProgress =  0,shortSelfTestInProgress = 1,extendedSelfTestInProgress = 2
        self.testStatus = 0 
        self.currentDeviceCompletion = 0
        self.resultDataStructureList = []

class DstResultDataStructure(object):
    def __init__(self):
        self.result = 0
        self.invokedTestType = 0
        self.selfTestStatus = 0 
        self.segmentNumber = 0
        self.validDiagnosticInformation = 0 
        self.powerOnHours = 0
        self.namespaceIdentifier = 0
        self.failingLBA = 0
        self.statusCodeType = 0
        self.statusCode = 0
        self.SC_ValidBit = 0
        self.SCT_ValidBiit = 0
        self.FLBA_ValidBit = 0
        self.NSID_ValidBit = 0

class CMDP_NVMe_Library(object):
    __staticCmdpNvmeLibObj = None
    __staticCmdpNvmeLibObjCreated   = False
    def __new__(cls, *args, **kwargs):

        if not CMDP_NVMe_Library.__staticCmdpNvmeLibObj:
            CMDP_NVMe_Library.__staticCmdpNvmeLibObj = super(CMDP_NVMe_Library,cls).__new__(cls, *args, **kwargs)

        return CMDP_NVMe_Library.__staticCmdpNvmeLibObj    
    def __init__(self, einLibObj):
        # Check if instance has already been created
        if CMDP_NVMe_Library.__staticCmdpNvmeLibObjCreated:
            return
        CMDP_NVMe_Library.__staticCmdpNvmeLibObjCreated = True
        super(CMDP_NVMe_Library, self).__init__()
        # Other APIs
        # Utils & Global Vars
        self.einLibObj    = einLibObj
        self.globalVarsObj = self.einLibObj.globalVarsObj
        self.ccmObj        = self.globalVarsObj.ccmObj
        self.sctpUtilsObj  = self.globalVarsObj.sctpUtilsObj
        return
    
    # @brief   Randomly Selects one NVMe-FE related operation and triggers the same
    # @details Add more options here for expanding the type of operations supported
    # @param   None
    # @return  None    
    def IssueRandomOperation(self):
        # List out all possible Operations here
        operationList = ['GSD', 'Format', 'Deallocate', 'Telemetry', 'Sanitize', 'Reset', 'Identify', 'PowerStateChange']
        # Randomly choose between an SDFE Operation
        operation = self.globalVarsObj.randomObj.choice(operationList)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "RANDOM OPERATION : {}".format(operation))
        if operation == 'ReadRegister':
            self.ReadRegister()
        elif operation == 'GSD':
            self.ccmObj.GSD()
        elif operation == 'Format':
            # TODO: Check if SDEx supports SES=0 or SES=2, after which we can choose between those as weel
            self.ccmObj.Format(SES=1)
            # Clear all test data
            self.einLibObj.ClearTestData()
        elif operation == 'Deallocate':
            # This is Namespace Management Command
            self.IssueTrimCommand()
        elif operation == 'DST':
            #check Identify Controller Data Structure parameters set correctly************
            IdentifyControllerObj      = self.ccmObj.IdentifyController()
            supportDST                 = IdentifyControllerObj.objOutputData.OACS.SupportDST
            extendedDeviceSelftestTime = IdentifyControllerObj.objOutputData.EDSTT
            deviceSelftestOptions      = IdentifyControllerObj.objOutputData.DSTO
            if (supportDST == 0 or extendedDeviceSelftestTime == 0 ):
                raise ValidationError.TestFailError(self.variationName, " Identify Controller Data Structure is not set correctly supportDST=%d, extendedDeviceSelftestTime=%d, deviceSelftestOptions=%d"
                                                    %(supportDST, extendedDeviceSelftestTime, deviceSelftestOptions))
            # Currently, this only triggers and does not include any error cases
            dstType = self.globalVarsObj.randomObj.choice(['short', 'extended'])
            if dstType == 'short':
                selfTest = pyWrap.DST(0, 0x1, 20000, pyWrap.SEND_NONE)
            else:
                selfTest = pyWrap.DST(1, 0x1, 20000, pyWrap.SEND_NONE)
            try :
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(selfTest)
            except ValidationError.CVFExceptionTypes:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in RunDst "+ self.globalVarsObj.FVTExcPrint())
            except Exception:
                raise ValidationError.TestFailError("In RunDst",self.globalVarsObj.FVTExcPrint())
            dstBuffer = self.ccmObj.GetLogPageNVMe(Constants.DST_LOG_PAGE_ID)
            dstObj = self.ParseDSTBuffer(dstBuffer)
            while dstObj.testStatus:
                self.ccmObj.Delay(5)
            self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "DST is completed")
        elif operation == 'Telemetry':
            # Currently, only Host Initiated Log is present
            dataUnitsReadEnd = self.ccmObj.GetHostInitiatedLogPage(pageID         = 0x7,
                                                                   numDL          = 511,
                                                                   pageOffset     = 0,
                                                                   isSecurityTest = 1)
            self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "numdword={0}, pageoffset={1}".format(511, 0))
        elif operation == 'Sanitize':
            self.ccmObj.Sanitize()
            # After issuing Sanitize, it is necessary to monitor status for successful completion
            respObj = self.GetSanitizeLogObj()
            self.saniConstObj = Constants.SANITIZE_CONSTANTS()
            # Add delay and query log for completion status
            while respObj.lastSanitizeStatus != self.saniConstObj.LastSanitizeCompletedSuccessfully:
                self.ccmObj.Delay(secondsToSleep=0, nanoSecToSleep=1000000)
                respObj = self.GetSanitizeLogObj()
            # Since Sanitize is done, perform Production again
            
            #commenting Production as it isnt required post production and is also causing bad block erase 
            #SANGAM-3316
            #self.globalVarsObj.vtfContainer.DoProduction(security_production=False)
            
            # Issue GSD
            self.ccmObj.GSD()
            # Clear all test data
            self.einLibObj.ClearTestData()
        elif operation == 'Reset':
            # This supports only NVMe Resets, since PCIe Resets are not supported in Model
            self.IssueNVMeReset()
        elif operation == 'Identify':
            # Add more Register related options here
            self.ccmObj.IdentifyController()
            # Uncomment later after fix, as this is giving error when issued
            #self.ccmObj.IdentifyNamespaces()
        elif operation == 'PowerStateChange':
            # Currently only perform DPS1/2 transition since DPS3/4 blocked by SANGAM-2962
            # Get current power state
            currentState = self.ccmObj.GetFeaturePWRM()	
            self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Get Feature issued: Current State: PS{0}".format(currentState))
            if currentState in [3,4]:
                # Need to send an admin command to bring it back to operational state
                self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Set Feature issued: PS4")
                self.ccmObj.SetFeaturesPwrMgmt(powerState=0)
            #Perform PS1/2 Transition to trigger PS1/2 Optimization due to shutdown
            choice = self.globalVarsObj.randomObj.choice(['DPS1', 'DPS2'])
            self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'Sending PowerSwitch to: %s'%(choice))
            if choice == 'DPS1':             
                self.ccmObj.SetFeaturesPwrMgmt(powerState=2)
            else:
                self.ccmObj.SetFeaturesPwrMgmt(powerState=3)            
        return
    
    def ReadRegister(self):
        registerList = ['CAP', 'VS', 'INTMS', 'INTMC', 'CC', 'CSTS', 'NSSR', 'AQA', 'ASQ', 'ACQ', 'CMBLOC', 'CMBSZ']
        register     = self.globalVarsObj.randomObj.choice(registerList)
        if register == 'CAP':
            self.ccmObj.ControllerCapability()
        elif register == 'VS':
            try:
                readVersionControllerObj = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.VS)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(readVersionControllerObj, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.vtfContainer.GetTestName(), "Error in Version ReadRegister CMDP: "+ exc.GetFailureDescription())
        elif register == 'INTMS':
            try:
                readInterruptMaskSetObj = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.INTMS)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(readInterruptMaskSetObj, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in INTMS ReadRegister CMDP: "+ exc.GetFailureDescription())        
        elif register == 'INTMC':
            try:
                readInterruptMaskClearObj = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.INTMC)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(readInterruptMaskClearObj, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in INTMC ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'CC':
            self.ccmObj.ControllerConfiguration()
        elif register == 'CSTS':
            self.ccmObj.ControllerStatus()
        elif register == 'NSSR':
            self.ccmObj.NvmeSubsystemResetControl()
        elif register == 'AQA':
            try:
                readAdminQueueAttributesObj = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.AQA)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(readAdminQueueAttributesObj, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in AQA ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'ASQ':
            try:
                readAdminSubmissionQueueBaseAddressObj = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.ASQ)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(readAdminSubmissionQueueBaseAddressObj, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in ASQ ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'ACQ':
            try:
                readAdminCompletionQueueBaseAddressObj = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.ACQ)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(readAdminCompletionQueueBaseAddressObj, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in ACQ ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'CMBLOC':
            try:
                controllerMemBuffLocation = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.CMBLOC)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(controllerMemBuffLocation, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in CMBLOC ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'CMBSZ':
            try:
                controllerMemBuffSize = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.CMBSZ)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(controllerMemBuffSize, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in CMBSZ ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'BPINFO':
            try:
                bootPartitionInformation = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.BPINFO)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(bootPartitionInformation, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in BPINFO ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'BPRSEL':
            try:
                bootPartitionReadSelect = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.BPRSEL)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(bootPartitionReadSelect, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in BPRSEL ReadRegister CMDP: "+ exc.GetFailureDescription())                
        elif register == 'BPMBL':
            try:
                bootPartitionMemBuffLocation = pyWrap.GetNVMeConfigReg(pyWrap.ControllerReg.BPMBL)
                self.globalVarsObj.vtfContainer.cmd_mgr.PostRequestToWorkerThread(bootPartitionMemBuffLocation, True)
            except:
                raise ValidationError.CVFGenericExceptions (self.globalVarsObj.vtfContainer.GetTestName(), "Error in BPRSEL ReadRegister CMDP: "+ exc.GetFailureDescription())
        return

    # @brief   Parse the DST Buffer details 
    # @details Call this after Sanitize Command is sent
    # @param   None
    # @return  SanitizeLogObject 
    def ParseDSTBuffer(self, dstBuffer):
        offset = 0
        dstObj = DST()
        dstObj.currentDeviceOperation = dstBuffer.GetOneByteToInt(0) 
        dstObj.currentDeviceCompletion = (dstBuffer.GetOneByteToInt(1) & 0x7F)
        #test status
        dstObj.testStatus = (dstObj.currentDeviceOperation & 0xF)                

        structureList = []
        for _ in range(20):
            newStructure = pyWrap.Buffer.CreateBuffer(28)
            structureList.append(newStructure)

        offset = 4
        for structIndex in range(20):
            structureList[structIndex].Copy(0, dstBuffer, offset, 28)
            offset +=28

        for structIndex in range(20):
            resultDataStructureObj = DstResultDataStructure() 
            resultDataStructureObj.selfTestStatus             = structureList[structIndex].GetOneByteToInt(0)
            resultDataStructureObj.result                     = resultDataStructureObj.selfTestStatus & 0xf
            resultDataStructureObj.invokedTestType            = resultDataStructureObj.selfTestStatus>>4 & 0xf 
            resultDataStructureObj.segmentNumber              = structureList[structIndex].GetOneByteToInt(1)
            resultDataStructureObj.validDiagnosticInformation = structureList[structIndex].GetOneByteToInt(2)
            resultDataStructureObj.powerOnHours               = structureList[structIndex].GetEightBytesToInt(4)
            resultDataStructureObj.namespaceIdentifier        = structureList[structIndex].GetFourBytesToInt(12)
            resultDataStructureObj.failingLBA                 = structureList[structIndex].GetEightBytesToInt(16)
            resultDataStructureObj.statusCodeType             = structureList[structIndex].GetOneByteToInt(24)
            resultDataStructureObj.statusCode                 = structureList[structIndex].GetOneByteToInt(25)
            resultDataStructureObj.NSID_ValidBit              = resultDataStructureObj.validDiagnosticInformation    & 0x1
            resultDataStructureObj.FLBA_ValidBit              = resultDataStructureObj.validDiagnosticInformation>>1 & 0x1
            resultDataStructureObj.SCT_ValidBiit              = resultDataStructureObj.validDiagnosticInformation>>2 & 0x1
            resultDataStructureObj.SC_ValidBit                = resultDataStructureObj.validDiagnosticInformation>>3 & 0x1
            dstObj.resultDataStructureList.append(resultDataStructureObj)
        return dstObj

    # @brief   Queries the Log Page for Sanitize details
    # @details Call this after Sanitize Command is sent
    # @param   None
    # @return  SanitizeLogObject    
    def GetSanitizeLogObj(self):
        logPageBuffer = self.ccmObj.GetLogPageNVMe(Constants.SANITIZE_STATUS_LOG_PAGE_ID)
        #parse buffer
        offset = 0
        sanitizeLogObj = Sanitize()
        sanitizeLogObj.SPROG  = logPageBuffer.GetTwoBytesToInt(0)
        sanitizeLogObj.SSTAT  = logPageBuffer.GetTwoBytesToInt(2)
        sanitizeLogObj.SCDW10 = logPageBuffer.GetFourBytesToInt(4)
        sanitizeLogObj.EstimatedTimeForOverwrite   = logPageBuffer.GetFourBytesToInt(8)
        sanitizeLogObj.EstimatedTimeForBlockErase  = logPageBuffer.GetFourBytesToInt(12)
        sanitizeLogObj.EstimatedTimeForCryptoErase = logPageBuffer.GetFourBytesToInt(16)
        sanitizeLogObj.lastSanitizeStatus      = sanitizeLogObj.SSTAT & 0x3
        sanitizeLogObj.NumberOfCompletedPasses = (sanitizeLogObj.SSTAT >> 0x3) & 0X1F #relevant only for OV, else = 0.
        sanitizeLogObj.GlobalDataErased        = (sanitizeLogObj.SSTAT & 0x3 >> 8) & 0x1
        return sanitizeLogObj    
    
    # @brief   Randomly Selects between type of NVMe Reset, along with the state of the Admin/IO Queue
    # @details Add more options here for expanding the type of operations supported
    # @param   None
    # @return  None    
    def IssueNVMeReset(self):
        assert self.globalVarsObj.vtfContainer.getActiveProtocol() == 'NVMe_OF_SDPCIe', 'NVMe Reset Attempted when not in NVMe mode'
        stateType = self.globalVarsObj.randomObj.choice(['AdminAndIOCmds', 'IdleState'])
        resetType = self.globalVarsObj.randomObj.choice(['ControllerReset', 'SubSystemReset']) 
        if stateType == 'AdminAndIOCmds':
            # Adding IO commands in queue
            for _ in range(20):
                # Add some IOs to the queue
                startLba = self.globalVarsObj.randomObj.randint(0, 100)
                txLen = self.globalVarsObj.randomObj.randint(1, 0x400)
                self.ccmObj.Write(startLba, txLen)
        if resetType == 'ControllerReset':
        # Controller Reset
            # Check if the Controller Status supports this and is ready
            if (self.ccmObj.ControllerConfiguration().EN != 1 or self.ccmObj.ControllerStatus().RDY != 1):
                raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), "Device or host is not in a ready state")
            else:
                self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Host and controller are in ready state as Controller Confguration Enable value is: %d and Controller Status Ready register value is: %d"%(self.ccmObj.ControllerConfiguration().EN,self.ccmObj.ControllerStatus().RDY))
            #Send command to do controller reset, wait for 5 seconds and verify the CC.EN and CSTS.RDY registers            
            self.ccmObj.NvmeControllerReset()
            self.ccmObj.Delay(secondsToSleep=5)
            self.ccmObj.NVMeControllerActivate(bytDisableDone=True)
            if(self.ccmObj.ControllerConfiguration().EN == 1 and self.ccmObj.ControllerStatus().RDY == 1):
                self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "The controller enable field is:%d  and status ready register's value is: %d"%(self.ccmObj.ControllerConfiguration().EN, self.ccmObj.ControllerStatus().RDY))
            else:
                raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), "Controller Status register reporting incorrect value when the drive is in reset state")
        else:
        # SubSystem Reset
            # three registers:
            # NSSRS - NVMe subsystem reset support
            # NSSRO - NVMe subsystem reset occured
            # NSSRC - NVMe subsystem reset control
            #1| Check the CAP.NSSRS(NVMe subsystem reset support) is supported or not
            if (self.ccmObj.ControllerCapability().NSSRS != 1):
                raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), "NVMe Subsystem Reset not supported in controller capability")
            else:
                self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "NVMe Subsystem Reset is supported in the controller capability register")            
                self.ccmObj.NvmeSubsystemReset(NvmssReset = True, DisableCtlr = True, ShutDownCtlr = True, DeleteQueues = True)
                self.ccmObj.Delay(secondsToSleep=5)
                self.ccmObj.NVMeControllerActivate(bytNvmSubsystemResetDone=True)
                self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762
                if (self.ccmObj.NvmeSubsystemResetControl().NSSRC == 0):
                    self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Correct value for NVMe subsystem reset control value returned")
                else:
                    ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), "NVMe subsystem reset control is a write only register and read should always return zero but instead returned: %d"%self.ccmObj.NvmeSubsystemReset().NSSRC)
        return
    
    # @brief   Issues Deallocate command of LBA ranges
    # @details Add more options here for expanding the type of operations supported
    # @param   None
    # @return  None    
    def IssueTrimCommand(self):
        if len(self.einLibObj._listOfWrites) == 0:
            pass
        else:        
            lbaRangeList = list()
            # randomly pick some entries
            # Max 256 entries can be deallocated in one command
            # What if the list of Writes is lesser than that? then dont deallocate at all
            entriesToErase = min(256, len(self.einLibObj._listOfWrites))
            self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'Sampling %d entries from listOfWrites of size %d'%(entriesToErase, len(self.einLibObj._listOfWrites)))
            # entriesToErase must be at max equal to the length of listOfWrites
            listOfEntriesToErase = self.globalVarsObj.randomObj.sample(self.einLibObj._listOfWrites, entriesToErase)
            for (lba, txLen) in listOfEntriesToErase:        
                lbaRange = pyWrap.LbaRange(lba, txLen)
                lbaRangeList.append(lbaRange)
                # Remove the entry from the list
                self.einLibObj._listOfWrites.remove((lba, txLen))
                self.einLibObj.HistoryObj.HistoryObj.GlobalWriteData.remove((lba, txLen))                
            self.ccmObj.DeAllcoate(lbaRangeList)
        return