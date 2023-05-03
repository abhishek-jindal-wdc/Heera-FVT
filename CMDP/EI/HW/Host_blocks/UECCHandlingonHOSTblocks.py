import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
import random
import CMDP.CMDP_History as History
import CMDP.EINCTD_Library as EINCTDLib

    
class UECChandler:
    
    __staticUECCObj = None

    ##
    # @brief A method to create a singleton object of LOG WA HANDLER
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
        self.globalVarsObj = GlobalVars.GlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.SDutilsObj = SDUtils.SDUtils()
        self.endLba = self.globalVarsObj.endLba        
        self.ccmObj = self.globalVarsObj.ccmObj                
        self.HistoryObj = History.EpicCallbacks()
        self.startLba = self.HistoryObj.HistoryObj.LastWrittenLBA
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            if(self.HistoryObj.Verbose):
                self.wayPointDict = {
                    "WP_FTL_HWD_WRITE_JB_VBA"           : [self.WP_FTL_HWD_WRITE_JB_VBA,'PrintArguments'],
                    "WP_FTL_RLC_WRITE_JB_VBA"           : [self.WP_FTL_RLC_WRITE_JB_VBA,'PrintArguments'],
                    "WP_PS_OTG_PROG_FLASH_ADDR"         : [self.WP_PS_OTG_PROG_FLASH_ADDR,'PrintArguments'],
                    "WP_PS_REH_BES7"                    : [self.WP_PS_REH_BES7_Callback,'PrintArguments'],         
                    "WP_PS_XOR_RECOVERY_START"          : [self.WP_PS_XOR_RECOVERY_START,'PrintArguments'],
                    "WP_FTL_RLC_SOURCE_BLOCK_SELECTED"  : [self.WP_FTL_RLC_SOURCE_BLOCK_SELECTED,'PrintArguments']                    
                }
            else:
                self.wayPointDict = {
                    "WP_FTL_HWD_WRITE_JB_VBA"           : [self.WP_FTL_HWD_WRITE_JB_VBA],
                    "WP_FTL_RLC_WRITE_JB_VBA"           : [self.WP_FTL_RLC_WRITE_JB_VBA],
                    "WP_PS_OTG_PROG_FLASH_ADDR"         : [self.WP_PS_OTG_PROG_FLASH_ADDR],
                    "WP_PS_REH_BES7"                    : [self.WP_PS_REH_BES7_Callback],     
                    "WP_PS_XOR_RECOVERY_START"          : [self.WP_PS_XOR_RECOVERY_START],
                    "WP_PS_OTG_SENSE_FLASH_ADDR"        : [self.WP_PS_OTG_SENSE_FLASH_ADDR],
                    "WP_FTL_RLC_SOURCE_BLOCK_SELECTED"  : [self.WP_FTL_RLC_SOURCE_BLOCK_SELECTED]
                }
                
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
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
    
    def WP_FTL_RLC_SOURCE_BLOCK_SELECTED(self,eventKey,args, pid):
        if(self.ReferenceSLCJB == args[1]):
            self.IsRequiredBlockSelectedForRelocation = True
        
        
    def WP_PS_OTG_SENSE_FLASH_ADDR(self,eventKey,args, pid):
        #print('OTG SENSE')
        #print('VBA : %d, Block Type: %d'%(args[0],args[1]))
        #print('DEVBA0 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[2],args[3],args[4],args[5],args[6]))
        #print('DEVBA1 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[7],args[8],args[9],args[10],args[11]))
        return 
        
    def WP_PS_OTG_PROG_FLASH_ADDR(self,eventKey,args, pid):
        #print('OTG PROGRAM')
        #print('VBA : %d, Block Type: %d'%(args[0],args[1]))
        #print('DEVBA0 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[2],args[3],args[4],args[5],args[6]))
        #print('DEVBA1 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[7],args[8],args[9],args[10],args[11]))
        if(args[1] == 1 and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.TLCvbaWritten.append(args[0])
            
    def WP_FTL_RLC_WRITE_JB_VBA(self,eventKey,args, pid):
        if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
            self.TLCvbaWritten.append(args[1])       
            self.TLCjbWritten.append(args[0])
    
    def WP_PS_REH_BES7_Callback(self,eventKey,args, pid):
        self.UECCdetected = True    
        
    def WP_FTL_HWD_WRITE_JB_VBA(self,eventKey,args, pid):
        self.SLCvbaWritten.append(args[1])       
        self.SLCjbWritten.append(args[0])

    def WP_PS_XOR_RECOVERY_START(self,eventKey,args, pid):
        self.XORrecoveryDetails.append(args)
        
    def ResetVariables(self):
        global WriteAbortDetected
        WriteAbortDetected = False
        self.ReadError = False
        self.JBBeforeWAHandling = False
        self.JBAfterWAHandling = False
        self.BlockWhichWasAddedToPartialBlock = None
        self.BlockAddedToPartialList = False
        self.writtendata = []
        self.WAdetected = False
        self.RelinkingHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterWAHandling = None
        self.AddressBeforeWAHandling = None
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
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.ccmObj.DoFlushCache()
        self.HistoryObj.HistoryObj.GlobalWriteData.append([startLba, txLen])
        self.HistoryObj.HistoryObj.LastWrittenLBA = startLba
        return txLen    
    
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    def UECCHandlerSLC(self, Blockstate, **kwargs):
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
            
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
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
                
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.ccmObj.DoFlushCache()            
            self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762            
            # Write a random number of JB
            
            ########################
            
            VBAtowhichErrorwasinjected, LBAtoWhichErrorWasInjected, tlen = self.GetVBAtoInject(blockType=0)
            
            if(VBAtowhichErrorwasinjected):
                self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected                
            else:
                self.VBAtowhichErrorwasinjected = self.SLCvbaWritten[-1]
            
            self.sctputilsobj.ErrorInjection(subOpcode=0, configType="singleError", operationType="Read", addrType="LBA", addr=LBAtoWhichErrorWasInjected, nsid=1, pattern="UECC", dataBuffer=None, binType=None, ErrLog=1, MBrevive=1, JBrevive=1, SurvivePC=1, isE2E=0, slot1=[0,0,0,0])
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)            
                        
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
        
        if('ModeAfterSwitch' in kwargs.keys()):
            if(kwargs['ModeAfterSwitch'] != 'Operational'):
                self.globalVarsObj.vtfContainer.switchProtocol()         
        #########################
            
        if(not VBAtowhichErrorwasinjected):
            for LBA, tlen in self.HistoryObj.HistoryObj.GlobalWriteData[::-1]:
                self.ccmObj.Read(LBA, tlen)  
                if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    kwargs['EINobj'].cmdpScsiFeLib.SdCmdsCls.CMD13()                
                self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762 
                #Optimization 
                if(self.UECCdetected):
                    break                
        else:
            self.ccmObj.Read(LBAtoWhichErrorWasInjected, tlen)
            if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                kwargs['EINobj'].cmdpScsiFeLib.SdCmdsCls.CMD13()
            self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762         
        ########################
        
        if(not self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "SLC UECC wasn't detected")
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
    
    def GetVBAtoInject(self, blockType = 0, **kwargs):
        LBA_list = [LBA for LBA,tlen in self.HistoryObj.HistoryObj.GlobalWriteData]
        LBA_list.append(sum(self.HistoryObj.HistoryObj.GlobalWriteData[-1])-1)
        self.globalVarsObj.randomObj.shuffle(LBA_list)
        vba_selected = None
        picked_LBA = None
        if(blockType == 1):
            for picked_LBA in LBA_list:
                temp_dict = self.sctputilsobj.LBA2VBA(picked_LBA, returnDict=True)
                
                if(temp_dict['blockType'] == blockType):
                    vba_selected = self.sctputilsobj.LBA2VBA(picked_LBA)
                    break
        
        else:
            for picked_LBA in LBA_list[::-1]:
                temp_dict = self.sctputilsobj.LBA2VBA(picked_LBA, returnDict=True)
                
                if(temp_dict['blockType'] == blockType):
                    vba_selected = self.sctputilsobj.LBA2VBA(picked_LBA)
                    break          
        
        #find tlen, even if VBA is not found, we shall filter later
        tlen = 1024
        if(picked_LBA == LBA_list[-1]):
            tlen =  self.HistoryObj.HistoryObj.GlobalWriteData[-2][-1]
        else:
            try:
                tlen = self.HistoryObj.HistoryObj.GlobalWriteData[::-1][LBA_list[::-1].index(picked_LBA)-1][-1]
            except:
                pass
        return vba_selected, picked_LBA, tlen
        
    def UECCHandlerTLC(self, Blockstate, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC UECC HANDLER *************')
        
        VBAtowhichErrorwasinjected = None
        LBAtoWhichErrorWasInjected= None
        tlen = None
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
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
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
        
        else:
            #Trigger Host Writes
            #########################
            #if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            #    self.sctputilsobj.changeModeToTLC()
            
            self.sctputilsobj.SetMvpThreshold(-15,-15)
            #sample SLC write
            Tlen = self.HostWrites(startLba)            
            self.ReferenceSLCJB = self.SLCjbWritten[-1]
            
            while(self.TLCvbaWritten == []):
                Tlen = self.HostWrites(startLba)
                startLba += Tlen
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
                Tlen = self.HostWrites(startLba)
                startLba += Tlen
                temp_count -= 1
            
            VBAtowhichErrorwasinjected, LBAtoWhichErrorWasInjected, tlen = self.GetVBAtoInject(blockType=1)
            
            if(VBAtowhichErrorwasinjected):
                self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected                
            else:
                self.VBAtowhichErrorwasinjected = self.TLCvbaWritten[-1]
            
            self.AddressBeforeUECCHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)                        
            self.errorInjObj.InjectUECC(self.AddressBeforeUECCHandling)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which UECC is injected :',self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address to which UECC is injected :',self.AddressBeforeUECCHandling)
            
        if('ModeAfterSwitch' in kwargs.keys()):
            if(kwargs['ModeAfterSwitch'] != 'Operational'):
                if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.SDutilsObj.performShutdown(operation='GSD')
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="GSD") 
                else:
                    self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")
                    
                    
        #########################
        if(not VBAtowhichErrorwasinjected):
            for LBA, tlen in self.HistoryObj.HistoryObj.GlobalWriteData:
                self.ccmObj.Read(LBA, tlen)     
                if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    kwargs['EINobj'].cmdpScsiFeLib.SdCmdsCls.CMD13()
                
                self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762   
                #Optimization 
                if(self.UECCdetected):
                    break
        else:
            self.ccmObj.Read(LBAtoWhichErrorWasInjected, tlen)
            if(self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                kwargs['EINobj'].cmdpScsiFeLib.SdCmdsCls.CMD13()
            
            self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762 
        ######################## 
        
            
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
                return  "XOR recovery triggerred in SD mode"               
        
        if(not self.UECCdetected):
            self.logger.Info(self.globalVarsObj.TAG, "TLC UECC wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            self.errorManager.DeRegisterCallback()
            return "TLC UECC wasn't detected"
        
        
        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC UECC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        self.errorManager.DeRegisterCallback()        
        return True            
        
