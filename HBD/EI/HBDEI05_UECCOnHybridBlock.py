#---------------------------------------------------------------------------------
#* MODULE     : HBD16_HybridOpenBlockPF
#* FUNCTION   : This test injects UECC failures hybrid blocks and checks for SLC
               #compaction to trigger
#* PROGRAMMER : Aarshiya Khandelwal
#* DATE(ORG)  : 12 Dec'2019
#* REMARKS    : This assumes that the hardware and framework have been set up
#* COPYRIGHT  : Copyright (C) 2019 SanDisk Corporation 
#*----------------------------------------------------------------------------------*
#*  Revision History
#*----------------------------------------------------------------------------------*
#* Sl.No:  Date  : Description                                 - Programmer
#*----------------------------------------------------------------------------------*
#*   1: 02/12/2019 : Programmed and Release for script testing - Aarshiya Khandelwal
#************************************************************************************

import Protocol.SCSI.Basic.TestCase as TestCase
import SCSIGlobalVars
import WaypointReg
import FwConfig as FwConfig
import Utils as Utils
import os

import Extensions.CVFImports as pyWrap
#import FeatureTests.ITGC.ITGC_Lib as ITGC_Lib
import ValidationLib.AddressTypes as AddressTypes
import SctpUtils
import ValidationLib.EIMediator as EIMediator
import FwConfig as FwConfig
import Core.ValidationError         as ValidationError
from Constants import StreamTypes as ST

