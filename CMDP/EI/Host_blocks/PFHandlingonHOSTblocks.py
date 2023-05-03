import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
#import EIMediator
import SctpUtils
import WaypointReg
import Extensions.CVFImports as pyWrap
import FwConfig
import EINCTD_Library
import CMDP_History as History

class PFhandler:

    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not PFhandler.__staticPFObj:
            PFhandler.__staticPFObj = super(PFhandler,cls).__new__(cls, *args, **kwargs)

        return PFhandler.__staticPFObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        #self.eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
        self.fwConfigObj = FwConfig.FwConfig(self.vtfContainer)
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba        
        self.HistoryObj = History.EpicCallbacks()
	self.einLibObj = EINCTD_Library.EINCTD_Library(self.vtfContainer)
	
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj, self.logger, self.globalVarsObj)
            if(self.HistoryObj.Verbose):
                self.wayPointDict = {
                    "DLM_RELINKED_METABLOCK_FORMED" : [], 
                    "UM_WRITE"           : [self.OnUMWrite],
                    #"MLC_COMPACTION_DATA_TRANSFER_BEGIN" : [], #GCC_GOING_TO_WRITE
                    #"SLC_COMPACTION_DATA_TRANSFER_BEGIN" : [],
                    #"GCC_SRC_SELECT"             : [],
                                                    #"LDPC_DECODE_SUCCESS"        : [],
                    #"GCC_GOING_TO_WRITE"         : [],
                    #"GCC_GOING_TO_READ"         : []
                }
            else:
                self.wayPointDict = {
                    "DLM_RELINKED_METABLOCK_FORMED" : [], 
                    "UM_WRITE"           : [self.OnUMWrite],
                    #"MLC_COMPACTION_DATA_TRANSFER_BEGIN" : [], #GCC_GOING_TO_WRITE
                    #"SLC_COMPACTION_DATA_TRANSFER_BEGIN" : [],
                    #"GCC_SRC_SELECT"             : [],
                                                    #"LDPC_DECODE_SUCCESS"        : [],
                    #"GCC_GOING_TO_WRITE"         : [],
                    #"GCC_GOING_TO_READ"         : []
                }               

            self.WaypointRegObj.RegisterWP(self.wayPointDict)
            self.livet = self.vtfContainer._livet
            self.livet.UnregisterLivetCallback(self.livet.lcFlashProgramFail)
            self.globalVarsObj.eiObj.RegisterProgramFailureCallback(self.OnProgramFailure)
        self.ResetVariables()



    def InjectErrorFromWP(self,vba,die,plane,block,wl,string,channel):
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramError ,errorPersistence,0,1,0,0)
        package = channel
        phyAddress=[die,plane,block,wl,string,0,0]            
        self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
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
        return

    def OnProgramFailure(self, package,addr):
        self.PFdetected = True
	self.einLibObj.errorAffectedLbaUECC.append([addr[2], addr[3]])     


    def PFinjector(self, MB, MBOffset):
        phyAddr =  self.globalVarsObj.eiObj.GetPhysicalAddress(MB, MBOffset)
        self.globalVarsObj.eiObj.InjectProgramFailureError(errorPhyAddress = phyAddr)
        return      

    def ResetVariables(self):
        self.writtendata = []
        self.txlen = None
        self.PFdetected = False
        self.RelinkingHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterPFHandling = None
        self.AddressBeforePFHandling = None
        self.BlockAddedToPartialList = -1
        self.XORrecoveryStarted = False
        self.ParityRebuildStarted = False
        self.PFInjected = False
        self.PFdetected = False
        self.RelinkingHappened = False
        self.secondaryMBWritten = None
        self.secondaryMBOffsetWritten = None
        self.primaryMBWritten = None
        self.primaryMBOffsetWritten = None        

    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)

    def PFHandlerSLC(self, Blockstate, **kwargs):
        try:
            self.DeregisterAllWaypoint()
        except:
            pass

        self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST SLC PF HANDLER *************')

        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 16

            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.PFinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforePFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection :',self.AddressBeforePFHandling)

        else:

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

            #Trigger Host Writes
            #Pre PF write
            #########################
            #self.writtendata = writeTotriggerHostAccumulation()
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)

            ########################
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
                self.PFinjector(errorMB, errorMBOffset)
                self.PFInjected = True            

        #########################
        #Perform few writes
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=20000, txLenThreshold=None)

        ########################

        if(not self.PFdetected):
            #self.secondaryMBWritten = None

            # Use the txlen as offset to inject error from last written offset            
            offset = 2 * self.txlen
            errorMB = self.secondaryMBWritten
            errorMBOffset = self.secondaryMBOffsetWritten + offset

            # If errorMBOffset is less than TLC MB size, perform error injection. 
            # Else skip EI for this instance, will be injected in next instance.
            if errorMBOffset < self.fwConfigObj.slcMBSize:
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))
                self.PFinjector(errorMB, errorMBOffset)
                self.PFInjected = True        

            # Perform writes to hit error location
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=20000, txLenThreshold=None)

            if(not self.PFdetected):
                self.logger.Info(self.globalVarsObj.TAG, "PF wasn't detected at the second instance")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "PF wasn't detected"

        #if(self.ParityRebuildStarted):
            #self.logger.Info(self.globalVarsObj.TAG, "Parity Rebuild Triggered")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.DeregisterAllWaypoint()
            #return "Parity Rebuild Triggered"        

        #if(self.XORrecoveryStarted):
            #self.logger.Info(self.globalVarsObj.TAG, "XOR recovery Triggered")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.DeregisterAllWaypoint()
            #return "XOR recovery Triggered"            

        #if(not self.RelinkingHappened):
            #self.logger.Info(self.globalVarsObj.TAG, "Relinink didnt Happen")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.DeregisterAllWaypoint()
            #return "Relinink didnt Happen"        


        #if(self.AddressAfterPFHandling == self.AddressBeforePFHandling):
            #self.logger.Info(self.globalVarsObj.TAG, "New Block wasnt allocated")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.DeregisterAllWaypoint()
            #return "New Block wasnt allocated"             


        self.logger.Info(self.globalVarsObj.TAG, "############ Host SLC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True        


    def PFHandlerTLC(self, Blockstate, **kwargs):
        startLba = 0
        try:
            self.DeregisterAllWaypoint()
        except:
            pass

        self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC PF HANDLER *************')

        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
        else:
            startLba = 0

        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 48

            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.PFinjector(self.VBAtowhichErrorwasinjected, blocktype= 1)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
            self.AddressBeforePFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection : {}'.format(str(self.AddressBeforePFHandling)))

        else:
           #Trigger Host Writes
            #########################
            self.primaryMBWritten = None
            while(self.primaryMBWritten == None):            
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)

            ########################            
            offset = 2 * self.txlen 
            errorMB = self.primaryMBWritten
            errorMBOffset = self.primaryMBOffsetWritten + offset
            
            # If errorMBOffset is less than TLC MB size, perform error injection. 
            # Else skip EI for this instance, will be injected in next instance.
            if errorMBOffset < self.fwConfigObj.mlcMBSize:
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))                
                self.PFinjector(errorMB, errorMBOffset)
                self.PFInjected = True
            
        # Perform writes to hit the injected error
        self.primaryMBWritten = None
        while(self.primaryMBWritten == None):            
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=10240, txLenThreshold=None)
        
        ######################## 

        if(not self.PFdetected):
            self.PFInjected = False
            self.logger.Info(self.globalVarsObj.TAG, "TLC PF wasn't detected at the first instance")
            # Use the txlen as offset to inject error from last written offset            
            offset = 2 * self.txlen 
            errorMB = self.primaryMBWritten
            errorMBOffset = self.primaryMBOffsetWritten + offset
            
            # If errorMBOffset is less than TLC MB size, perform error injection. Else skip EI for this instance, will be injected later.
            if errorMBOffset < self.fwConfigObj.mlcMBSize:
                self.PFinjector(errorMB, errorMBOffset)
                self.logger.Info(self.globalVarsObj.TAG, 'Injecting error at MB: 0x%X, MBOffset: 0x%X' % (errorMB, errorMBOffset))
            
            # Perform writes to hit error
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)

            if(not self.PFdetected):
                self.logger.Info(self.globalVarsObj.TAG, "PF wasn't detected at the second instance")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "PF wasn't detected"   

        #if(self.ParityRebuildStarted):
            #self.logger.Info(self.globalVarsObj.TAG, "Parity Rebuild Triggered")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.DeregisterAllWaypoint()
            #return "Parity Rebuild Triggered"        

        #if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            #if(not self.XORrecoveryStarted):
                #self.logger.Info(self.globalVarsObj.TAG, "XOR recovery not Triggered")
                #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                #self.ResetVariables()
                #self.DeregisterAllWaypoint()
                #return "XOR recovery not Triggered"            
        #else:
            #if(self.XORrecoveryStarted):
                #self.logger.Info(self.globalVarsObj.TAG, "XOR recovery Triggered")
                #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                #self.ResetVariables()
                #self.DeregisterAllWaypoint()
                #return "XOR recovery Triggered"            


        #if(self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe" and self.BlockAddedToPartialList == self.TLCjbWritten[-1]):
            #self.logger.Info(self.globalVarsObj.TAG, "Block wasnt added to Partial list")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.DeregisterAllWaypoint()
            #return "Block wasnt added to Partial list"                  


        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            

