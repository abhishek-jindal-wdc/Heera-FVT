#"""
#*********************************************************************************************
    # @file       : HBD06_HybridBlockCounterVerification.py
    # @brief      : The test is designed to check Hybrid Block Counter verification
    # @author     : Komala Nataraju
    # @date       : 30 APR 2020
    # @copyright  : Copyright (C) 2020 SanDisk Corporation
#*********************************************************************************************
#--------------------------------------------------------------------------------
# Updated for Testing on Heera CVF    -     Aarshiya Khandelwal   -   Oct 5 2020
#--------------------------------------------------------------------------------

import Protocol.SCSI.Basic.TestCase as TestCase
import SCSIGlobalVars
import WaypointReg
import FwConfig as FwConfig
import Constants
import AccessPatternLib
import SctpUtils  
import Utils                        as Utils                               
import Core.ValidationError         as ValidationError
import FileData
import AddressTypes
#FVT Imports goes here
import GlobalVars as GlobalVars
from Constants import GC as GCConstants 
from Constants import StreamTypes as ST

# @brief A class as a structure for HBD06_HybridBlockCounterVerification Test
# @details Test scope is to check Hybrid Full and Partila Block Invalidation
class HBD06_HybridBlockCounterVerification(TestCase.TestCase):
    def setUp(self):
        TestCase.TestCase.setUp(self)
    
        # Library Objects
        self.globalVarsObj    = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
        self.ccmObj           = self.globalVarsObj.ccmObj    
        self.accessPatternObj = AccessPatternLib.AccessPatternLib()
        self.utilsObj         = Utils.Utils(self.vtfContainer)
        self.sctpUtilsObj     = SctpUtils.SctpUtils() 
        self.__fwConfigData   = FwConfig.FwConfig(self.vtfContainer)
        self.WaypointRegObj   = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
        self.__randomObj      = self.globalVarsObj.randomObj
                                
        # Variation variables
        self.amountOfData   = self.currCfg.variation.amountOfData
        self.transferLength = self.accessPatternObj.GetTransferLength(self.currCfg.variation.transferLengthMode)
        self.transferLengthMode = self.currCfg.variation.transferLengthMode
        self.alignment = self.accessPatternObj.GetAlignment(self.currCfg.variation.alignmentMode, self.transferLength)
        self.readWriteSelect = self.currCfg.variation.readWriteSelect
        self.verifyMode      = self.currCfg.variation.verifyMode
    
        # For short stroking only. i.e. CMD Line: "--lbaRange=0-1024"
        self.startLba, self.endLba = self.utilsObj.AdjustStartAndEndLBA()
        self.lbaRange = [self.startLba, self.endLba]
	self.sectorsPerLg=self.__fwConfigData.sectorsPerLg
    
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	        
        self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')         
        #self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.__livet = self.vtfContainer._livet
        self.__livetFlash = self.__livet.GetFlash() 

        self.__HDWMode = False
        self.__HybridSequentialMode = False
        self.__HDWSwitchHappened = False
        self.__GATSyncOccurred   = False
        self.__evictionStart     = False
        
    
        self.wayPointDict = {
            "MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedToClosedHybridBlockList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBReleasedfromClosedHBDList],
            "READ_ONLY_MODE"                           : [],
            "SEQUENTIAL_MODE_SWITCH"                   : [],
            "UM_WRITE"                                 : [],
            "GC_TASK_STARTED"                          : [self.OnGCTaskStarted],
            "MLC_COMPACTION_DATA_TRANSFER_BEGIN"       : [self.OnMLCCompactionDataTransferBegin],
            "HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED"                     : [self.OnHybridBlockRemoved],   
	    "UM_BLOCK_ALLOCATION"                     :[self.OnUmBlockAllocation],
	    "EPWR_START"                 : [self.OnEPWRStart],
	    "EPWR_COMPLETE"              : [self.OnEPWRComplete],	    
            "SLC_COMPACTION_DATA_TRANSFER_BEGIN"       : []
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict) 
        # Config File Params
        #File14Buf = FileData.FileData.GetFile14Data(self.vtfContainer)
        File21Obj = FileData.ConfigurationFile21Data(self.vtfContainer)
        #MaxLimitOfHybridBlocks = File14Buf["numOfHybridBlocks"] 
        HybridBlockEvictionThreshold = File21Obj.HybridBlocksEvictionThreshold
    
        self.metaBlockList = []
        self.ExpectedHybridBlockCount = 1 #First hybrid allocated during DLE hence waypoint for that won't hit.
        self.WaypointReturnedHybridBlockCount = 0
        self.WayPointReturnedClosedHybridBlockCount = 0
        self.ClosedHybridBlockCount = 0
	#MMP Support
	
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}		
	self.CurrentMetaPlane=None
	self.NextMetaPlane=None	
	self.UMCount=0	
	self.HDWStreamSeq_0=False
	self.HDWStreamSeq_1=False
	self.HDWBlkCountSeq_0=0
	self.HDWBlkCountSeq_1=0
	self.HybridBlkCount=0
	self.RandomBlkCount=0
	self.RandomStream=False
	self.GetMLCCount=True
	self.HybridStream=False	
	self.UMBlockAllocation=False
	self.InvalidMB=0x3FFF
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	else:
	    self.MaxMLCFreeCountMetaPlane=0	
    #-------------------------------------------------------------------------------  
    def OnUmBlockAllocation(self,args):
	
	""" 
	    "StreamType","StreamID","PrimaryMB","SecondaryMB","SecondaryMB[2]","SecondaryMB[3]"
	"""
	
	#arguments 
	self.UMBlockAllocation =True
	self.UMCount+=1
	self.PriMB=args["PrimaryMB"]
	self.SecMB=args['SecondaryMB']
	self.SecondSecMB=args['SecondaryMB[2]']
	self.ThirdSecMB=args['SecondaryMB[3]']
	
	#mmp support
	self.PriMBMetaplane= self.PriMB  % self.numberOfMetaPlane
	self.SecMBMetaplane=self.SecMB % self.numberOfMetaPlane
        self.CurrentMetaPlane=self.PriMBMetaplane
	self.logger.Info("","Block Allocated from MetaPlane %d " % self.CurrentMetaPlane)
	self.logger.Info("","UM_BLOCK_ALLOCATION Count  %d" %  self.UMCount)	
	if args["StreamType"] == Constants.StreamTypes.STREAM_HOST_SEQUENTIAL and not self.HostBlkDict.has_key(self.PriMB) :
	    if  args["StreamID"]==0:
		self.HDWStreamSeq_0 =True
		self.HDWBlkCountSeq_0+=1
		self.stream="HDW"
		self.count=self.HDWBlkCountSeq_0
		self.blktype=True
	    else:
		self.HDWStreamSeq_1 =True
		self.HDWBlkCountSeq_1+=1
		self.stream="HDW"
		self.count=self.HDWBlkCountSeq_1
		self.blktype=True
	
	if args["StreamType"] == Constants.StreamTypes.STREAM_HOST_SEQUENTIAL_HYBRID_BLOCK  :
	    self.HybridStream =True
	    self.HybridBlkCount+=1
	    self.stream="Hybrid"
	    self.count=self.HybridBlkCount
	    self.blktype=True
	    
	if args["StreamType"] == Constants.StreamTypes.STREAM_HOST_SLC_RANDOM :
	    self.RandomStream =True	
	    self.RandomBlkCount+=1
	    self.stream="Random"
	    self.count=0		
	    self.blktype=False
	    
	#Host block Dictionary ,  primary ->secondary mapping 
	if not self.HostBlkDict.has_key(self.PriMB  ):
	    self.HostBlkDict[self.PriMB ]=[self.SecMB]
    
	if self.SecondSecMB!=self.InvalidMB and self.SecondSecMB not in self.HostBlkDict[self.PriMB  ] :  
	    self.HostBlkDict[self.PriMB ].append(self.SecondSecMB)
    
     
	if self.ThirdSecMB!=self.InvalidMB and  self.ThirdSecMB not in self.HostBlkDict[self.PriMB ]:
	    self.HostBlkDict[self.PriMB ].append(self.ThirdSecMB)                                                                                

	self.ccmObj.VerifyBlockAllocation(stream=self.stream, count=self.count, CurrentMetaPlane=self.CurrentMetaPlane,MLCFreecountPerMP=self.MLCFreeCountForMMP, MaxMLCFreeCountMetaPlane=self.MaxMLCFreeCountMetaPlane,fwConfig=self.__fwConfigData,Blktype=self.blktype)
        self.blktype=False
    def tearDown(self):
	self.ccmObj.DataVerify()
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

    #-------------------------------------------------------------------------------    
    def testHBD06_HybridBlockCounterVerification(self):
	self.ccmObj.SetLbaTracker()
        self.logger.Info(self.globalVarsObj.TAG, "...Writing data sequentially...")
        self.__transferLength = self.__fwConfigData.sectorsPerSlcMetaBlock
        self.__maxWrites = self.globalVarsObj.maxLba/self.__transferLength
        self.startLG = self.globalVarsObj.randomObj.randint(0, self.__fwConfigData.lgsInCard)
        self.__startLba = self.startLG * self.__fwConfigData.sectorsPerLg               
        self.__numWrites = 0
        sectorsToWrite = 0
        self.sizeInSectors = self.utilsObj.ConvertAmountOfDataToSectors(self.amountOfData) # 1 GB data 

        # Write 1 GB data
        while(self.ClosedHybridBlockCount < 5):
                    
	    sectorsWritten=0
	    TotalsectorsToWrite=self.__fwConfigData.sectorsPerSlcMetaBlock
	    self.txlength=0x100
            self.logger.Info(self.globalVarsObj.TAG, self.globalVarsObj.TAG, "Write with StartLba = %d and TranferLength = %d" % (self.__startLba, self.__transferLength))
	    
	    while sectorsWritten<TotalsectorsToWrite:
		self.accessPatternObj.PerformWrites(Constants.DO_NOT_VERIFY,self.__startLba, self.txlength)
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		else:
		    self.MaxMLCFreeCountMetaPlane=0		
		
		sectorsWritten+=self.txlength
		self.__startLba+=self.txlength
		sectorsToWrite+=self.txlength
            self.__numWrites += 1
            self.__startLba += self.__transferLength
            sectorsToWrite += self.__transferLength
              
        # Check hybrid block count after 1 GB write
        self.HybridBlockCounterCheck()
        
        # Selecting Blocks for invalidation
        self.__HybridBlockCountbeforeinvalidation = len(self.metaBlockList)
        
        self.logger.Info(self.globalVarsObj.TAG, "****************************************************************************************")
        self.logger.Info(self.globalVarsObj.TAG, "Convert the metablock number to physical address and invalidate some hybrid blocks  .")
        self.logger.Info(self.globalVarsObj.TAG, "****************************************************************************************")
        transferLength = self.__fwConfigData.sectorsPerLg
        
        for i in range (0,3):
            self.BlockForPartialInvalidation = self.metaBlockList[0] 
            self.BlockForFullInvalidation = self.metaBlockList[1]
                        
            phyAddr = AddressTypes.PhysicalAddress()
            phyAddrList = self.__livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(self.metaBlockList[i] ,0) # Get block details from first MB in the list
            phyAddrIndex = self.__randomObj.randrange(0, len(phyAddrList))
    
            phyAddr.chip = phyAddrList[phyAddrIndex][0]
            phyAddr.die = phyAddrList[phyAddrIndex][1]
            phyAddr.plane = phyAddrList[phyAddrIndex][2]
            phyAddr.block = phyAddrList[phyAddrIndex][3]  
            phyAddr.wordLine = self.__randomObj.randint(0,self.__fwConfigData.wordLinesPerPhysicalBlock_BiCS)    
            phyAddr.string = self.__randomObj.randint(0,self.__fwConfigData.stringsPerBlock)
    
            package = phyAddr.chip
            if self.__fwConfigData.isBiCS:
                address = (phyAddr.die, phyAddr.plane, phyAddr.block, phyAddr.wordLine, phyAddr.string, 0, 0)
            else:
                address = (phyAddr.die, phyAddr.plane, phyAddr.block, phyAddr.wordLine, 0, 0)
            
            # Get the lba's from physical blocks
            self.logger.Info(self.globalVarsObj.TAG, "Get the lba's from physical blocks 0x%X " % self.metaBlockList[i])
            self.GetWordlineLbas(package,address)
            
            self.logger.Info(self.globalVarsObj.TAG, "Invalidating the 0x%X Hybrid Block"%self.metaBlockList[i])
            for lba in self.errorAffectedLbaListTemp:
                self.ccmObj.Write(lba, 0x1)
        
        # Check hybrid block count post invalidation
        self.HybridBlockCounterCheck()
        
        # Inserting delay of 10 seconds
        self.utilsObj.InsertDelay(10000)
                
        # Perform Random writes
        transferLength = 0x50
        for i in range(5):
            self.startLG = self.globalVarsObj.randomObj.randint(0, self.__fwConfigData.lgsInCard)
            self.__startLba = self.startLG * self.__fwConfigData.sectorsPerLg   
            self.ccmObj.Write(self.__startLba, transferLength)
	    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	    if self.numberOfMetaPlane>1:
		self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	    else:
		self.MaxMLCFreeCountMetaPlane=0		
        
        # Inserting delay of 5 seconds after Random writes
        self.utilsObj.InsertDelay(5000)    
        
        # Perform few Sequential writes
        self.startLG = self.globalVarsObj.randomObj.randint(0, self.__fwConfigData.lgsInCard)
        self.__startLba = self.startLG * self.__fwConfigData.sectorsPerLg    
        transferLength = self.__fwConfigData.sectorsPerSlcMetaBlock
        for i in range(5):
            self.ccmObj.Write(self.__startLba, transferLength)
	    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	    if self.numberOfMetaPlane>1:
		self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	    else:
		self.MaxMLCFreeCountMetaPlane=0		
            
        # Check hybrid block count after delay and more writes
        self.HybridBlockCounterCheck()                                
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)        
    #-------------------------------------------------------------------------------------------
    def HybridBlockCounterCheck(self):
        # Check if number of hybrid blocks added exceeds max limit of hybrid block
        if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxLimitOfHybridBlocks:
            raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
                                                (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxLimitOfHybridBlocks))
        
        # Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
        if self.ClosedHybridBlockCount != self.WayPointReturnedClosedHybridBlockCount:
            raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
                                                (self.ClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))
        
    #--------------------------------------------------------------------------------------------
    def OnEPWRComplete(self,argsDict):
	if self.EPWRStart:
	    self.GetMLCCount=True
	    self.EPWRStart=False
	    
    #-------------------------------------------------------------------------------------------
    def OnEPWRStart(self, argsDict):
	"""
	"Block", "Sector", "NumSectors", "MemoryAccess", "Requestor"
	"""
		
	self.EPWRStart=True          
    #-------------------------------------------------------------------------------------------                    
    def OnHybridBlockAdded(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount", "StreamID"
        """
        self.metaBlockList.append(args['MBAddress'])

        self.ExpectedHybridBlockCount += 1
        self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
	if self.WaypointReturnedHybridBlockCount != (self.ClosedHybridBlockCount + 1):
	    raise ValidationError.TestFailError("", "Last Closed Hybrid Block Count: %d. Expected New Hybrid Block Count: %d, Received New Hybrid Block Count: %d" %
					                                                  (self.ClosedHybridBlockCount, self.ClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
        
        return
    #-------------------------------------------------------------------------------------------
    def OnHybridBlockRemoved(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount"
        """
        self.ExpectedHybridBlockCount -= 1    
        self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
        
    #-------------------------------------------------------------------------------------------
    def OnMBReleasedfromClosedHBDList(self, args):
        """
        "MBAddress", "ClosedHybridBlockCount"
        """
        self.ClosedHybridBlockCount -= 1
        self.WayPointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"] 
        return
    
    #-------------------------------------------------------------------------------------------
    def OnMBAddedToClosedHybridBlockList(self, args):
        """
            MBAddress, ClosedHybridBlockCount
        """
        self.WayPointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"] 
        self.ClosedHybridBlockCount += 1
        return
    
    #-------------------------------------------------------------------------------------------
    def OnMLCCompactionDataTransferBegin(self, args):
        """
        Args: "SrcMB", "DestMB", "DestMBOffset", "NumOfFragments"
        """
        if args["SrcMB"] ==  self.metaBlockList[0]:
            self.bloclCompacted = args["SrcMB"]
            self.logger.Info(self.globalVarsObj.TAG, "Compaction triggerd on partially invalidated Block as expected")
            self.InvalidBlockCompacted = True
    
    #------------------------------------------------------------------------------------------- 
    def OnGCTaskStarted(self, args):
        if (args["GCComponentType"] == GCConstants.GC_Component_GatCompaction):
            self.__GATSyncOccurred = True

    #-------------------------------------------------------------------------------------------
    def GetWordlineLbas(self,package,addr):
        """
        Description:
           * Gets the wordline lbas
        """
        self.errorAffectedLbaListTemp = []
        wordLineLbas = self.__livetFlash.GetWordlineLBAs(package,addr)
        startIndex = wordLineLbas[0] + 1
        self.logger.Info(self.globalVarsObj.TAG, "wordline lbas :: %s"%(list(wordLineLbas)))
        # Form a list with valid lba's
        for lba in range(startIndex,len(wordLineLbas)):
            if not wordLineLbas[lba] < 0:
                self.errorAffectedLbaListTemp.append(wordLineLbas[lba])        