class HBDEI05_UECCOnHybridBlock(TestCase.TestCase):
    
    def setUp(self):
        TestCase.TestCase.setUp(self)

        self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
        self.__ccmObj         = self.globalVarsObj.ccmObj
        self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
        self.utilsObj       = Utils.Utils()
        self.sctpUtilsObj = SctpUtils.SctpUtils()

        self.wayPointDict = {
            "BLM_GROWN_BAD_BLOCK_ADDED" : [self.OnBlmGrownBlockAdded],
            "DLM_GROWN_BAD_BLOCK_ADDED" : [self.OnDlmGrownBlockAdded],
            "BLM_SET_GROWN_DEFECT"      : [],
            "EPWR_COMPLETE" : [],
            "EPWR_START" : [self.OnEpwrStart],
            "MB_ADDED_TO_CLOSED_HYBRID_LIST" : [self.OnMBAddedtoClosedHBDList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST" : [self.OnMBReleasedfromClosedHBDList],
            "HYBRID_BLOCK_ADDED" : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED" : [self.OnHybridBlockRemoved],            
            "READ_ONLY_MODE" : [self.OnReadOnlyMode],
            "SLC_COMPACTION_DATA_TRANSFER_BEGIN" : [self.OnSlcCompactionDataTransferBegin],
            "MLC_COMPACTION_DATA_TRANSFER_BEGIN" : [self.OnSlcCompactionDataTransferBegin],
            "UECC_DETECTED" : [],
            "UM_WRITE" : [self.OnUmWrite],
	    "HYBRID_BLOCK_EVICTION_COMPLETE" : [self.OnHybridBlockEvictionComplete],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict)
                
        self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)

        self.__livet = self.vtfContainer._livet
        self.__livetFlash = self.__livet.GetFlash()             
        
        self.__logger = self.logger
        
        self.__randomObj = self.globalVarsObj.randomObj
        self.__eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
        
        self.diesPerChip = self.__fwConfigObj.diesPerChip 
        self.lgsInCard = self.__fwConfigObj.lgsInCard
        self.maxLba = self.__fwConfigObj.maxLba
        self.metaPageSize = self.__fwConfigObj.metaPageSize
        self.sectorsPerLg = self.__fwConfigObj.sectorsPerLg   
        self.sectorsPerSlcBlock = self.__fwConfigObj.sectorsPerSlcBlock        
        self.slcMBSize = self.__fwConfigObj.slcMBSize
        
        self.RegisterWaypoints()
        self.numHybridBlocks = 0
        self.isHybridBlock = False
        self.injectError = False
        self.injectMultipleFails = False
	self.HybridEvictionComplete = False
	self.__STMerror=self.__eiObj.STMerror
	
	self.maxSTM=1920
        
        self.slcCompactionTriggeredlbas = []
        self.destMbList=[]
        self.currentHybridBlock = 0
        self.currentStream    = 0
        self.hybridBlocksList = []
        self.__blocksReleased = []
        self.__errorInjectedBlocks = []
        self.__multipleUECCInjectedBlocks = []
	self.MMPList = list(range(0, self.__fwConfigObj.numberOfMetaPlane))	
        #self.SLCBlocksCount = ITGC_Lib.GetITGCfile21params( "ITGC_FIFOsize")
        delay_params = 11
        self.wl=0
        self.__listOfWordLines={}
        self.delay=self.__randomObj.randint(30*delay_params,40*delay_params)               
        self.ThresholdMaxHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.ExpectedHybridBlockCount = 1
        self.ClosedHybridBlockCount = 0
        self.WaypointReturnedHybridBlockCount = 0   
	self.WaypointReturnedClosedHybridBlockCount=0

        path = os.environ["FVTPATH"]
        
    def tearDown(self):
        self.__ccmObj.DataVerify()
        if self.globalVarsObj.manualDoorbellMode:
            tempAvailableSQList = list(set(self.__ccmObj.usedSQIDs))

            for tempSqID in tempAvailableSQList:
                self.__ccmObj.RingDoorBell(tempSqID)
            status = self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762

            if status == False:
                raise ValidationError.CVFGenericExceptions(self.variationName, 'WaitForCompletion Failed')
        self.utilsObj.DrawGraph(self.variationName)
        self.utilsObj.CalculateStatistics()
        super(type(self), self).tearDown()

    def testHBDEI05_UECCOnHybridBlock(self):
        self.__ccmObj.SetLbaTracker()
        Lg = self.globalVarsObj.randomObj.randint(0, self.__fwConfigObj.lgsInCard/2)
        startLba = self.sectorsPerLg*Lg
        transferLength = 0x100
        OneGBLen = 0x200000
        sectorsIn5GB = OneGBLen * 5
        startAddress = startLba
        self.lbaToInjectError = self.__randomObj.sample(range(1, self.ThresholdMaxHybridBlocks-20), 5)
        self.maxEPWRFailure = self.__randomObj.sample(range(1, self.ThresholdMaxHybridBlocks-20), 5)
       
        
        self.__logger.Info(self.globalVarsObj.TAG, "...Writing 1 GB data sequentially...")
        self.__logger.Info(self.globalVarsObj.TAG, "-"*100)        
        
        while (startLba < (startAddress + sectorsIn5GB) and len(self.MMPList)):
	    if startLba + transferLength > self.__fwConfigObj.maxLba:
		startLba = 0x0		
            self.__ccmObj.Write(startLba, transferLength)
            startLba += transferLength 
            
            # If hybridblock count in randomly generated range, inject error(uecc)
            if self.numHybridBlocks in self.lbaToInjectError:
                self.injectError = True
                
            if self.numHybridBlocks in self.maxEPWRFailure:
                self.injectMultipleFails = True
        
                
            # insert delay, after half hybrid blocks have been created
            if self.numHybridBlocks == self.ThresholdMaxHybridBlocks/2:
                self.__logger.Info(self.globalVarsObj.TAG, "******************************************************")
                self.__logger.Info(self.globalVarsObj.TAG, "\t\tInserting delay for %s millisec" % self.delay)
                self.__logger.Info(self.globalVarsObj.TAG, "******************************************************")                    
                self.utilsObj.InsertDelay(self.delay)
                
                
        self.__logger.Info(self.globalVarsObj.TAG, "...Completed writing 5 GB data...")
        self.__logger.Info(self.globalVarsObj.TAG, "-"*100)   
        
        #self.utilsObj.InsertDelay(self.delay)
        self.sctpUtilsObj.ForceGC()
        self.sctpUtilsObj.ForceHybridEviction()
        
        # Write 5 Hybrid Blocks
        self.logger.Info("", "Write 5 hybrid blocks worth data to trigger Hybrid Eviction")
        sectorsToWrite = self.__fwConfigObj.slcMBSize * 20
        sectorsWritten = 0
        while not self.HybridEvictionComplete:

            self.__ccmObj.Write(startLba, transferLength)
            startLba += transferLength
            sectorsWritten += transferLength
        
        # check if compaction got triggered for all lbas where UECC STM was injected
        self.logger.Info("", "-"*100)
        self.logger.Info("", "List of UECC Injected blocks: %s" % str(self.__errorInjectedBlocks))
        self.logger.Info("", "List of Compaction Triggred blocks: %s" % str(self.slcCompactionTriggeredlbas))
        
        if len(self.slcCompactionTriggeredlbas) == 0:
            if len(self.__errorInjectedBlocks)==0:
                raise ValidationError.TestFailError("", "UECC Error not injected on a Single block")
            else:
                raise ValidationError.TestFailError("", "Compaction did not trigger on a single error injected block")
        else:        
            compactionNotTriggered = list(set(self.__errorInjectedBlocks) - set(self.slcCompactionTriggeredlbas))
            if compactionNotTriggered != []:
                raise ValidationError.TestFailError("", "Compaction not triggered for UECC injected blocks(s): %s" % compactionNotTriggered)
        
        self.logger.Info("", "List of max UECC injected blocks: %s" % str(self.__multipleUECCInjectedBlocks))
        self.logger.Info("", "List of Released blocks: %s" % str(self.__blocksReleased))
        self.logger.Info("", "-"*100)
        
        if len(self.__blocksReleased)==0:
            if len(self.__multipleUECCInjectedBlocks)==0:
                raise ValidationError.TestFailError("", "Max UECC Error not injected on a Single block")

        blocksReleased = list(set(self.__multipleUECCInjectedBlocks) - set(self.__blocksReleased))
        if blocksReleased != []:
            raise ValidationError.TestFailError("", "Block not released after injecting 4 UECCs: %s" % blocksReleased)
        
        #Perform one Hybrid block write for counter verification
        sectorsToWrite = self.__fwConfigObj.slcMBSize
        sectorsWritten = 0
        transferLength = 0x100
        while sectorsWritten < sectorsToWrite:
            self.__ccmObj.Write(startLba, transferLength)
            startLba += transferLength
            sectorsWritten += transferLength
        # Check if number of hybrid blocks added exceeds max limit of hybrid block
        if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxHybridBlocks:
            raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
                                                (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxHybridBlocks))
    
    
	# Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
	if self.ClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
	    raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
	                                                                                      (self.ClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))
            
          
        ## Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
        #if self.ExpectedHybridBlockCount != self.WaypointReturnedHybridBlockCount:
            #raise ValidationError.TestFailError("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
                                                #(self.ExpectedHybridBlockCount, self.WaypointReturnedHybridBlockCount))

        
    def RegisterWaypoints(self):
        #Register Firmware Waypoints required
        
        self.__eiObj.RegisterProgramFailureCallback(self.OnProgramFailure)
        
    def InjectMultipleUECC(self, errorLba):
	if errorLba not in self.destMbList and errorLba in self.hybridBlocksList and errorLba % self.__fwConfigObj.numberOfMetaPlane in self.MMPList:
	    self.__multipleUECCInjectedBlocks.append(errorLba)
	
        
        phyAddr = AddressTypes.PhysicalAddress()
        self.__logger.Info(self.globalVarsObj.TAG, "Injecting four UECCs in block: 0x%X" % errorLba)
        phyAddrList = self.__livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(errorLba,0)
        phyAddrIndex = self.__randomObj.randrange(0, len(phyAddrList))

        phyAddr.chip = phyAddrList[phyAddrIndex][0]
        phyAddr.die = phyAddrList[phyAddrIndex][1]
        phyAddr.plane = phyAddrList[phyAddrIndex][2]
        phyAddr.block = phyAddrList[phyAddrIndex][3]            
        phyAddr.mlcLevel = self.__randomObj.randrange(0,self.__fwConfigObj.mlcLevel)
        wordLines=[]
        if self.__listOfWordLines.has_key(errorLba):
            wl=self.__listOfWordLines[errorLba]
            
            wordLines = self.__randomObj.sample(range(wl+1,wl+10),4)
        else:
        # Inject 4 UECC in different wordlines, not within guardband
            wordLines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+8)) #no hardcoding
	    wordLines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2+10,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+18))
	    wordLines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2+20,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+28))
	    wordLines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2+30,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+38))
        
        
        for i in range(0, 4):
            phyAddr.wordLine = wordLines[i]
            #self.__eiObj.ApplySTM(errorPhyAddress=phyAddr, 
                                 #stmfile=self.fileName,  
                                 #isCalledFromWaypoint=True, 
                                 #isToBeAppliedToWordline=True)
            self.__eiObj.InjectUECCErrorWithSTM(errorPhyAddress=phyAddr, 
                                               isCalledFromWaypoint=True, 
                                               applyOnlyToEccPage=True, blktype='slc')
        self.injectMultipleFails = False
        if errorLba not in self.destMbList and errorLba in self.hybridBlocksList:
            self.__errorInjectedBlocks.append(errorLba)
	self.MMPList.remove(errorLba % self.__fwConfigObj.numberOfMetaPlane)    
	
	    
        
            
    def OnEpwrStart(self , args):
        """
        "Block", "Sector", "NumSectors", "MemoryAccess", "Requestor"
        """
         # check for UECC injected STMS 
	self.__STMerror=self.__eiObj.STMerror
	if self.__STMerror>=self.maxSTM:
	    
	    return True		
	#PHASED-EPWR for compaction destMB 
        if args["Block"] in self.destMbList:
	    #block-wordline MAP 
            if self.__listOfWordLines.has_key(args["Block"]):
		# incrementing 9 wordlines , EPWR is performed for  0x2400 sectors in every loop
                if self.wl+9>self.__fwConfigObj.wordLinesPerPhysicalBlock-10:
                    return True
                self.wl=self.wl+9
                self.__listOfWordLines[args["Block"]]=self.wl
        
            else:
                self.wl=0
                self.__listOfWordLines[args["Block"]]= self.wl
              
            if self.injectMultipleFails:
                self.InjectMultipleUECC(args["Block"])
            else:
                phyAddr = AddressTypes.PhysicalAddress()
                if self.injectError and args["Block"] not in self.__errorInjectedBlocks:
                    phyAddrList = self.__livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(args["Block"],0)
                    phyAddrIndex = self.__randomObj.randrange(0, len(phyAddrList))
        
                    phyAddr.chip = phyAddrList[phyAddrIndex][0]
                    phyAddr.die = phyAddrList[phyAddrIndex][1]
                    phyAddr.plane = phyAddrList[phyAddrIndex][2]
                    phyAddr.block = phyAddrList[phyAddrIndex][3]            
                    wl=self.__listOfWordLines[args["Block"]]
                    phyAddr.wordLine = self.__randomObj.randint(wl,wl+9)
                    self.__eiObj.InjectUECCErrorWithSTM(errorPhyAddress=phyAddr, 
                                                       isCalledFromWaypoint=True, blktype='slc')
        else:
            
            if self.injectMultipleFails:
                self.InjectMultipleUECC(args["Block"])
            else:
                phyAddr = AddressTypes.PhysicalAddress()
                if self.injectError and args["Block"] not in self.__errorInjectedBlocks:
                    phyAddrList = self.__livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(args["Block"],0)
                    phyAddrIndex = self.__randomObj.randrange(0, len(phyAddrList))
        
                    phyAddr.chip = phyAddrList[phyAddrIndex][0]
                    phyAddr.die = phyAddrList[phyAddrIndex][1]
                    phyAddr.plane = phyAddrList[phyAddrIndex][2]
                    phyAddr.block = phyAddrList[phyAddrIndex][3]            
                    
                    phyAddr.wordLine = self.__randomObj.randint(8,self.__fwConfigObj.wordLinesPerPhysicalBlock-10)
                    self.__eiObj.InjectUECCErrorWithSTM(errorPhyAddress=phyAddr, 
                                                       isCalledFromWaypoint=True, blktype='slc')
                        
            self.injectError = False
        
        
    def OnBlmGrownBlockAdded(self , args):
        """
        Args       : "Bank","MB"
        """
        self.__blocksReleased.append(args["MB"])
        return 0
        
    def OnDlmGrownBlockAdded(self , args):
        """
        Args       : "Bank", "MBAddr", "BlockType", "PhyBlock0", "PhyBlock1", "PhyBlock2","PhyBlock3",
						"PhyBlock4", "PhyBlock5", "PhyBlock6", "PhyBlock7"
        """
        if args["MBAddr"] not in self.__blocksReleased:
            self.__blocksReleased.append(args["MBAddr"])
        return 0
    
    #------------------------------------------------------------------------------------                  
    def OnMBAddedtoClosedHBDList(self, args):
        """
        MBAddress, ClosedHybridBlockCount
        """
        self.ClosedHybridBlockCount = self.ClosedHybridBlockCount + 1
	self.WaypointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"]
        return

    #------------------------------------------------------------------------------------
    def OnHybridBlockAdded(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount", "StreamID"
        """
        self.ExpectedHybridBlockCount += 1  
        self.numHybridBlocks += 1
        #self.metaBlockList.append(args["MBAddress"])
        self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
        self.hybridBlocksList.append(args["MBAddress"])
        return

    #------------------------------------------------------------------------------------
    def OnHybridBlockRemoved(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount"
        """
        self.ExpectedHybridBlockCount -= 1  
        self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
        return

    #------------------------------------------------------------------------------------
    def OnMBReleasedfromClosedHBDList(self, args):
        """
        "MBAddress", "ClosedHybridBlockCount"
        """
        self.ExpectedHybridBlockCount -= 1
        #self.metaBlockList.remove(args["MBAddress"])
        self.HybridBlockReleased = True
        self.ClosedHybridBlockCount = self.ClosedHybridBlockCount - 1   
        self.WaypointReturnedClosedHybridBlockCount=args["ClosedHybridBlockCount"]
        return 0
    
    def OnSlcCompactionDataTransferBegin(self , args):
        """
        Args       : "SrcMB", "DestMB","MBOffset", "DestAccessType", "NumberOfFragments"
        """
        if args['DestMB'] not in self.destMbList:
            self.destMbList.append(args['DestMB'])
            
        if args["SrcMB"] not in self.slcCompactionTriggeredlbas:
            self.slcCompactionTriggeredlbas.append(args["SrcMB"])
	    
    def OnHybridBlockEvictionComplete(self,args):
	self.HybridEvictionComplete = True
	
	return
        
    def OnUmWrite(self , args):
        """
        Args: "Bank","LG","LGOffset","transferLength","StreamType","StreamID","MB","MBOffset","primary","numSectorsToPrepad","numSectorsToPostpad","startWriteOffset"
        """
        
        self.currentStream = args["StreamType"]
        if args["MB"] in self.hybridBlocksList:
            self.isHybridBlock = True
            self.currentHybridBlock = args["MB"]
            
    def OnProgramFailure(self, package, addr):
        """
        Description:
        * Waypoint to indicate if program failure has occured.
        * chip = package, die = addr[0], plane = addr[1], block = addr[2], 
        * wordLine = addr[3], mlcLevel = addr[4], eccPage = addr[5]
        """
        return 0
    
    def OnReadOnlyMode(self , args):
        self.__logger.Info(self.globalVarsObj.TAG, "PF injected on %d LBAs: " % len(self.errorInjectedLbaList)) 
        #for lba in self.errorInjectedLbaList:
            #self.__logger.Info("0x%X" % lba) 
        
    def GetWordlineLbas(self,package,addr):
        """
        Description:
           * Gets the wordline lbas
        """
        self.errorAffectedLbaListTemp = []
        wordLineLbas = self.__livetFlash.GetWordlineLBAs(package,addr)
        startIndex = wordLineLbas[0] + 1
        #self.logger.Info("wordline lbas :: %s"%(list(wordLineLbas)))
        # Form a list with valid lba's
        for lba in range(startIndex,len(wordLineLbas)):
            if not wordLineLbas[lba] < 0:
                self.errorAffectedLbaListTemp.append(wordLineLbas[lba]) 

        