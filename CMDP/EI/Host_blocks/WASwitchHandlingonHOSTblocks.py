import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WaypointReg
import SDUtils
import Extensions.CVFImports as pyWrap
import random
import CMDP.CMDP_History as History
import SDExpressWrapper as SDExWrap
import CTFServiceWrapper as ServiceWrap

WriteAbortDetected = False

def OnWriteAbort(package, addr):
    """
    Write Abort callback function
    Arguments: 
    """
    global WriteAbortDetected
    WriteAbortDetected = True
    print('DETECTED WRITE ABORT')
    
class WAhandler:
    
    __staticWAObj = None

    ##
    # @brief A method to create a singleton object of LOG WA HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not WAhandler.__staticWAObj:
            WAhandler.__staticWAObj = super(WAhandler,cls).__new__(cls, *args, **kwargs)

        return WAhandler.__staticWAObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.SDutilsObj = SDUtils.SDUtils
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba        
        self.HistoryObj = History.EpicCallbacks()
        self.livetObj.UnregisterLivetCallback(self.livetObj.lcFlashProgramAbort)        
        self.livetObj.RegisterLivetCallback(self.livetObj.lcFlashProgramAbort, OnWriteAbort)                        
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj, self.logger)
            self.wayPointDict = {
                "WP_PS_BBM_PH_BLOCK_RELINK"         : [self.WP_PS_BBM_PH_BLOCK_RELINK], 
                "WP_FTL_HWD_WRITE_JB_VBA"           : [self.WP_FTL_HWD_WRITE_JB_VBA],
                "WP_FTL_RLC_WRITE_JB_VBA"           : [self.WP_FTL_RLC_WRITE_JB_VBA],
                "WP_FTL_BML_PARTIAL_BLOCK_ADDED"    : [self.WP_FTL_BML_PARTIAL_BLOCK_ADDED],
                "WP_PS_OTG_PROG_FLASH_ADDR"         : [self.WP_PS_OTG_PROG_FLASH_ADDR],
                "WP_MNT_PERFORM_BRLC"               : [self.WP_MNT_PERFORM_BRLC]
            }
            self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)    
                
    def ErrorHandlerFunction(self,statusCodeType,statusCode):	
        self.logger.Info(self.globalVarsObj.TAG, "Callback received with received status code: %d and status code type: %d"%(statusCode,statusCodeType))       
        self.KWARGS['EINobj'].cmdpScsiFeLib.inLowVoltageMode = False
        
        if((WriteAbortDetected or (statusCode in [5,11,144]) or self.FromTLC2TLCrelocation)) and not self.AlreadySwitched:
            self.errorManager.ClearAllErrors() 
            self.AlreadySwitched = True
            #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762                            
            #self.vtfContainer.switchProtocol(powerCycleType="UGSD")
            if(self.vtfContainer.activeProtocol == 'SD_OF_SDPCIe'):
                SDExWrap.SwitchProtocol(shutdownType=ServiceWrap.UNGRACEFUL)                  
                self.vtfContainer.activeProtocol = 'NVMe_OF_SDPCIe'
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode = False
            else:
                SDExWrap.SwitchProtocol(shutdownType=ServiceWrap.ABORT)                  
                self.vtfContainer.activeProtocol = 'SD_OF_SDPCIe'
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode = True
        else:
            self.errorManager.ClearAllErrors()   
        
        #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762

    def WP_MNT_PERFORM_BRLC(self,eventKey,args, pid) :
        self.BRLChappended = True
        
    def WP_PS_OTG_PROG_FLASH_ADDR(self,eventKey,args, pid):
        print('OTG PROGRAM')
        print('VBA : %d, Block Type: %d'%(args[0],args[1]))
        print('DEVBA0 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[2],args[3],args[4],args[5],args[6]))
        print('DEVBA1 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[7],args[8],args[9],args[10],args[11]))        
        if(args[1] == 1 and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.TLCvbaWritten.append(args[0])
            
    def WP_FTL_BML_PARTIAL_BLOCK_ADDED(self,eventKey,args, pid):
        #partialItem_p->partialJBA.jumboBlockId, ptnId, partialListType,SAT_VCGetVC(partialItem_p->partialJBA), partialItem_p->partialAddReason
        
        self.BlockAddedToPartialList = True
        self.BlockWhichWasAddedToPartialBlock = args[0]
        
        
    def InjectErrorFromWP(self,vba,die,plane,block,wl,string,channel):
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        package = channel
        phyAddress=[die,plane,block,wl,string,0,0]            
        self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)
        self.logger.Info(self.globalVarsObj.TAG, "Injected Write Abort on VBA: %d"% (vba))
        self.logger.Info(self.globalVarsObj.TAG, "Physical Address -> Die: %d, Plane: %d, PhysicalBlock: %d, Wordline: %d, String: %d" \
                         % (die,plane,block,wl,string))
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)        
            
    def WP_FTL_RLC_WRITE_JB_VBA(self,eventKey,args, pid):
        self.TLCvbaWritten.append(args[1])       
        self.TLCjbWritten.append(args[0])
        
    def WP_FTL_HWD_WRITE_JB_VBA(self,eventKey,args, pid):
        self.SLCvbaWritten.append(args[1])       
        self.SLCjbWritten.append(args[0])
       
    def WP_PS_WA_DETECTED(self,eventKey,args, pid):
        self.WAdetected = True
    
    def WP_PS_BBM_PH_BLOCK_RELINK(self,eventKey,args, pid):
        if(args[4]== self.AddressBeforeWAHandling['physicalblock'] and args[3]== self.AddressBeforeWAHandling['plane']):
            self.RelinkingnotHappened = False
        else:
            self.RelinkingHappened = True
    
    def WAinjector(self,VBA, blocktype=0):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1, blockType=blocktype)        
        phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        self.livetObj.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, 'WA is injected to ',physical_address)
                
    
    def ResetVariables(self):
        global WriteAbortDetected
        WriteAbortDetected = False
        
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
        self.SLCvbaWritten = []
        self.SLCjbWritten = []
        self.TLCvbaWritten = []
        self.TLCjbWritten = []   
        self.FromTLC2TLCrelocation = False
        self.SetSwitchDuringAbort(setFlag=1)
        self.AlreadySwitched = False
        self.BRLChappended = False
        self.KWARGS = {}
        
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
    
    def SetSwitchDuringAbort(self, setFlag = 0):
        self.globalVarsObj.configParser.SetValue("Switch_protocol_after_abort", setFlag)
    
    def WAHandlerSLC(self, Blockstate, **kwargs):
        global WriteAbortDetected 
        self.KWARGS = kwargs
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.WaypointRegObj.RegisterWP(self.wayPointDict)   
        self.SetSwitchDuringAbort(setFlag=1)
        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST SLC WA HANDLER *************')
        
        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16
            
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
        
        else:
            #Trigger Host Writes
            #Pre WA write
            #########################
            #self.writtendata = writeTotriggerHostAccumulation()
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)
            # Write a random number of JB
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()            
            ########################
            
            VBAtowhichErrorwasinjected = self.SLCvbaWritten[-1]  + 16                
            self.WAinjector(VBAtowhichErrorwasinjected)
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
            self.JBBeforeWAHandling = self.SLCjbWritten[-1]
            self.logger.Info(self.globalVarsObj.TAG, 'SLC JB before WA Detection :',self.JBBeforeWAHandling)            
            
        #########################
        #WA detection Write
        try:   
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=5000, txLenThreshold=None)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()               
        except:
            self.ErrorHandlerFunction(0, 144)
        
        ########################
        
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=5000, txLenThreshold=None)
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.globalVarsObj.ccmObj.DoFlushCache()               

        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "SLC WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "SLC WA wasn't detected"  
        
        self.JBAfterWAHandling = self.SLCjbWritten[-1]
        self.logger.Info(self.globalVarsObj.TAG, 'SLC JB After WA Detection :',self.JBAfterWAHandling)
        
        if(not self.BRLChappended and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC didnt happen in nvme mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC didnt happen in nvme mode"  
        
        if(self.BRLChappended and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC Happened in SD mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC Happened in SD mode" 
                
        if(self.JBAfterWAHandling == self.JBBeforeWAHandling and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "SLC Block Wasn't added to partial List")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "SLC Block Wasn't added to partial List"           
        
        self.logger.Info(self.globalVarsObj.TAG, "############ Host SLC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True        
    
    
    def WAHandlerTLC(self, Blockstate, **kwargs):
        global WriteAbortDetected     
        self.KWARGS = kwargs
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.WaypointRegObj.RegisterWP(self.wayPointDict)           
        self.SetSwitchDuringAbort(setFlag=1)
        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC WA HANDLER *************')
        
        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
            self.FromTLC2TLCrelocation = True
        else:
            startLba = self.HistoryObj.HistoryObj.LastWrittenLBA
        
        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 48
            
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
        
        else:
            #Trigger Host Writes
            #########################
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 1024 * 10 +1000, txLenThreshold=None)
            ########################            
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
            
            VBAtowhichErrorwasinjected = self.TLCvbaWritten[-1] + 48
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
            self.JBBeforeWAHandling = self.TLCjbWritten[-1]
            self.logger.Info(self.globalVarsObj.TAG, 'TLC JB before WA Detection :',self.JBBeforeWAHandling)            
            

        #########################
        self.sctputilsobj.SetMvpThreshold(-15,-15)
        while(self.TLCvbaWritten == []):            
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
        
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
        
        ######################## 
        
        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.globalVarsObj.ccmObj.DoFlushCache()

        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "TLC WA wasn't detected at the first instance")
            VBAtowhichErrorwasinjected = self.TLCvbaWritten[-1] + 48
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.WAinjector(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
            if(not WriteAbortDetected):
                self.logger.Info(self.globalVarsObj.TAG, "TLC WA wasn't detected at the second instance")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "TLC WA wasn't detected"
        
           
        self.JBAfterWAHandling = self.TLCjbWritten[-1]
        self.logger.Info(self.globalVarsObj.TAG, 'TLC JB After WA Detection :',self.JBAfterWAHandling)
        
        if(self.JBAfterWAHandling == self.JBBeforeWAHandling and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "SLC Block Wasn't added to partial List")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "SLC Block Wasn't added to partial List"           
        
        if(not self.BRLChappended and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC didnt happen in nvme mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC didnt happen in nvme mode"  
        
        if(self.BRLChappended and self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe"):
            self.logger.Info(self.globalVarsObj.TAG, "BRLC Happened in SD mode")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "BRLC Happened in SD mode"          
                         
        
        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            
