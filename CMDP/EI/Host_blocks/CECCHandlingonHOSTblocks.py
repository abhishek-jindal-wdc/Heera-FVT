import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
#import EIMediator
import SctpUtils
import WaypointReg
import SDUtils
import Extensions.CVFImports as pyWrap
import random
import CMDP_History as History
import EINCTD_Library
import UECCHandlingonHOSTblocks as UECCHandle

    
class CECChandler:
    
    __staticUECCObj = None

    ##
    # @brief A method to create a singleton object of LOG WA HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not CECChandler.__staticUECCObj:
            CECChandler.__staticUECCObj = super(CECChandler,cls).__new__(cls, *args, **kwargs)

        return CECChandler.__staticUECCObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
	self.__livetFlash = self.livetObj.GetFlash()
        self.__livetFlash.TraceOn("data_write")
	self.__livetFlash.TraceOn("data_read")
        self.__livetFlash.TraceOn('error_injected')
        self.__livetFlash.TraceOn('error_occurred') 	
        self.sctpUtilsObj = SctpUtils.SctpUtils()
        #self.eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
                
        self.ccmObj = self.globalVarsObj.ccmObj                
        self.HistoryObj = History.EpicCallbacks()
        self.startLba = self.HistoryObj.HistoryObj.LastWrittenLBA
        self.endLba = self.globalVarsObj.endLba
	self.einLibObj = EINCTD_Library.EINCTD_Library(self.vtfContainer)
	self.HdrUeccDetected=False
	self.DcdFailed=False
	self.UECCBlockList = list()
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj, self.logger, self.globalVarsObj)
            self.wayPointDict = {
                "UECC_DETECTED"              : [self.OnUECCDetected],
                #"UM_BLOCK_ALLOCATION"        : [],
                "UM_READ"                    : [],
                "UM_WRITE"                   : [],
                "EPWR_START"                 : [self.OnEPWRStart],
                "EPWR_COMPLETE"              : [],
	        #"EPWR_PHY_ADDRESS"           : [],
	        #"SLC_COMPACTION_DATA_TRANSFER_BEGIN" : [],
	        #"MLC_COMPACTION_DATA_TRANSFER_BEGIN" : [],
	        "LDPC_HDR_UECC"              : [self.OnHDRUECCDetected],
                #"GCC_SRC_SELECT"             : [],
				#"LDPC_DECODE_SUCCESS"        : [],
                #"GCC_GOING_TO_WRITE"         : [],
	        #"GCC_GOING_TO_READ"         : []
                }
                
            self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.ResetVariables()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)        
        
    def ErrorHandlerFunction(self,errorGroup, errorCode) :
        self.logger.Info(self.globalVarsObj.TAG, "\n!!!Callback received. Received error group : {0} error code : {1} " .format(errorGroup,errorCode))
        self.ReadError = True
        
        if(errorGroup==65291 and errorCode==11):
            self.errorManager.ClearAllErrors()  
        
        if(errorGroup==65338 and errorCode==524288):
            self.errorManager.ClearAllErrors()  
        
        if(errorGroup==65338 and errorCode==2097152):
            self.errorManager.ClearAllErrors()     
        
        if(errorGroup==2 and errorCode==129):
            self.errorManager.ClearAllErrors() 
            
        if(errorGroup==2 and errorCode==0):
            self.errorManager.ClearAllErrors()        
    
    #def WP_FTL_RLC_SOURCE_BLOCK_SELECTED(self,eventKey,args, pid):
        #if(self.ReferenceSLCJB == args[1]):
            #self.IsRequiredBlockSelectedForRelocation = True
        
            
    #def WP_FTL_RLC_WRITE_JB_VBA(self,eventKey,args, pid):
        #if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
            #self.TLCvbaWritten.append(args[1])       
            #self.TLCjbWritten.append(args[0])
    
    def OnUECCDetected(self,args):
	#self.UECCBlock = args['Block']
        self.UECCdetected = True  
	self.UECCBlockList = [args['block'], args['wordline']]
	
    def OnHDRUECCDetected(self,args):
        if args['Decode_Status']&0x10:
	    self.HdrUeccDetected=True
	elif args['Decode_Status']&0x8:
	    self.DcdFailed=True		
		    
    def clearErrsExcptns(self):
	#Upon expected exceptions, clearing the errors and exceptions to continue test execution
	self.__livetFlash.ClearErrors(True)
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()  	
        
    def ResetVariables(self):
        global WriteAbortDetected
        WriteAbortDetected = False
        self.ReadError = False
        self.JBBeforeWAHandling = False
        self.JBAfterWAHandling = False
        self.BlockWhichWasAddedToPartialBlock = None
        self.BlockAddedToPartialList = False
        self.writtendata = []
        self.IsRequiredBlockSelectedForRelocation = False
        self.SLCvbaWritten = []
        self.SLCjbWritten = []
        self.TLCvbaWritten = []
        self.TLCjbWritten = []   
        self.UECCdetected= False
        self.XORrecoveryDetails = []
        self.errorManager.DeRegisterCallback()            
        self.ReferenceSLCJB = None
        
    def HostWrites(self, startLba):
        txLen = random.choice([256, 512, 1024])
        self.ccmObj.Write(startLba, txLen)
        self.HistoryObj.HistoryObj.GlobalWriteData.append([startLba, txLen])
        self.HistoryObj.HistoryObj.LastWrittenLBA = startLba
        return txLen    
    
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
        
    def OnEPWRStart(self,argDict):
	if argDict["Block"] not in self.einLibObj.epwrBlocks:
	    self.einLibObj.epwrBlocks.append(argDict["Block"])
	#if self.blk_for_epwr == argDict["Block"]:
	#self.epwr_start_flag = True  
		       
	return        
        
    def CECChandlerSLC(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST SLC UECC HANDLER *************')   
        
        VBAtowhichErrorwasinjected = None
        LBAtoWhichErrorWasInjected= None
        tlen = None
        
        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
        else:
            try:
                startLba = sum(self.HistoryObj.HistoryObj.GlobalWriteData[-1]) - 1
            except:
                startLba = self.HistoryObj.HistoryObj.LastWrittenLBA
                
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error            
            self.VBAtowhichErrorwasinjected = kwargs['ErrorVBA']
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
            self.errorInjObj.InjectUECConCol(self.AddressBeforeUECCHandling)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)

        else:
            #Trigger Host Writes
            #Pre WA write
            #########################
            #self.writtendata = writeTotriggerHostAccumulation()
            temp_count = 400
            while(temp_count):
                Tlen = self.HostWrites(startLba)
                startLba += Tlen
                temp_count -= 1
                
            #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762            
            # Write a random number of JB
            
            ########################
            
            VBAtowhichErrorwasinjected, LBAtoWhichErrorWasInjected, tlen = self.GetVBAtoInject(blockType=0)
            
            if(VBAtowhichErrorwasinjected):
                self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected                
            else:
                self.VBAtowhichErrorwasinjected = self.SLCvbaWritten[-1]
            
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
            
            if(VBAtowhichErrorwasinjected):
                ErrDesc = (self.vtfContainer._livet.etBadPage, self.vtfContainer._livet.epHard, 0, 0, 0, 0)
                self.livetObj.GetFlash().SetLogicalTrigger(LBAtoWhichErrorWasInjected, self.vtfContainer._livet.foRead, 0, ErrDesc, None)
            else:
                self.errorInjObj.InjectUECConCol(self.AddressBeforeUECCHandling)
            
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
        
        #if('ModeAfterSwitch' in kwargs.keys()):
            #if(kwargs['ModeAfterSwitch'] != 'Operational'):
                #self.globalVarsObj.vtfContainer.switchProtocol()         
        #########################
            
        if(not VBAtowhichErrorwasinjected):
            for LBA, tlen in self.HistoryObj.HistoryObj.GlobalWriteData[::-1]:
                self.ccmObj.Read(LBA, tlen)  
                if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    kwargs['EINobj'].cmdpScsiFeLib.SdCmdsCls.CMD13()                
                #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762 
                #Optimization 
                if(self.UECCdetected):
                    break                
        else:
            self.ccmObj.Read(LBAtoWhichErrorWasInjected, tlen)
            if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                kwargs['EINobj'].cmdpScsiFeLib.SdCmdsCls.CMD13()
            #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762         
        ########################
        
        if(not self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "SLC UECC wasn't detected at the first instance")
            VBAtowhichErrorwasinjected, LBAtoWhichErrorWasInjected, tlen = self.GetVBAtoInject(blockType=0)                        
            if(VBAtowhichErrorwasinjected):
                self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected                
            else:
                self.VBAtowhichErrorwasinjected = self.SLCvbaWritten[-1]
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            if(VBAtowhichErrorwasinjected):
                ErrDesc = (self.vtfContainer._livet.etBadPage, self.vtfContainer._livet.epHard, 0, 0, 0, 0)
                self.livetObj.GetFlash().SetLogicalTrigger(LBAtoWhichErrorWasInjected, self.vtfContainer._livet.foRead, 0, ErrDesc, None)
            else:
                self.errorInjObj.InjectUECConCol(self.AddressBeforeUECCHandling)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling) 
            self.ccmObj.Read(LBAtoWhichErrorWasInjected, tlen)
            if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                kwargs['EINobj'].cmdpScsiFeLib.SdCmdsCls.CMD13()
            #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762 
            if(not self.UECCdetected):
                self.logger.Info(self.globalVarsObj.TAG, "SLC UECC wasn't detected at the second instance")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                self.errorManager.DeRegisterCallback()            
                return "SLC UECC wasn't detected" 
        
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):        
            if(not self.XORrecoveryDetails):
                self.logger.Info(self.globalVarsObj.TAG, "XOR recovery didnt trigger in NVMe mode")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                self.errorManager.DeRegisterCallback()            
                return "XOR recovery didnt trigger in NVMe mode"         
                
            
        if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
            if(not self.ReadError):
                self.logger.Info(self.globalVarsObj.TAG, "Read error didnt occur in SD mode")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                self.errorManager.DeRegisterCallback()            
                return "Read error didnt occur in SD mode"         
            
            if(self.XORrecoveryDetails):
                self.logger.Info(self.globalVarsObj.TAG, "XOR recovery triggerred in SD mode")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                self.errorManager.DeRegisterCallback()            
                return "XOR recovery triggerred in SD mode"             
                   
        
        self.logger.Info(self.globalVarsObj.TAG, "############ Host SLC UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        self.errorManager.DeRegisterCallback()        
        return True        
    
    def GetLBAtoInject(self, **kwargs):
        LBA_list = [LBA for LBA,tlen in self.HistoryObj.HistoryObj.GlobalWriteData]
        LBA_list.append(sum(self.HistoryObj.HistoryObj.GlobalWriteData[-1])-1)
        self.globalVarsObj.randomObj.shuffle(LBA_list)
        
        picked_LBA = self.globalVarsObj.randomObj.choice(LBA_list)

        return picked_LBA
        
    def CECCHandlerTLC(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC CECC HANDLER *************')
        
        VBAtowhichErrorwasinjected = None
        LBAtoWhichErrorWasInjected= None
        tlen = None
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
        else:
            try:
                startLba = sum(self.HistoryObj.HistoryObj.GlobalWriteData[-1]) - 1
            except:
                startLba = self.HistoryObj.HistoryObj.LastWrittenLBA
        
        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error            
            self.VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] 
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)            
            self.errorInjObj.InjectUECC(self.AddressBeforeUECCHandling)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which CECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which CECC is injected :',self.AddressBeforeUECCHandling)
        
        else:
            #Trigger Host Writes
            #########################
            #if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            #    self.sctputilsobj.changeModeToTLC()
            
            #self.sctputilsobj.SetMvpThreshold(-15,-15)
            #sample SLC write
            Tlen = self.HostWrites(startLba)            
            
            ########################            
            """
            while(not self.IsRequiredBlockSelectedForRelocation):
                Tlen = self.HostWrites(startLba)
                startLba += Tlen
                
            #write till The block selected finishes
            
            while(self.IsRequiredBlockSelectedForRelocation):
                Tlen = self.HostWrites(startLba)
                startLba += Tlen            
            """
            
            #do some more writes
            temp_count = 400
            while(temp_count):
		if self.UECCdetected and self.ccmObj.powerCycleIssued:
		    self.UECCdetected = False
                Tlen = self.HostWrites(startLba)
                startLba += Tlen
                temp_count -= 1
            
            self.ccmObj.powerCycleIssued = False
            errorLBA = self.GetLBAtoInject()
            self.logger.Info(self.globalVarsObj.TAG, 'Injecting CECC on LBA: 0x%X' % errorLBA)
            self.__errorAddress = self.sctpUtilsObj.TranslateLogicalToPhy(errorLBA)
	    self.livetObj.VcdDump(1)
            self.globalVarsObj.eiObj.InjectCECCErrorWithSTM(errorPhyAddress=self.__errorAddress)
	    self.CECCBlockList = [self.__errorAddress.block, self.__errorAddress.wordLine]
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which CECC is injected: %s'% self.__errorAddress)
            
        #if('ModeAfterSwitch' in kwargs.keys()):
            #if(kwargs['ModeAfterSwitch'] != 'Operational'):
                #if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    #self.SDutilsObj.performShutdown(operation='GSD')
                #elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    #self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                #elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    #self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="GSD") 
                #else:
                    #self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")
                    
                    
        #########################
        for LBA, tlen in self.HistoryObj.HistoryObj.GlobalWriteData:
	    self.__errorAddress = self.sctpUtilsObj.TranslateLogicalToPhy(LBA)
	    self.UECCBlockList = list()
	    try:
		self.ccmObj.Read(LBA, tlen)
		if self.UECCBlockList in self.einLibObj.errorAffectedLbaUECC:
		    self.logger.Info(self.globalVarsObj.TAG, 'UECC detected but not injected in CECC Handling. So clearing the error and proceeding with test')
		    self.clearErrsExcptns()
		    self.UECCdetected = False			
	    except:
		if self.UECCdetected and self.UECCBlockList in self.einLibObj.errorAffectedLbaUECC:
		    self.logger.Info(self.globalVarsObj.TAG, 'UECC detected but not injected in CECC Handling. So clearing the error and proceeding with test')
		    self.clearErrsExcptns()
		    self.UECCdetected = False    
		elif self.HdrUeccDetected:
		    #self.__errorAddress = self.sctpUtilsObj.TranslateLogicalToPhy(LBA)
		    self.HeaderUECCBlockList = [self.__errorAddress.block, self.__errorAddress.wordLine]
		    self.UECCDetectedList = [x for x in self.einLibObj.UECCInjectionList if x>=LBA and x<=LBA+tlen-1]
		    if len(self.UECCDetectedList)>0 or self.HeaderUECCBlockList in self.einLibObj.errorAffectedLbaUECC:
			self.logger.Info(self.globalVarsObj.TAG, 'Header UECC detected but not injected in CECC Handling. So clearing the error and proceeding with test')
			self.clearErrsExcptns()
		    else:
			raise ValidationError.TestFailError("CECCHandling","Header UECC detected, but UECC is not injected")	    
		else:
		    raise ValidationError.TestFailError("CECCHandling","Read is failed")	    
			
            #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762   


        ######################## 
        self.livetObj.VcdDump(0)    
        #if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):              
            #if(not self.XORrecoveryDetails):
                #self.logger.Info(self.globalVarsObj.TAG, "XOR recovery didnt trigger in NVMe mode")
                #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                #self.ResetVariables()
                #self.DeregisterAllWaypoint()
                #self.errorManager.DeRegisterCallback()            
                #return "XOR recovery didnt trigger in NVMe mode"         
                
            
        #if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
            #if(not self.ReadError):
                #self.logger.Info(self.globalVarsObj.TAG, "Read error didnt occur in SD mode")
                #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                #self.ResetVariables()
                #self.DeregisterAllWaypoint()
                #self.errorManager.DeRegisterCallback()            
                #return "Read error didnt occur in SD mode"         
            
            #if(self.XORrecoveryDetails):
                #self.logger.Info(self.globalVarsObj.TAG, "XOR recovery triggerred in SD mode")
                #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                #self.ResetVariables()
                #self.DeregisterAllWaypoint()
                #self.errorManager.DeRegisterCallback()            
                #return  "XOR recovery triggerred in SD mode"               
        
        if(self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "TLC UECC detected but not expected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            self.errorManager.DeRegisterCallback()
            return "TLC UECC detected but not expected"
        
	self.clearErrsExcptns()
	self.globalVarsObj.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	self.vtfContainer.cmd_mgr.ClearExceptionNotification()
	ErrorManager.ClearAllErrors()         
        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC CECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        self.errorManager.DeRegisterCallback()        
        return True            
        
