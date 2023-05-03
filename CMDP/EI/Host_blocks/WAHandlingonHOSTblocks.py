import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WaypointReg
import Utils
import Extensions.CVFImports as pyWrap
import random
#import EIMediator
import FwConfig
#import CMDP.EINCTD_Library as CMDP_AP_Lib
#import NVMeCMDWrapper as NVMeWrap

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
        #self.eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
        self.fwConfigObj = FwConfig.FwConfig(self.vtfContainer)
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.TLCBlock = False
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba        
        self.livet = self.vtfContainer._livet
        self.livet.UnregisterLivetCallback(self.livet.lcFlashProgramAbort) 
        self.livet.UnregisterLivetCallback(self.livet.lcPostProgramAbort)
        self.livet.UnregisterLivetCallback(self.livet.lcPreProgramAbort)
        self.globalVarsObj.eiObj.RegisterPostWriteAbortCallback(OnWriteAbort)
        self.globalVarsObj.eiObj.RegisterPreWriteAbortCallback(OnWriteAbort)
        self.globalVarsObj.eiObj.RegisterWriteAbortCallback(OnWriteAbort)
        
        if self.vtfContainer.isModel is True:
            self.livet = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
            self.wayPointDict = {
                "DLM_RELINKED_METABLOCK_FORMED" : [], 
                "UM_WRITE"           : [self.OnUMWrite],
                "MLC_COMPACTION_DATA_TRANSFER_BEGIN" : [], #GCC_GOING_TO_WRITE
                "SLC_COMPACTION_DATA_TRANSFER_BEGIN" : []
            }
            self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.globalVarsObj.eiObj.ErrorHandlerFunction) 
            
    def ErrorHandlerFunction(self,statusCodeType,statusCode):	
        self.logger.Info(self.globalVarsObj.TAG, "Callback received with received status code: %d and status code type: %d"%(statusCode,statusCodeType))       
        self.KWARGS['EINobj'].cmdpScsiFeLib.inLowVoltageMode = False
        if(self.AlreadySwitched):
            self.errorManager.ClearAllErrors()
            return 
        
        if(WriteAbortDetected or (statusCode == 144) or (statusCode == 5) or (statusCode == 11) or self.FromTLC2TLCrelocation):
            self.errorManager.ClearAllErrors() 
            self.AlreadySwitched = True
            #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762                            
            if(self.vtfContainer.activeProtocol == 'SD_OF_SDPCIe'):
                pass
            else:
                ulActivateControllerTimeOut = 0
                retTuple = self.globalVarsObj.configParser.GetValue("activate_controller_time_out", ulActivateControllerTimeOut)
                ulActivateControllerTimeOut = retTuple[0]             
                ObjNVMeActivateCtlr = NVMeWrap.ActivateCntrlrCMD(False, False, False, True, ulActivateControllerTimeOut)
                ObjNVMeActivateCtlr.Execute()
                ObjNVMeActivateCtlr.HandleOverlappedExecute()
                ObjNVMeActivateCtlr.HandleAndParseResponse()                
        else:
            self.errorManager.ClearAllErrors()
        
        #self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762      
            
    def InjectErrorFromWP(self,vba,die,plane,block,wl,string,channel):
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        package = channel
        phyAddress=[die,plane,block,wl,string,0,0]            
        self.livet.GetFlash().InjectError(package, phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)
        self.logger.Info(self.globalVarsObj.TAG, "Injected Write Abort on VBA: %d"% (vba))
        self.logger.Info(self.globalVarsObj.TAG, "Physical Address -> Die: %d, Plane: %d, PhysicalBlock: %d, Wordline: %d, String: %d" \
                         % (die,plane,block,wl,string))
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)        
            
        
    def OnUMWrite(self,args):
        """
        "Bank","LG","LGOffset","transferLength","StreamType","StreamID","MB","MBOffset","primary","numSectorsToPrepad","numSectorsToPostpad","startWriteOffset"
        """
        if args["primary"]:
            self.primaryMBWritten = args["MB"]
            self.primaryMBOffsetWritten = args["MBOffset"]
        else:
            self.secondaryMBWritten = args["MB"]      
            self.secondaryMBOffsetWritten = args["MBOffset"]
            
        self.txlen = args["transferLength"]
        if args["StreamType"] == 0:
            self.TLCBlock = True
        return        
                       
    def WAinjector(self, MB, MBOffset):
        #physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1, blockType=blocktype)        
        #phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
        #errorPersistence = 1 
        #paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        #self.livet.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        
        phyAddr =  self.globalVarsObj.eiObj.GetPhysicalAddress(MB, MBOffset)
        errorType = self.globalVarsObj.randomObj.choice(["wrab", "prwa", "powa"])
        self.globalVarsObj.eiObj.InjectWriteAbortError(errorPhyAddress = phyAddr, errorType = errorType)
        return     
    
    def ResetVariables(self):
        global WriteAbortDetected
        WriteAbortDetected = False
        self.BRLChappended = False
        self.JBBeforeWAHandling = False
        self.JBAfterWAHandling = False
        self.BlockWhichWasAddedToPartialBlock = None
        self.BlockAddedToPartialList = False
        self.writtendata = []
        self.txlen = None
        self.WAInjected = False
        self.WAdetected = False
        self.RelinkingHappened = False
        self.AddressAfterWAHandling = None
        self.AddressBeforeWAHandling = None
        self.secondaryMBWritten = None
        self.secondaryMBOffsetWritten = None
        self.primaryMBWritten = None
        self.primaryMBOffsetWritten = None
        self.FromTLC2TLCrelocation = False
        self.KWARGS = {}
        
        
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
        
    def WAHandlerSLC(self, Blockstate, **kwargs):
        global WriteAbortDetected 
        self.KWARGS = kwargs
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.WaypointRegObj.RegisterWP(self.wayPointDict)           
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
            
            self.secondaryMBWritten = None
            while(self.secondaryMBWritten == None):            
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
            
            # Use the txlen as offset to inject error from last written offset            
            offset = 2 * self.txlen
            errorMB = self.secondaryMBWritten
            errorMBOffset = self.secondaryMBOffsetWritten + offset
            
            # If errorMBOffset is less than TLC MB size, perform error injection. 
            # Else skip EI for this instance, will be injected in next instance.
            if errorMBOffset < self.fwConfigObj.slcMBSize:
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))
                self.WAinjector(errorMB, errorMBOffset)
                self.WAInjected = True
                
        #########################
        #WA detection Write
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)
        ########################
            
        if(not WriteAbortDetected):
            self.WAInjected = False
            self.logger.Info(self.globalVarsObj.TAG, "SLC WA wasn't detected at the first instance")
            self.secondaryMBWritten = None
            while(self.secondaryMBWritten == None):            
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
            
            # Use the txlen as offset to inject error from last written offset            
            offset = 2 * self.txlen 
            errorMB = self.secondaryMBWritten
            errorMBOffset = self.secondaryMBOffsetWritten + offset
            
            # If errorMBOffset is less than TLC MB size, perform error injection. 
            # Else skip EI for this instance, will be injected in next instance.
            if errorMBOffset < self.fwConfigObj.slcMBSize:
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))
                self.WAinjector(errorMB, errorMBOffset)
                self.WAInjected = True            
            # Perform writes to hit injected error
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)

            if(not WriteAbortDetected):
                self.logger.Info(self.globalVarsObj.TAG, "SLC WA wasn't detected at the second instance")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "SLC WA wasn't detected"  
            
        self.logger.Info(self.globalVarsObj.TAG, "############ Host SLC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True        
    
    
    def WAHandlerTLC(self, Blockstate, **kwargs):
        global WriteAbortDetected 
        self.KWARGS = kwargs
        startLba = 0
        self.WAInjected = False
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC WA HANDLER *************')
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
            
        self.WaypointRegObj.RegisterWP(self.wayPointDict)   
        
        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
        else:
            startLba = 0
            
        """
        First error injection attempt
        """
        if('ErrorVBA' in kwargs.keys()):
            #Not updated in Heera yet
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 48
                        
            # Use the txlen as offset to inject error from last written offset            
            offset = 2 * self.txlen # kwargs['EINobj'].GetTransferLength(txLenThreshold=None)
            errorMB = self.primaryMBWritten
            errorMBOffset = self.primaryMBOffsetWritten + offset
            
            # If errorMBOffset is less than TLC MB size, perform error injection. Else skip EI for this instance, will be injected later.
            if errorMBOffset < self.fwConfigObj.mlcMBSize:
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))                
                self.WAinjector(errorMB, errorMBOffset)
                self.WAInjected = True
        else:
            #Trigger some Host Writes
            #########################
            self.primaryMBWritten = None
            while(self.primaryMBWritten == None):            
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
            
            # Use the txlen as offset to inject error from last written offset            
            offset = 2 * self.txlen 
            errorMB = self.primaryMBWritten
            errorMBOffset = self.primaryMBOffsetWritten + offset
            
            # If errorMBOffset is less than TLC MB size, perform error injection. 
            # Else skip EI for this instance, will be injected in next instance.
            if self.TLCBlock:
                maxSize = self.fwConfigObj.mlcMBSize
            else:
                maxSize = self.fwConfigObj.slcMBSize
                
            if errorMBOffset < maxSize:
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))                
                self.WAinjector(errorMB, errorMBOffset)
                self.WAInjected = True
                
        # Perform writes to hit the injected error
        self.primaryMBWritten = None
        while(self.primaryMBWritten == None):            
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=10240, txLenThreshold=None)
        
        ######################## 
        """
        Second error injection attempt
        """
        if(not WriteAbortDetected):
            self.WAInjected = False
            self.logger.Info(self.globalVarsObj.TAG, "TLC WA wasn't detected at the first instance")
            # Use the txlen as offset to inject error from last written offset            
            offset = 2 * self.txlen 
            errorMB = self.primaryMBWritten
            errorMBOffset = self.primaryMBOffsetWritten + offset
            
            # If errorMBOffset is less than TLC MB size, perform error injection. Else skip EI for this instance, will be injected later.
            if errorMBOffset < self.fwConfigObj.mlcMBSize:
                self.WAinjector(errorMB, errorMBOffset)
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))
            
            #self.AddressBeforeWAHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            #self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before WA Detection :',self.AddressBeforeWAHandling)
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=10240, txLenThreshold=None)
                
            if(not WriteAbortDetected):
                self.logger.Info(self.globalVarsObj.TAG, "TLC WA wasn't detected at the second instance")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "TLC WA wasn't detected"
                           
        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            
        
