import Constants
import SCSIGlobalVars
import WaypointReg
import CMDP_History as History
#import EIMediator
import AddressTypes
import SctpUtils  
import FwConfig as FwConfig

class EFhandler:

    __staticEFObj = None

    ##
    # @brief A method to create a singleton object of LOG EF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not EFhandler.__staticEFObj:
            EFhandler.__staticEFObj = super(EFhandler,cls).__new__(cls, *args, **kwargs)

        return EFhandler.__staticEFObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
        self.ccmObj = self.globalVarsObj.ccmObj
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livet = self.vtfContainer._livet
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba
        self.HistoryObj = History.EpicCallbacks()
        self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)
        #self.eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
        self.globalVarsObj.eiObj.RegisterEraseFailureCallback(self.EraseFailureCallback) 
        self.globalVarsObj.eiObj.RegisterEraseAbortCallback(self.EraseAbortCallback) 
        self.globalVarsObj.eiObj.RegisterPostEraseAbortCallback(self.PostEraseAbortCallback) 
        self.globalVarsObj.eiObj.RegisterPreEraseAbortCallback(self.PreEraseAbortCallback) 
        self.__numberOfDies = self.__fwConfigObj.diesPerChip
        self.__numberOfFIMs = 2
        self.__numberOfMetaDies = 4
        self.__numberOfStrings = self.__fwConfigObj.stringsPerBlock
        self.__maxLba = self.globalVarsObj.maxLba
        self.__sectorsInAPhyPage = self.globalVarsObj.lbasInPhyPage
        self.__numberOfWordlines = self.__fwConfigObj.wordLinesPerPhysicalBlock_BiCS
        self.__pagesInABlock = self.__numberOfWordlines * 4
        self.__mlcLevel = 3
        self.__planesInADie = self.__fwConfigObj.planesPerDie
        self.__chipCount = self.__fwConfigObj.numChips
        self.__sectorsPerSLCJB   = self.__sectorsInAPhyPage * self.__numberOfWordlines * self.__numberOfStrings * self.__planesInADie * self.__numberOfDies * self.__chipCount 
        self.__sectorsPerTLCJB   = self.__sectorsPerSLCJB * self.__mlcLevel # MLC Level
        self.sctpUtilsObj   = SctpUtils.SctpUtils() 

        if self.vtfContainer.isModel is True:
            self.livet = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
            self.wayPointDict = {
                    #"WP_FTL_OBM_JUMBO_BLOCK_ALLOC"     : [self.WP_FTL_OBM_JUMBO_BLOCK_ALLOC_Callback],
                    #"WP_PS_BBM_PH_BLOCK_RELINK"        : [self.WP_PS_BBM_PH_BLOCK_RELINK_Callback],
                    #"WP_PS_EF_DETECTED"                : [self.WP_PS_EF_DETECTED_Callback],
                    #"WP_PS_EH_FIM_ISR"                 : [self.WP_PS_EH_FIM_ISR_Callback],
                    #"WP_FTL_RLC_RLC_START"             : [self.WP_FTL_RLC_RLC_START_Callback] 
                    "LL_ERASE_METABLOCK_COMPLETE"        : [],
                    "LL_ERASE_METABLOCK_START"           : [self.OnLLEraseMetaBlockStart],
                    "FBL_BEFORE_ERASE_OF_ALLOCATED_BLOCK"    : [self.OnFblBeforeEraseOfAllocatedBlock],  
                    "BLM_GROWN_BAD_BLOCK_ADDED" : [self.OnBLMGrownBadBlockAdded],
                    "DLM_RELINKED_METABLOCK_FORMED" : [self.DLMRelinkedMBFormed],
                    "UM_READ"                    : [],
                    "UM_WRITE"                   : [],                    
                    "UM_BLOCK_ALLOCATION" : [],
                    "DLM_GROWN_BAD_BLOCK_ADDED" : [],
                    "DLM_RELINKED_METABLOCK_FORMED" : [],
                    "BLM_SET_GROWN_DEFECT" : [],
                }              

            self.WaypointRegObj.RegisterWP(self.wayPointDict)        

        self.SetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.globalVarsObj.eiObj.ErrorHandlerFunction)         
        return    

    def SetVariables(self):
        self.isErrorDetected = False
        self.EraseAbortDetected = False 
        self.PostEraseAbortDetected = False
        self.PreEraseAbortDetected = False
        self.isErrorInjected = False
        self.__DLMRelinkedOccured=False
        self.isNewMBErasedAfterError = False
        self.isRelinkingTriggered = False
        self.isRlcTriggered = False        
        #FlashAddress = (Die, Plane, Block, Wordline, String, Bit, Sector offset)
        self.errorInjectedFlashAddress = dict()
        self.errorDetectedFlashAddress = dict()
        self.__listOfGBBs = []
        # Wait for a random number of SLC blocks to be allocated before injecting EF
        self.jumboBlocksToAllocateBeforeEF = self.globalVarsObj.randomObj.randint(0, 15)
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'Will wait for %d more JBs to be erased before applying error'%(self.jumboBlocksToAllocateBeforeEF))
        self.livet = self.vtfContainer._livet
        #self.numberOfPlanes
        #self.CalculateSizeofJB()
        self.EFInjected = False
        self.EFDetected = False
        self.EAInjected = False 
        self.EADetected = False
        self.InjectErrorOnPrimary = False
        self.InjectErrorOnSecondary = False        
        return

    def ResetVariables(self):
        self.EFInjected = False
        self.EAInjected = False
        self.isErrorInjected = False
        self.isNewMBErasedAfterError = False
        self.isRelinkingTriggered = False
        self.__DLMRelinkedOccured=False
        self.isRlcTriggered = False
        self.errorInjectedFlashAddress.clear()
        self.errorDetectedFlashAddress.clear()
        self.jumboBlocksToAllocateBeforeEF = None
        self.InjectErrorOnPrimary = False
        self.InjectErrorOnSecondary = False
        return    

    def InjectErrorFromWP(self, MB):    
        phyAddrList = self.livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(MB, 0)
        # Randomly pick physical block to inject error
        addrIndex = self.globalVarsObj.randomObj.randint(0, len(phyAddrList)-1)
        self.phyAddr = AddressTypes.PhysicalAddress()
        self.phyAddr.chip = phyAddrList[addrIndex][0]
        self.phyAddr.die = phyAddrList[addrIndex][1]
        self.phyAddr.plane = phyAddrList[addrIndex][2]
        self.phyAddr.block = phyAddrList[addrIndex][3]
        
        errorType = self.globalVarsObj.randomObj.choice(["EF", "EA"])
        if errorType == "EF":
            self.globalVarsObj.eiObj.InjectEraseFailureError(errorPhyAddress=self.phyAddr)
            self.EFInjected = True
        if errorType == "EA":
            eaType = self.globalVarsObj.randomObj.choice(["erab", "prea", "poea"])
            self.globalVarsObj.eiObj.InjectEraseAbortError(errorType=eaType, errorPhyAddress=self.phyAddr)
            self.EAInjected = True
        self.isErrorInjected = True
        return

    def OnFblBeforeEraseOfAllocatedBlock(self, args):
        """
        "Bank", "MBAddr", "BlockType", "Plane"
        """
        if self.InjectErrorOnSecondary and args["BlockType"] == 0:
            self.InjectErrorFromWP(args["MBAddr"])
            self.InjectErrorOnSecondary = False
            
        if self.InjectErrorOnPrimary and args["BlockType"] == 1:
            self.InjectErrorFromWP(args["MBAddr"])
            self.InjectErrorOnPrimary = False            
            
        return    


    def DLMRelinkedMBFormed(self , args):
        self.__DLMRelinkedOccured=True
        RelinkBlockFormed = args[1]
        dynamicMBList.append(RelinkBlockFormed)
        
    def OnBLMGrownBadBlockAdded (self, args):
        # Bank, MB        
        self.__listOfGBBs.append(args['MB'])
        return        
    

    def WP_PS_BBM_PH_BLOCK_RELINK_Callback(self, eventKeys, args, processorID):
        #6,md,blkType,blk,phyPlNum,pRelinkedDeVBA->bits.phyBlock,recycleBadBlkFlag
        #FlashAddress = (Die, Plane, Block, Wordline, String, Bit, Sector offset)
        if self.isErrorInjected and self.isErrorDetected:
            self.errorDetectedFlashAddress['die'] = args[0]
            self.errorDetectedFlashAddress['phyPlane'] = args[3]
            self.errorDetectedFlashAddress['block'] = args[2] 
            self.isRelinkingTriggered = True
            self.logger.Info(self.globalVarsObj.TAG, "newly relinked block number = %d"%(args[4]))
        # Add the block to history
        self.HistoryObj.HistoryObj.BadBlockList.append([args[4], args[3], args[0]])
        return

    def EraseFailureCallback(self, package, addr):
        #3, pPSRequest->reqGeneric.VBA.PS_flavor3.MB, pPSRequest->reqGeneric.dw0.split.blkType, pPSRequest->reqGeneric.VBA.PS_flavor3.MD
        if self.EFInjected:
            self.EFDetected = True
            return
        
    def EraseAbortCallback(self, package, addr):
        #3, pPSRequest->reqGeneric.VBA.PS_flavor3.MB, pPSRequest->reqGeneric.dw0.split.blkType, pPSRequest->reqGeneric.VBA.PS_flavor3.MD
        if self.EAInjected:
            self.globalVarsObj.waOccured =True
            self.EADetected = True
            return  
        
    def PreEraseAbortCallback(self, package, addr):
        #3, pPSRequest->reqGeneric.VBA.PS_flavor3.MB, pPSRequest->reqGeneric.dw0.split.blkType, pPSRequest->reqGeneric.VBA.PS_flavor3.MD
        if self.EAInjected:
            self.globalVarsObj.waOccured =True
            self.EADetected = True
            return         

    def PostEraseAbortCallback(self, package, addr):
        #3, pPSRequest->reqGeneric.VBA.PS_flavor3.MB, pPSRequest->reqGeneric.dw0.split.blkType, pPSRequest->reqGeneric.VBA.PS_flavor3.MD
        if self.EAInjected:
            self.globalVarsObj.waOccured =True
            self.EADetected = True
            return  
                
                
    def WP_FTL_OBM_JUMBO_BLOCK_ALLOC_Callback(self, eventKeys, args, processorID):
        #5, jumboBlockId, partition, openBlock->policy.validFMUsSize, openBlockType, prtAvgPec
        # check how many times this WP is hit
        hits = self.WaypointRegObj.GetWPCounter('WP_FTL_OBM_JUMBO_BLOCK_ALLOC')
        # Livet API to convert JB to constituent flash address.
        # Note: The API originally used to convert MB to flashaddress, but has been modified for SDExpress to convert JB to flashaddress
        constituentFlashAddress = self.globalVarsObj.vtfContainer._livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(args[0], 0)
        # the pba will have (num_of_fims * num_of_dies * num_of_planes) blocks, choose randomly  
        randomlyChosenPba = self.globalVarsObj.randomObj.choice(constituentFlashAddress)
        if not self.isErrorInjected and self.jumboBlocksToAllocateBeforeEF == hits:
            self.InjectErrorFromWP(randomlyChosenPba)
        return

    def WP_PS_EH_FIM_ISR_Callback(self, eventKeys, args, processorID):
        #8, tlc_fa.bits.fim_low, tlc_fa.bits.dieInFIM, deVBA0.bits.phyBlock, deVBA1.bits.phyBlock, tlc_fa.bits.wordLine, tlc_fa.bits.stringNo, tlc_fa.bits.tlcPage, errInfo.readStatus
        # fim number, die in fim, phy block in plane 0, phy block in plane 1, phy WL, string, page, check status from NAND
        return

    def OnLLEraseMetaBlockStart(self, args):
        """
        "MB_Num","MemoryAccess"
        """
        return
    
    def EFhandlerSLC(self, Blockstate, **kwargs):
        try:
            self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
        except:
            pass

        self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST SLC EF HANDLER *************')

        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
        else:
            startLba = 0        
        
        # For SLC error injection, set inject error on secondary flag to True
        self.InjectErrorOnSecondary = True
        # Keep writing on the premise that blocks will be allocated, hence the JB_ALLOC WP will be hit
        while not self.isErrorInjected:
            self.ccmObj.Write(startLba=startLba, txLen=0x400)
            txLen=0x400
            startLba = startLba+txLen+8
            
        # Once the error is injected, Write a maximum of 1JB
        # This is because the error is injected on any one of the physical blocks of the JB, so the
        # error is not detected as soon as we inject it
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=self.__sectorsPerSLCJB, txLenThreshold=None)

        if(not self.EFDetected):
            if(self.EFInjected):
                self.logger.Info(self.globalVarsObj.TAG, "EF was injected but not detected")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
                return "EF was injected but not detected"
            
        if(not self.EADetected):
            if(self.EAInjected):
                self.logger.Info(self.globalVarsObj.TAG, "EA was injected but not detected")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
                return "EA was injected but not detected"            

        #if(not self.__DLMRelinkedOccured):
            #self.logger.Info(self.globalVarsObj.TAG, "Relinking didnt Happen")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
            #return "Relinking didnt Happen"
        #else:
            #if self.errorDetectedFlashAddress['die'] != self.errorInjectedFlashAddress['die']:
                #message = 'EF Injected on Die=%d, but detected on %d'%(self.errorInjectedFlashAddress['die'], self.errorDetectedFlashAddress['die'])
                #self.logger.Info(self.globalVarsObj.TAG, message)
                #return message
            #if self.errorDetectedFlashAddress['block'] != self.errorInjectedFlashAddress['block']:
                #message = 'EF Injected on Block=%d, but detected on %d'%(self.errorInjectedFlashAddress['block'], self.errorDetectedFlashAddress['block'])
                #self.logger.Info(self.globalVarsObj.TAG, message)
                #return message
            #errorInjectedPhyPlNum = (self.errorInjectedFlashAddress['fim'] * self.psConstants.PLANES_IN_PHYSICAL_BLK + self.errorInjectedFlashAddress['plane'])
            #if self.errorDetectedFlashAddress['phyPlane'] != errorInjectedPhyPlNum:
                #message = 'EF Injected on Physical plane=%d, but detected on %d'%(errorInjectedPhyPlNum, self.errorDetectedFlashAddress['phyPlane'])
                #self.logger.Info(self.globalVarsObj.TAG, message)
                #return message

        self.logger.Info(self.globalVarsObj.TAG, "############ Host SLC handling SUCCESSFULL###############")
        self.ResetVariables()
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
        return True        


    def EFhandlerTLC(self, Blockstate, **kwargs):
        try:
            self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
            #self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
        except:
            pass

        self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING HOST TLC EF HANDLER *************')

        if ('startLba' in kwargs.keys()):
            startLba = kwargs['startLba']
        else:
            startLba = 0

        self.InjectErrorOnPrimary = True
        self.__sectorsPerTLCMB   = self.__fwConfigObj.mlcMBSize
        self.sctpUtilsObj.SetMaxHybridBlockCount(0)
        # Keep writing till GC is triggered
        while not self.isErrorInjected:
            self.ccmObj.Write(startLba=startLba, txLen=0x400)
            txLen=0x400
            startLba = startLba+txLen
        # Once the error is injected, Write a maximum of 1JB
        # This is because the error is injected on any one of the physical blocks of the JB, so the
        # error is not detected as soon as we inject it
        kwargs['EINobj'].DoMeasuredSequentialWrite(numberOfWrites=None, sectorsToBeWritten=self.__sectorsPerTLCJB, txLenThreshold=None)        

        #if('ModeAfterSwitch' in kwargs.keys()):
            #if(kwargs['ModeAfterSwitch'] != 'Operational'):
                #if(kwargs['ModeAfterSwitch'] == 'PCIe' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    #self.sdUtilsObj.performShutdown(operation='GSD')
                #elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "SD_OF_SDPCIe"):
                    #self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD") 
                #elif(kwargs['ModeAfterSwitch'] == 'SD' and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                    #self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="GSD") 
                #else:
                    #self.globalVarsObj.vtfContainer.switchProtocol(powerCycleType="UGSD")

        if(not self.EFDetected):
            if(self.EFInjected):
                self.logger.Info(self.globalVarsObj.TAG, "EF was injected but not detected")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
                return "EF was injected but not detected"
            
        if(not self.EADetected):
            if(self.EAInjected):
                self.logger.Info(self.globalVarsObj.TAG, "EA was injected but not detected")
                self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
                self.ResetVariables()
                self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
                return "EA was injected but not detected" 

 
        #if(not self.__DLMRelinkedOccured):
            #self.logger.Info(self.globalVarsObj.TAG, "Relinking didnt Happen")
            #self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            #self.ResetVariables()
            #self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
            #return "Relinking didnt Happen"
        #else:
            #if self.errorDetectedFlashAddress['die'] != self.errorInjectedFlashAddress['die']:
                #message = 'EF Injected on Die=%d, but detected on %d'%(self.errorInjectedFlashAddress['die'], self.errorDetectedFlashAddress['die'])
                #self.logger.Info(self.globalVarsObj.TAG, message)
                #return message
            #if self.errorDetectedFlashAddress['block'] != self.errorInjectedFlashAddress['block']:
                #message = 'EF Injected on Block=%d, but detected on %d'%(self.errorInjectedFlashAddress['block'], self.errorDetectedFlashAddress['block'])
                #self.logger.Info(self.globalVarsObj.TAG, message)
                #return message
            #errorInjectedPhyPlNum = (self.errorInjectedFlashAddress['fim'] * self.psConstants.PLANES_IN_PHYSICAL_BLK + self.errorInjectedFlashAddress['plane'])
            #if self.errorDetectedFlashAddress['phyPlane'] != errorInjectedPhyPlNum:
                #message = 'EF Injected on Physical plane=%d, but detected on %d'%(errorInjectedPhyPlNum, self.errorDetectedFlashAddress['phyPlane'])
                #self.logger.Info(self.globalVarsObj.TAG, message)
                #return message


        self.logger.Info(self.globalVarsObj.TAG, "############ Host TLC EF handling SUCCESSFULL###############")
        self.ResetVariables()
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
        return True