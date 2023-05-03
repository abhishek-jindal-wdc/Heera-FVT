#"""
#*********************************************************************************************
    # @file       : HBD07_HybridBlockExchange.py
    # @brief      : The test is designed to check Hybrid Block Exchange
    # @author     : Komala Nataraju
    # @date       : 05 MAY 2020
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

# @brief A class as a structure for HBD07_HybridBlockExchange Test
# @details Test scope is to check Hybrid Block Exchange
class HBD07_HybridBlockExchange(TestCase.TestCase):

        # @brief A method to instantiate and define variables used by HBD07_HybridBlockExchange Class
    # @details Here we instantiate objects of GlobalVars and Common Code Manager modules.
    # Also read the input parameters from the XML Config file and assign it to local variables
    # @Params This method takes no parameters
    # @return None
    # @exception None
    def setUp(self):
        TestCase.TestCase.setUp(self)

        # Library Objects
        self.globalVarsObj    = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
        self.ccmObj           = self.globalVarsObj.ccmObj    
        self.accessPatternObj = AccessPatternLib.AccessPatternLib()
        self.utilsObj         = Utils.Utils()
        self.sctpUtilsObj     = SctpUtils.SctpUtils() 
        self.__fwConfigData   = FwConfig.FwConfig(self.vtfContainer)
        self.WaypointRegObj   = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
        self.__randomObj      = self.globalVarsObj.randomObj
        self.BlockForPartialInvalidation = None
	self.BlockForFullInvalidation = None
	
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
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	        
        self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')  
       # self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.__livet = self.vtfContainer._livet
        self.__livetFlash = self.__livet.GetFlash()

        self.__HDWMode = False
        self.__HybridSequentialMode = False
        self.__HDWSwitchHappened = False
    
        self.wayPointDict = {
            "HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED"                     : [self.OnHybridBlockRemoved],
            "MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedtoClosedHBDList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBReleasedfromClosedHBDList],
            "READ_ONLY_MODE"                           : [],
            "SEQUENTIAL_MODE_SWITCH"                   : [],
	    "EPWR_START"                 : [self.OnEPWRStart],
	    "EPWR_COMPLETE"              : [self.OnEPWRComplete],	    
            "UM_WRITE"                                 : [self.OnUmWrite],
            "GC_TASK_STARTED"                          : [self.OnGCTaskStarted],
            "HYBRID_BLOCK_EVICTION_COMPLETE"           : [],
            "HYBRID_BLOCK_EVICTION_IN_PROGRESS"        : [],
            "HYBRID_BLOCK_EVICTION_START"              : [self.OnHybridBlockEvictionStart], 
	    "UM_BLOCK_ALLOCATION"                     :[self.OnUmBlockAllocation],
            "MLC_COMPACTION_BEGIN"                     : [self.OnMLCCompactionBegin],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict) 
        # Config File Params
        ##File14Buf = FileData.FileData.GetFile14Data(self, self.vtfContainer)
        File21Obj = FileData.ConfigurationFile21Data(self.vtfContainer)
        ##MaxLimitOfHybridBlocks = File14Buf["numOfHybridBlocks"] 
        HybridBlockEvictionThreshold = File21Obj.HybridBlocksEvictionThreshold
    
        self.metaBlockList = []
	#MMP Support
	self.MMP=1
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.MMP=1
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}	
	self.CurrentMetaPlane=None
	self.NextMetaPlane=None	
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
	self.UMCount=0	
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
    
	else:
	    self.MaxMLCFreeCountMetaPlane=0	  	
        self.__EvictionStart = False
        self.ExpectedHybridBlockCount = 1
        self.closedHybridBlockCount = 0
    
    #------------------------------------------------------------------------------------            
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

    #------------------------------------------------------------------------------------   
    def testHBD07_HybridBlockExchange(self):
	self.ccmObj.SetLbaTracker()
        self.logger.Info(self.globalVarsObj.TAG, "...Writing data sequentially...")
        self.__transferLength = self.__fwConfigData.sectorsPerSlcMetaBlock
        self.__maxWrites = self.globalVarsObj.maxLba/self.__transferLength
        self.__startLba = 0
        self.__numWrites = 0
        self.sizeInSectors = 1024 * 1024 * 2 #self.utilsObj.ConvertAmountOfDataToSectors(self.amountOfData) # 1 GB data 
        self.sizeInSectors += self.__startLba

        while(self.__startLba < self.sizeInSectors):
            self.LBAWrittenList = []

            sectorsToWrite=self.__fwConfigData.sectorsPerSlcMetaBlock
	    sectorsWritten=0
	    self.txlength=0x100
	    self.logger.Info(self.globalVarsObj.TAG, "Write with StartLba = %d and TranferLength = %d" % (self.__startLba, self.__transferLength))
	    while  sectorsWritten< sectorsToWrite:
		if (self.__startLba + self.txlength) < self.globalVarsObj.maxLba:
		    self.accessPatternObj.PerformWrites(Constants.DO_NOT_VERIFY,self.__startLba,self.txlength)
		    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		    if self.numberOfMetaPlane>1:
			self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		    else:
			self.MaxMLCFreeCountMetaPlane=0	  		    
		    
		    self.LBAWrittenList.append(self.__startLba)  
		    self.__numWrites += 1
		else:
		    self.__startLba = 0
		
		
		sectorsWritten+=self.txlength
		self.__startLba+=self.txlength
            #if (self.__startLba + self.__transferLength) < self.globalVarsObj.maxLba:
                #self.accessPatternObj.PerformWrites(Constants.DO_NOT_VERIFY,self.__startLba, self.__transferLength)
                #self.LBAWrittenList.append(self.__startLba)
                #self.logger.Info(self.globalVarsObj.TAG, "Write with StartLba = %d and TranferLength = %d" % (self.__startLba, self.__transferLength))
                #self.__numWrites += 1
            #else:
                #self.__startLba = 0

            #self.__startLba += self.__transferLength 

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

            ## Get the lba's from physical blocks
            self.logger.Info(self.globalVarsObj.TAG, "Get the lba's from physical blocks 0x%X " % self.metaBlockList[i])
            self.GetWordlineLbas(package,address)

            self.logger.Info(self.globalVarsObj.TAG, "Invalidating the 0x%X Hybrid Block" % self.metaBlockList[i])
            for lba in self.errorAffectedLbaListTemp:
                self.accessPatternObj.PerformWrites(Constants.DO_NOT_VERIFY,lba, 0x1)

        self.sctpUtilsObj.ForceHybridEviction()
        
        # One write post Force HB Eviction
        self.ccmObj.Write(0, 0x2000)
        
        if not self.__EvictionStart:
            raise ValidationError.TestFailError("", "Hybrid Eviction did not start upon forcing through diag. Closed Hybrid Block Count = %d" % self.closedHybridBlockCount)
    
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)            
    #------------------------------------------------------------------------------------               
    def OnUmWrite(self, args):
        if (args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_HYBRID):                   
            self.__IsHybridSequentialMode = True
        elif (args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_SEQUENTIAL_0 or 
              args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_SEQUENTIAL_1 ): 
            self.__IsHDWMode = True
        elif(args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_RANDOM or
             args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_RANDOM_INTERMEDIATE):                   ## Random write
            self.__IsRandomstream =True
        return True
            

    #------------------------------------------------------------------------------------       
    def OnHybridBlockEvictionStart(self, args):
        self.__EvictionStart =True
    

    #------------------------------------------------------------------------------------       
    def OnMBAddedtoClosedHBDList(self, args):
        """
        Args: MBAddress, ClosedHybridBlockCount
        """
        self.metaBlockList.append(args["MBAddress"])
        self.closedHybridBlockCount = args["ClosedHybridBlockCount"]
        return

    #------------------------------------------------------------------------------------
    def OnMBReleasedfromClosedHBDList(self, args):
        """
        Args: MBAddress, ClosedHybridBlockCount
        """     
        MB = args["MBAddress"]
        self.closedHybridBlockCount = args["ClosedHybridBlockCount"]
        if MB == self.BlockForPartialInvalidation:
            #self.PartiallyInvalidBlockReleased = true
            self.logger.Info(self.globalVarsObj.TAG, "Partially invalidated block is released after the compaction")
            
        if MB == self.BlockForFullInvalidation :
            #self.FullyInvalidBlocReleased = true
            self.logger.Info(self.globalVarsObj.TAG, "The invalidated hybrid block(0x%X) is compacted and released from the Closed hybrid block List." % self.BlockForFullInvalidation)
        
        #self.metaBlockList.remove(MB)
        self.HybridBlockReleased = True

    
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
		self.count=self.HDWBlkCountSeq_0	
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
	    self.count=self.RandomBlkCount	
	    self.blktype=True
	
	
	#Host block Dictionary ,  primary ->secondary mapping 
	if not self.HostBlkDict.has_key(self.PriMB  ):
	    self.HostBlkDict[self.PriMB ]=[self.SecMB]
    
	if self.SecondSecMB!=self.InvalidMB and self.SecondSecMB not in self.HostBlkDict[self.PriMB  ] :  
	    self.HostBlkDict[self.PriMB ].append(self.SecondSecMB)
    
     
	if self.ThirdSecMB!=self.InvalidMB and  self.ThirdSecMB not in self.HostBlkDict[self.PriMB ]:
	    self.HostBlkDict[self.PriMB ].append(self.ThirdSecMB)                                                                                

        self.ccmObj.VerifyBlockAllocation(stream=self.stream, count=self.count, CurrentMetaPlane=self.CurrentMetaPlane,MLCFreecountPerMP=self.MLCFreeCountForMMP, MaxMLCFreeCountMetaPlane=self.MaxMLCFreeCountMetaPlane, fwConfig=self.__fwConfigData,Blktype=self.blktype)
        self.blktype=False
    
    #------------------------------------------------------------------------------------
    def OnMLCCompactionBegin(self, args):
        """
        "SrcMB", "VFC", "DestMB", "DestAccessType"
        """
        if args["SrcMB"] ==  self.metaBlockList[0]:
            self.blockCompacted = args["SrcMB"]
            self.logger.Info(self.globalVarsObj.TAG, "Compaction triggerd on invalidated Block as expected")
            self.InvalidBlockCompacted = True
            
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
    #------------------------------------------------------------------------------------
    def OnGCTaskStarted(self, args):
        """
        "Bank", "GCComponentType", "GCCategoryType", "Time"
        """
        if (args["GCComponentType"] == GCConstants.GC_Component_GatCompaction):
            self.__GATSyncOccurred = True
        return
    
    #------------------------------------------------------------------------------------
    def OnHybridBlockAdded(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount", "StreamID"
        """
        self.ExpectedHybridBlockCount += 1  
        if self.ExpectedHybridBlockCount != args["HybridBlockCount"]:
            raise ValidationError.TestFailError("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
                                                (self.ExpectedHybridBlockCount, args["HybridBlockCount"]))
    
        return True
    
    #------------------------------------------------------------------------------------
    def OnHybridBlockRemoved(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount"
        """
        self.ExpectedHybridBlockCount -= 1  
        if self.ExpectedHybridBlockCount != args["HybridBlockCount"]:
            raise ValidationError.TestFailError("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
                                                (self.ExpectedHybridBlockCount, args["HybridBlockCount"]))
    
        return True
    
    #------------------------------------------------------------------------------------
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
