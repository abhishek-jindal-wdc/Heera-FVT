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
import Lib.FWStructs.FWObjectWrapper as fwWrap

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
        self.globalVarsObj = GlobalVars.GlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba        
        self.HistoryObj = History.EpicCallbacks()
        
        self.wayPointDict = {
            "WP_PS_PF_DETECTED"                 : [self.WP_PS_PF_DETECTED]                    
        }                
        self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)        
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        

        self.ResetVariables()


    def WP_PS_PF_DETECTED(self,eventKey,args, pid):
        self.PFdetected = True

    def PFinjector(self,VBA, blocktype = 0):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1, blockType=blocktype)    
        VBA |= 32768
        VBA = VBA >> 2 << 2
        if(blocktype):
            #self.sctputilsobj.ErrorInjection(binType="RandomTLCPF")
            self.sctputilsobj.ErrorInjection(subOpcode=0, configType="singleError", operationType="Prog", addrType="VBA", addr=VBA, nsid=1, pattern="1WL", dataBuffer=None, binType=None, ErrLog=1, MBrevive=1, JBrevive=1, SurvivePC=1, isE2E=0, slot1=[0,0,0,0])
            
        else:
            self.sctputilsobj.ErrorInjection(subOpcode=0, configType="singleError", operationType="Prog", addrType="VBA", addr=VBA, nsid=1, pattern="1WL", dataBuffer=None, binType=None, ErrLog=1, MBrevive=1, JBrevive=1, SurvivePC=1, isE2E=0, slot1=[0,0,0,0])
        self.logger.Info(self.globalVarsObj.TAG, 'PF is injected to {}'.format(str(physical_address)))


    def ResetVariables(self):
        self.writtendata = []
        self.PFdetected = False
        self.RelinkingHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterPFHandling = None
        self.AddressBeforePFHandling = None
        self.SLCvbaWritten = []
        self.SLCjbWritten = []
        self.TLCvbaWritten = []
        self.TLCjbWritten = []   
        self.BlockAddedToPartialList = -1
        self.XORrecoveryStarted = False
        self.ParityRebuildStarted = False


    def GetLastWrittenAddress(self):
        LBA, tlen = self.HistoryObj.HistoryObj.GlobalWriteData[-1]
        #LBA = LBA + tlen - 1
        BLOCKDICT  = self.sctputilsobj.LBA2VBA(LBA, returnDict= True)
        PBA =  self.sctputilsobj.TranslateVbaToDeVbaAndPba(BLOCKDICT['vba'], 1, blockType=BLOCKDICT['blockType'])
        PBA['VBA'] = BLOCKDICT['vba']
        return PBA        

    def PFHandlerSLC(self, Blockstate, **kwargs):

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

            #Trigger Host Writes
            #Pre PF write
            #########################
            #self.writtendata = writeTotriggerHostAccumulation()
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=10000, txLenThreshold=None)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
            self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762   

            # Write a random number of JB

            ########################
            #temp address
            temp_address = self.GetLastWrittenAddress()
            if(temp_address['wordline'] >= 95):
                self.sctputilsobj.changeModeToSLC()
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()

            VBAtowhichErrorwasinjected = self.GetLastWrittenAddress()['VBA']  + 32
            self.PFinjector(VBAtowhichErrorwasinjected)
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
            self.AddressBeforePFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection : {}'.format(str(self.AddressBeforePFHandling)))

        #########################
        #PF detection Write
        self.ParityRebuildStarted = False
        #To accomodate rebuild due to mode switch/UGSD
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=10000, txLenThreshold=None)
        self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762   
        ########################


        self.AddressAfterPFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
        self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))        
        self.logger.Info(self.globalVarsObj.TAG, 'Physical Address After PF Detection : {}'.format(str(self.AddressAfterPFHandling)))
        self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection : {}'.format(str(self.AddressBeforePFHandling)))

        if(self.AddressAfterPFHandling == self.AddressBeforePFHandling):
            self.logger.Info(self.globalVarsObj.TAG, "New Block wasnt allocated")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            return "New Block wasnt allocated"             


        self.logger.Info(self.globalVarsObj.TAG, "############ Host SLC handling SUCCESSFULL###############")
        self.ResetVariables()
        return True        


    def PFHandlerTLC(self, Blockstate, **kwargs):
        startLba = 0
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
            if('ModeAfterSwitch' in kwargs.keys()):
                if(kwargs['ModeAfterSwitch'] != 'Operational'):
                    if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                        self.SDutilsObj.performShutdown(operation='GSD')
                    elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                        self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                    elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                        self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="ABORT") 
                    else:
                        self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")

            #Trigger Host Writes
            #########################
            self.sctputilsobj.SetMvpThreshold(-10,-15)
            self.TLCvbaWritten = []
            while(self.TLCvbaWritten == []):            
                kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
                if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    self.globalVarsObj.ccmObj.DoFlushCache()

            ########################            


        if('ErrorVBA' not in kwargs.keys()):

            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()
            VBAtowhichErrorwasinjected = self.TLCvbaWritten[-1] + 48 
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.PFinjector(self.VBAtowhichErrorwasinjected, blocktype= 1)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))
            self.AddressBeforePFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection : {}'.format(str(self.AddressBeforePFHandling)))



        #########################
        self.ParityRebuildStarted = False
        self.TLCvbaWritten = []
        while(self.TLCvbaWritten == []):            
            kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=1024 * 10 +1000, txLenThreshold=None)
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()        
        ######################## 

        self.stats = self.sctputilsobj.GetErrorHandlingStatistics()
        self.sctpParsedObj = fwWrap.FWDiagCustomObject(self.stats, "EH_ErrorCounterXML_s").EH_ErrorCounterXML_s.PS0.__dict__

        if(not self.PFdetected):
            self.logger.Info(self.globalVarsObj.TAG, "PF wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "PF wasn't detected"   

        if(self.ParityRebuildStarted):
            self.logger.Info(self.globalVarsObj.TAG, "Parity Rebuild Triggered")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "Parity Rebuild Triggered"        

        if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            if(not self.XORrecoveryStarted):
                self.logger.Info(self.globalVarsObj.TAG, "XOR recovery not Triggered")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "XOR recovery not Triggered"            
        else:
            if(self.XORrecoveryStarted):
                self.logger.Info(self.globalVarsObj.TAG, "XOR recovery Triggered")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.DeregisterAllWaypoint()
                return "XOR recovery Triggered"            


        if(self.vtfContainer.getActiveProtocol() != "NVMe_OF_SDPCIe" and self.BlockAddedToPartialList == self.TLCjbWritten[-1]):
            self.logger.Info(self.globalVarsObj.TAG, "Block wasnt added to Partial list")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "Block wasnt added to Partial list"        

        self.AddressAfterPFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1, 1)
        self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected : {}'.format(str(self.VBAtowhichErrorwasinjected)))        
        self.logger.Info(self.globalVarsObj.TAG, 'Physical Address After PF Detection : {}'.format(str(self.AddressAfterPFHandling)))
        self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection : {}'.format(str(self.AddressBeforePFHandling)))

        if(self.AddressAfterPFHandling == self.AddressBeforePFHandling):
            self.logger.Info(self.globalVarsObj.TAG, "New Block wasnt allocated")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return "New Block wasnt allocated"             


        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC PF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            

