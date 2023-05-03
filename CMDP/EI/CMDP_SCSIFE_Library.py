##
#***********************************************************************************************
# @file            : CMDP_SCSIFE_Library.py
# @brief           : This is a library meant for SDFE APIs, mostly validating the frontend
# @author          : Adarsh
# @date(ORG)       : 15 Jan 21
# @copyright       : Copyright (C) 2021 SanDisk Corporation
#***********************************************************************************************
# @detail Internal Module Specific libraries here 
import Utils
import ScsiCmdWrapper as scsiwrap
import Core.ValidationError as ValidationError


class CMDP_SCSIFE_Library(object):
    __staticCmdpSdLibObj = None
    __staticCmdpSdLibObjCreated   = False
    def __new__(cls, *args, **kwargs):

        if not CMDP_SCSIFE_Library.__staticCmdpSdLibObj:
            CMDP_SCSIFE_Library.__staticCmdpSdLibObj = super(CMDP_SCSIFE_Library,cls).__new__(cls, *args, **kwargs)

        return CMDP_SCSIFE_Library.__staticCmdpSdLibObj    
    def __init__(self, einLibObj):
        # Check if instance has already been created
        if CMDP_SCSIFE_Library.__staticCmdpSdLibObjCreated:
            return
        CMDP_SCSIFE_Library.__staticCmdpSdLibObjCreated = True
        super(CMDP_SCSIFE_Library, self).__init__()
        # Other APIs
        # Utils & Global Vars
        self.einLibObj     = einLibObj
        self.globalVarsObj = self.einLibObj.globalVarsObj
        self.ccmObj        = self.globalVarsObj.ccmObj
        self.sctpUtilsObj  = self.globalVarsObj.sctpUtilsObj
        self.utilsObj     = Utils.Utils()
        # Livet related variables
        self.livetObj = self.globalVarsObj.vtfContainer._livet
        #self.livetObj.GetController().SetStringVariable( "SD_HIM.protocol", "sdv2" )
        self.CmdGen = self.livetObj.GetCmdGenerator()
        self.LogicHost = self.livetObj.GetLogicalHost()	
        # Flags
        self.inLowVoltageMode = False
        self.currentSpeedMode = None
        return
    
    # @brief   Randomly Selects one SD-FE related operation and triggers the same
    # @details Add more options here for expanding the type of operations supported
    # @param   None
    # @return  None    
    def IssueRandomOperation(self):
        # List out all possible Operations here
        operationList = ['PowerCycle', 'Erase', 'ReadRegister', 'SpeedModeChange', 'LV_Init', 'Delay']
        operationList = ['PowerCycle', 'Delay']
        # Randomly choose between an SDFE Operation
        operation = self.globalVarsObj.randomObj.choice(operationList)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "RANDOM OPERATION : {}".format(operation))        
        if operation == 'PowerCycle':
            self.ccmObj.PowerCycle()
            self.inLowVoltageMode = False
        elif operation == 'Erase':
            self.PerformErase()
        elif operation == 'ReadRegister':
            self.ReadRegister()
        elif operation == 'SpeedModeChange':
            self.CheckAndSwitchSpeedMode()
        elif operation == 'LV_Init':
            self.SdCmdsCls.Initialize_LowVoltage_Sequence()
            self.inLowVoltageMode = True
        elif operation == 'Delay':
            delayTime = self.globalVarsObj.randomObj.randint(10, 10000)
            self.utilsObj.InsertDelay(delayTime)
        return

    # @brief   Randomly Selects one Speed mode to switch to through CMD6
    # @details This includes frequency changes done in Model. Change for hw required
    # @param   None
    # @return  None     
    def CheckAndSwitchSpeedMode(self):
        # Define a list of possible speed modes
        speedModeList = ['SDR12_DEFAULT_SPEED', 'SDR25_HIGH_SPEED', 'SDR50_ULTRA_HIGH_SPEED', 'SDR104_ULTRA_HIGH_SPEED', 'DDR50_HIGH_SPEED']
        # Query the current Speed mode
        cmdObj = self.SdCmdsCls.CMD6(0xF, 0xF, 0xF, 0xF, bMode=False)
        currentSetSpeedValue = cmdObj.statusDataStructure.uiFunctionSelectionOfFunctionGroup1
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Current CMD6 Query/Read mode of set speed is %s" % str(speedModeList[int(currentSetSpeedValue)]))	
        self.currentSpeedMode = cmdObj.statusDataStructure.uiFunctionSelectionOfFunctionGroup1	
        # Randomly select a mode to switch to
        modeToSwitch = self.globalVarsObj.randomObj.choice(speedModeList)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Changing Speed Mode fom %s to %s"%(str(speedModeList[int(self.currentSpeedMode)]), modeToSwitch))
        # Issue CMD11 to switch from 3.3V to 1.8V
        if modeToSwitch in ['SDR50_ULTRA_HIGH_SPEED', 'SDR104_ULTRA_HIGH_SPEED', 'DDR50_HIGH_SPEED']:
            # Check if device is already in 1.8V
            if not self.inLowVoltageMode:
                self.SdCmdsCls.Initialize_LowVoltage_Sequence()
                self.inLowVoltageMode = True
        # Set Mode
        cmdObj = self.SdCmdsCls.CMD6(speedModeList.index(modeToSwitch), 0xF, 0xF, 0xF, bMode=True)
        # Send once agai if it has changed
        cmdObj = self.SdCmdsCls.CMD6(0xF, 0xF, 0xF, 0xF, bMode=False)
        assert cmdObj.statusDataStructure.uiFunctionSelectionOfFunctionGroup1 == speedModeList.index(modeToSwitch), "Queried Speed Mode %s not matching Set Mode %s"\
               %(cmdObj.statusDataStructure.uiFunctionSelectionOfFunctionGroup1, speedModeList.index(modeToSwitch))
        self.currentSpeedMode = modeToSwitch
        # Wait to go back to Tran state
        self.GetSDTranState()	
        return

    # @brief   Randomly Selects one Erase operation type (Erase, Discard, Fule)
    # @details CVF currrently claims tht it calculates timeout independantly, but more needs to be checked
    # @param   None
    # @return  None    
    def PerformErase(self):
        if len(self.einLibObj._listOfWrites) == 0:
            pass
        else:
            # randomly pick some entries
            entriesToErase       = self.globalVarsObj.randomObj.randint(1, (len(self.einLibObj._listOfWrites)-1))
            self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'Sampling %d entries from listOfWrites of size %d'%(entriesToErase, len(self.einLibObj._listOfWrites)))
            # entriesToErase must be at max equal to the length of listOfWrites
            listOfEntriesToErase = self.globalVarsObj.randomObj.sample(self.einLibObj._listOfWrites, entriesToErase)
            for (lba, txLen) in listOfEntriesToErase:
                self.SdCmdsCls.CMD32(lba)
                self.SdCmdsCls.CMD33(lba+txLen)
                # select type of erase
                argument = self.globalVarsObj.randomObj.choice([0,1,2])
                self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'Issuing CMD38 arg=%d with startLba = %d endLba = %d'%(argument, lba, (lba+txLen)))
                self.SdCmdsCls.CMD38(argument)
                # Remove the entry from the list
                self.einLibObj._listOfWrites.remove((lba, txLen))
                self.einLibObj.HistoryObj.HistoryObj.GlobalWriteData.remove((lba, txLen))
            self.einLibObj
        return

    # @brief   Randomly Selects one Register to read
    # @details Some registers can be only read in specific states such as Tran, Stby. Ensure card is in that state before issuing
    # @param   None
    # @return  None
    def ReadRegister(self):
        # List out all possible Registers here
        registerList = ['CSD', 'SD_Status', 'CID', 'SCR', 'DSR', 'OCR', 'Ext_Register', 'CardStatus']
        register     = self.globalVarsObj.randomObj.choice(registerList)
        if register == 'CSD':
            self.ReadCSD()
        elif register == 'CID':
            self.ReadCID()
        elif register == 'SCR':
            self.ReadSCR()
        elif register == 'OCR':
            self.ReadOCR()
        elif register == 'DSR':
            self.ReadDSR()
        elif register == 'Ext_Register':
            self.ReadExtensionRegister()
        elif register == 'CardStatus':
            self.GetSDTranState()
        elif register == 'SD_Status':
            self.ReadSdStatus()
        return

    # @brief   Read Card Specific Data Register
    # @details Needs to be in STBY state
    # @param   None
    # @return  None    
    def ReadCSD(self):
        ################################################################################################################
        ## Step(0): Ensure we are in STBY State
        ################################################################################################################
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_STBY_S_X)
        ################################################################################################################
        ## Step(1): Issue CMD9
        ################################################################################################################        
        cmdObj = self.SdCmdsCls.CMD9()
        self.CSD = cmdObj.pyResponseData.r2Response.CSD        
        ################################################################################################################
        ## Step(2): Ensure we are back to Tran state
        ################################################################################################################        
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_TRAN_S_X)
        return
    
    # @brief   Read Card Identification Data Register
    # @details Needs to be in STBY state
    # @param   None
    # @return  None    
    def ReadCID(self):
        ################################################################################################################
        ## Step(0): Ensure we are in STBY State
        ################################################################################################################
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_STBY_S_X)
        ################################################################################################################
        ## Step(1): Issue CMD10
        ################################################################################################################        
        self.SdCmdsCls.CMD10()
        ################################################################################################################
        ## Step(2): Ensure we are back to Tran state
        ################################################################################################################        
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_TRAN_S_X)
        return

    # @brief   Read SD Status Register
    # @details None
    # @param   None
    # @return  None  
    def ReadSdStatus(self):
        ################################################################################################################
        ## Step(1): Issue ACMD13 to get extended SD status
        ################################################################################################################
        self.SdCmdsCls.ACMD13()
        return

    # @brief   Read Driver State Register
    # @details Not a FW cmd, handled by HIM
    # @param   None
    # @return  None  
    def ReadDSR(self):
        ################################################################################################################
        ## Step(0): Ensure we are in STBY State
        ################################################################################################################
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_STBY_S_X)
        ################################################################################################################
        ## Send CMD4
        ## TODO: Send values other than the default 0x404, and check if the register value is updated
        ################################################################################################################        
        self.SdCmdsCls.CMD4(0x404)
        ################################################################################################################
        ## Step(2): Ensure we are back to Tran state
        ################################################################################################################
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_TRAN_S_X)
        return

    # @brief   
    # @details 
    # @param   None
    # @return  None
    def ReadSCR(self):
        ################################################################################################################
        ## Step(1): Issue ACMD51 to get extended SD status
        ################################################################################################################
        # Issue ACMD51 to receive 64-bit SCR register on data lines
        self.SdCmdsCls.ACMD51()     
        return

    # @brief   Read OCR
    # @details ACMD41 enquiry fetches OCR data, so must follow a soft reset
    # @param   None
    # @return  None      
    def ReadOCR(self):
        ################################################################################################################
        ## Step(1): Issue CMD0 to go to Idle State, and Issue ACMD41 Inquiry
        ################################################################################################################
        self.SdCmdsCls.ACMD41Inquiry()
        ################################################################################################################
        ## Step(2): Init back to Tran state
        ################################################################################################################        
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_TRAN_S_X)
        return

    # @brief   Pools Status Register until we come back to tran state
    # @details Needs to be in STBY state
    # @param   None
    # @return  None      
    def GetSDTranState(self):
        # Keep checking the status of the device until Tran state
        timeout_cnt = 0
        simTime = 5
        while True:
            cmdObj = self.SdCmdsCls.CMD13()
            sd_state = self.SdCmdsCls.GetDeviceState(cmdObj.pyResponseData.r1Response.uiCardStatus)
            if sd_state == sdCmdWrap.STATUS_CODE_CURRENT_STATE_TRAN_S_X:
                break
            else:
                self.ccmObj.Delay(secondsToSleep=0, nanoSecToSleep=simTime*1000000)
                timeout_cnt = timeout_cnt + simTime
                if timeout_cnt > 250:
                    message = "Test polled for the next task > 250 millisec but couldn't get back to Tran State"
                    raise ValidationError.TestFailError(self.ccmObj.vtfContainer.GetTestName(), message)              
            # end_if
        # end_while
        return
    
    def ReadExtensionRegister(self, mio = 0, fno = 2, addr = 0, length = 511):
        cmdObj = self.SdCmdsCls.CMD48(mio = mio, fno = fno, addr = addr, length = length)
        dataBuf = cmdObj.rawBuffer
        return dataBuf
    
    def WriteExtensionRegister(self, mio = 0, fno = 2, mw = 0, addr = 0, length = 511, enableCache = 0, enableCQ = 0, cqMode = 'sequential'):
        # Creating a datatype for the Perf Enhancement Register
        perfEncmnt = sdCmdWrap.EXT_REGISTER_SET_FOR_PERFORMANCE_ENHENCEMENT_FUNCTION()
        # Set the CQ Mode
        assert cqMode in ['sequential', 'voluntary'], "mode can be sequential/voluntary only"
        if cqMode == 'voluntary':
            perfEncmnt.ui8CQMode = 0
        elif cqMode == 'sequential':
            perfEncmnt.ui8CQMode = 1
        # Set the Enable CQ bit
        if enableCQ == 1:
            perfEncmnt.ui8EnableCQ = 1
        # Set the Enable Cache bit
        if enableCache == 1:
            perfEncmnt.ui8CacheEnable = 1
        # Write function extension registers for performance enhancement ( FNO = 2 ),
        un =sdCmdWrap.U()
        un.perfEncmntFunc = perfEncmnt            
        extReg = sdCmdWrap.EXTENSION_REGISTERS()
        extReg.u = un
        # Submit Command
        self.SdCmdsCls.CMD49( mio = mio, fno = fno, mw = mw, addr = addr, length = length, extReg = extReg )
        return    

    def GetCQDepth(self):
        dataBuf = self.ReadExtensionRegister()
        cmdq_byte = dataBuf.GetByte(6)
        if cmdq_byte == 0:
            message = "This device doesn't support Command Queue, this test cannot proceed further!"
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), message)
        if cmdq_byte > 31:
            message = 'Illegal depth of command queue = %d' % cmdq_byte
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), message)
        cmdq_depth = cmdq_byte + 1
        return cmdq_depth
    
    def IssueTuningBlockCommand(self):
        # Check if device is already in 1.8V
        if not self.inLowVoltageMode:
            self.SdCmdsCls.Initialize_LowVoltage_Sequence()
            self.inLowVoltageMode = True
        # Choose anywhere upto 40 times to send this command, as allowed by Spec
        numOfCommands = self.globalVarsObj.randomObj.randint(1,40)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, "Issing %d Tuning Block Commands"%(numOfCommands))
        for _ in range(numOfCommands):
            self.SdCmdsCls.CMD19()
            self.GetSDTranState()
        return
    
    def SetTemporaryWriteProtect(self):
        ################################################################################################################
        ## Step(0): Ensure we are in STBY State
        ################################################################################################################
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_STBY_S_X)
        ################################################################################################################
        ## Step(1): Issue CMD9 to get the CSD Data
        ################################################################################################################
        respBlock = self.LivetCommand(index=9, argument=int( self.SdCmdsCls.RCA << 16 ))
        dataBuf = self.livetObj.GetDataBlock(512)
        for i in range(0,15):
            byte = respBlock.GetByte(i+1)
            dataBuf.SetByte(i, byte)	
        ################################################################################################################
        ## bits 12:12: Temporary Write Protect (TEMP_WRITE_PROTECT)
        ################################################################################################################
        byte14 = dataBuf.GetByte(14)
        temp_write_protect = (byte14 & (1<<4) == (1<<4))
        message = 'CSD bit 12: Temporary Write Protect (TEMP_WRITE_PROTECT): %d'%(temp_write_protect)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, message )        
        ################################################################################################################
        ## Step(3): Set bit12 (TMP_WRITE_PROTECT) of the CSD data, before sending the same in CMD27 to program CSD data
        ################################################################################################################
        sdCmdWrap.SelectDeselectCard(self.SdCmdsCls.RCA)
        byte14 = byte14 | (1<<4)
        dataBuf.SetByte(14,byte14)
        self.LivetCommand(index=27, argument=0)
        self.transfer_host_to_device(numOfBlocks=1, livetDataBuf=dataBuf)
        ################################################################################################################
        ## Step(4): Send CSD and confirm if the bit is set
        ################################################################################################################
        sdCmdWrap.SelectDeselectCard(0x0)
        cmdObj = self.SdCmdsCls.CMD9()
        self.CSD = cmdObj.pyResponseData.r2Response.CSD 
        temp_write_protect = None
        if self.CSD[14] & (1<<4) != (1<<4):
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'CSD not reflecting TWP bit set')
        ################################################################################################################
        ## Step(4): Get back to Tran state
        ################################################################################################################        
        sdCmdWrap.SelectDeselectCard(self.SdCmdsCls.RCA)
        return

    def SetPermanentWriteProtect(self):
        ################################################################################################################
        ## Step(0): Ensure we are in STBY State
        ################################################################################################################
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_STBY_S_X)	
        ################################################################################################################
        ## Step(1): Issue CMD9 to get the CSD Data
        ################################################################################################################
        respBlock = self.LivetCommand(index=9, argument=int( self.SdCmdsCls.RCA << 16 ))
        dataBuf = self.livetObj.GetDataBlock(512)
        for i in range(0,15):
            byte = respBlock.GetByte(i+1)
            dataBuf.SetByte(i, byte)	
        ################################################################################################################
        ## Step(2): bit 12: Permanent Write Protect (PERM_WRITE_PROTECT)
        ################################################################################################################
        byte14 = dataBuf.GetByte(14)
        temp_write_protect = (byte14 & (1<<5) == (1<<5))
        message = 'CSD bit 12: Permanent Write Protect (PERM_WRITE_PROTECT): %d'%(temp_write_protect)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, message )        
        ################################################################################################################
        ## Step(3): Set bit12 (PERM_WRITE_PROTECT) of the CSD data, before sending the same in CMD27 to program CSD data
        ################################################################################################################
        # Changing to Tran state
        self.SdCmdsCls.CMD7()
        byte14 = byte14 | (1<<5)
        dataBuf.SetByte(14,byte14)
        self.LivetCommand(index=27, argument=0)
        self.transfer_host_to_device(numOfBlocks=1, livetDataBuf=dataBuf)
        ################################################################################################################
        ## Step(4): Send CSD and confirm if the bit is set
        ################################################################################################################
        # Changing to Stby state
        self.SdCmdsCls.CMD7(uiRCA=0x0)
        # Send CSD
        cmdObj = self.SdCmdsCls.CMD9()
        self.CSD = cmdObj.pyResponseData.r2Response.CSD 
        temp_write_protect = None
        if self.CSD[14] & (1<<5) != (1<<5):
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'CSD not reflecting PWP bit set')
        ################################################################################################################
        ## Step(5): Get back to Tran state
        ################################################################################################################        
        sdCmdWrap.SelectDeselectCard(self.SdCmdsCls.RCA)        
        return

    def ClearTemporaryWriteProtect(self):
        ################################################################################################################
        ## Step(0): Ensure we are in STBY State
        ################################################################################################################
        self.SdCmdsCls.InitToState(target_state=sdCmdWrap.STATUS_CODE_CURRENT_STATE_STBY_S_X)
        ################################################################################################################
        ## Step(1): Issue CMD9 to get the CSD Data
        ################################################################################################################
        respBlock = self.LivetCommand(index=9, argument=int( self.SdCmdsCls.RCA << 16 ))
        dataBuf = self.livetObj.GetDataBlock(512)
        for i in range(0,15):
            byte = respBlock.GetByte(i+1)
            dataBuf.SetByte(i, byte)	
        ################################################################################################################
        ## bits 12:12: Temporary Write Protect (TEMP_WRITE_PROTECT)
        ################################################################################################################
        byte14 = dataBuf.GetByte(14)
        temp_write_protect = (byte14 & (1<<4) == (1<<4))
        message = 'CSD bit 12: Temporary Write Protect (TEMP_WRITE_PROTECT): %d'%(temp_write_protect)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, message )        
        ################################################################################################################
        ## Step(3): Clear bit12 (TMP_WRITE_PROTECT) of the CSD data, before sending the same in CMD27 to program CSD data
        ################################################################################################################
        sdCmdWrap.SelectDeselectCard(self.SdCmdsCls.RCA)
        byte14 = byte14 | ~(1<<4)
        dataBuf.SetByte(14,byte14)
        self.LivetCommand(index=27, argument=0)
        self.transfer_host_to_device(numOfBlocks=1, livetDataBuf=dataBuf)
        ################################################################################################################
        ## Step(4): Send CSD and confirm if the bit is set
        ################################################################################################################
        sdCmdWrap.SelectDeselectCard(0x0)
        cmdObj = self.SdCmdsCls.CMD9()
        self.CSD = cmdObj.pyResponseData.r2Response.CSD 
        temp_write_protect = None
        if self.CSD[14] & (1<<4) == 0:
            raise ValidationError.TestFailError(self.vtfContainer.GetTestName(), 'CSD not reflecting TWP bit clear')
        ################################################################################################################
        ## Step(4): Get back to Tran state
        ################################################################################################################        
        sdCmdWrap.SelectDeselectCard(self.SdCmdsCls.RCA)
        return
    
    def LivetCommand(self, index, argument):
        """
            Description:
                This method creates and issues a protocol command
            Arguments:
                index = command index
                arguments = arguments for that command
            Returns:
                """
        self.last_resp = None
        try:
            # Create command and response data blocks
            cmdblk  = self.livetObj.GetDataBlock( 6 )
            respblk = self.livetObj.GetDataBlock( 17 )
        except Exception, exc:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), testFailueDescription='Error in Creating Livet Datablocks')
        else:
            pass
        # end_try-except-else
        try:
            # Set up command block using index and argument
            opcode = int( ( index & 0x3F ) | 0x40 )
            cmdblk.SetByte( 0, opcode )
            arg = self.SwapDword( argument )
            cmdblk.SetDword( 1, arg )
        except Exception, exc:
            raise exc
        else:
            pass
        # end_try-except-else
        message = "CMD%d: arg = 0x%08X" % ( index, argument )
        # end_if
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, message)
        try:
            # Issue the command to Livet Model and check response
            return_response_blk = False
            self.CmdGen.ProtocolCommand( cmdblk, respblk )
            # Wait until it transitions state
            self.LogicHost.WaitReady()
            status = self.LogicHost.GetLastStatus()
            if status == 0:
                return_response_blk = True
            # end_if
        except Exception, exc:
            raise ValidationError.TestFailError('ROMode_Lib', 'Exception while sending LivetCommand')
        else:
            if return_response_blk:
                return respblk
            else:
                return None
            # end_if
        # end_try-exception-else
        return
        # end of LivetCommand method of LockUnlock_LivetAPI_Lib class
    
    def transfer_host_to_device( self, numOfBlocks, livetDataBuf = None ):
        bytes_to_xfer = ( numOfBlocks * 512 )
        if livetDataBuf == None:
            livetDataBuf = self.livetObj.GetDataBlock( bytes_to_xfer )
        # end_if
        self.LogicHost.WriteData( numOfBlocks, 512, bytes_to_xfer, livetDataBuf )
        self.LogicHost.WaitIdle()
        # Check how to check the timetaken for WaitIdle function
        #self.LogicHost.WaitIdleTimeout()
        return
    # end of method
    
    def SwapDword( self, dword ):
        """ This function swaps bytes of a 32-bit word """
        byte0 = int( dword & 0x000000FF )
        byte1 = int( ( dword & 0x0000FF00 ) >> 8 )
        byte2 = int( ( dword & 0x00FF0000 ) >> 16 )
        byte3 = int( ( dword & 0xFF000000 ) >> 24 )
        retdword = int( ( byte0 << 24 ) | ( byte1 << 16 ) | ( byte2 << 8 ) | byte3 )
        return retdword
    # end of SwapDword    