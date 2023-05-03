#"""
#*********************************************************************************************
    # @file       : HBD04_HybridFirstBlockFullSecondBlockPartialInvalidation.py
    # @brief      : The test is designed to check Hybrid Full and Partial Block Invalidation
    # @author     : Komala Nataraju
    # @date       : 29 APR 2020
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
import AddressTypes as AddressTypes
from Constants import GC as GCConstants 
#FVT Imports goes here
import GlobalVars as GlobalVars
from Constants import StreamTypes as ST


# @brief A class as a structure for HBD04 Test
# @details Test scope is to check Hybrid Full and Partila Block Invalidation
class HBD04_HybridFirstBlockFullSecondBlockPartialInvalidation(TestCase.TestCase):

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
    
        # Variation variables
        self.amountOfData   = self.currCfg.variation.amountOfData
        self.transferLength = self.accessPatternObj.GetTransferLength(self.currCfg.variation.transferLengthMode)
        self.transferLengthMode = self.currCfg.variation.transferLengthMode
        self.alignment = self.accessPatternObj.GetAlignment(self.currCfg.variation.alignmentMode, self.transferLength)
        self.readWriteSelect = self.currCfg.variation.readWriteSelect
        self.verifyMode      = self.currCfg.variation.verifyMode
    
        # For short stroking only. i.e. CMD Line: "--lbaRange=0-1024"
        self.startLba, self.endLba = self.utilsObj.AdjustStartAndEndLBA()
        self.lbaRange = [self.startLba, self.endLba/2]
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	        
        self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks') 
	#self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.__livet = self.vtfContainer._livet
        self.__livetFlash = self.__livet.GetFlash()        
        self.__HDWMode = False
        self.__HybridSequentialMode = False
        self.__HDWSwitchHappened = False
        #self.__GATSyncOccurred   = False
	self.stop_over_write = False
	
    
        self.wayPointDict = {
            "HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED"                     : [self.OnHybridBlockRemoved],
            "MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedtoClosedHBDList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBReleasedfromClosedHBDList],
            "READ_ONLY_MODE"                           : [],
            "SEQUENTIAL_MODE_SWITCH"                   : [],
	    "GCC_START":[self.OnGCCStart],
            "UM_WRITE"                                 : [],
	    "EPWR_START"                 : [self.OnEPWRStart],
	    "EPWR_COMPLETE"              : [self.OnEPWRComplete],	    
            "GC_TASK_STARTED"                          : [self.OnGCTaskStarted],
            "MLC_COMPACTION_BEGIN"                     : [self.OnMLCCompactionBegin],
	    "UM_BLOCK_ALLOCATION"      : [self.OnUMBlockAllocation],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict) 
	#MMP Support
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}	
        
        self.metaBlockList                 = []
        self.__lbaList                     = []
        self.ExpectedHybridBlockCount      = 1 #First hybrid allocated during DLE hence waypoint for that won't hit.
        self.ClosedHybridBlockCount        = 0
        self.FullyInvalidBlockReleased     = False
        self.PartialInvalidBlockCompacted  = False
        self.PartiallyInvalidBlockReleased = False
        self.blockCompacted                = None
        self.BlockForPartialInvalidation   = None
        self.BlockForFullInvalidation      = None
        self.HybridBlockReleased           = False
        self.WaypointReturnedHybridBlockCount = 1 #First hybrid allocated during DLE hence waypoint for that won't hit.
	self.WaypointReturnedClosedHybridBlockCount = 0
	self.ReleasedBlockCount = 0
	self.FullyInvalidatedBlockCount = 0
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
	self.UMBlockAllocation=False
	self.GetMLCCount=True	
	self.InvalidMB=0x3FFF
	self.HybridStream=False	
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	else:
	    self.MaxMLCFreeCountMetaPlane=0	
	
	self.block_for_full_invalidation = None
	      
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
    def testHBD04_HybridFirstBlockFullSecondBlockPartialInvalidation(self):
	self.ccmObj.SetLbaTracker()
        self.logger.Info(self.globalVarsObj.TAG, "...Writing data sequentially...")
        
        #if self.globalVarsObj.vtfContainer.cmd_line_args.numOfDies == 1:
	    #self.shift_inMBoffset = 0x800
	#elif self.globalVarsObj.vtfContainer.cmd_line_args.numOfDies == 2:
	    #self.shift_inMBoffset = 0x1000
	#else:
	    #self.shift_inMBoffset = 0x2000
	self.shiftInWl=8
	self.wlSize=self.__fwConfigData.planeInterleave*self.__fwConfigData.dieInterleave*self.__fwConfigData.pageSize*self.__fwConfigData.stringsPerBlock
        self.shift_inMBoffset      = self.shiftInWl *self.wlSize  
        self.sizeInSectors = 1024 *1024 * 2    #1 GB data 
	self.__startLba = self.accessPatternObj.GetRandomStartLba(self.lbaRange, self.alignment)
	self.endOfSector =  self.__startLba + self.sizeInSectors
	sectorsWritten = 0
	i = 1
	self.block = None
	
	self.accessPatternObj.LogStartEndSector(self.__startLba, min(self.endOfSector, self.endLba), self.sizeInSectors)
        while(sectorsWritten < self.sizeInSectors):
	    
	    if i % 2: 
		self.__transferLength = self.__fwConfigData.slcMBSize - self.shift_inMBoffset
		self.accessPatternObj.PerformWrites(self.verifyMode, self.__startLba, self.__transferLength)
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		else:
		    self.MaxMLCFreeCountMetaPlane=0		
			
		self.logger.Info(self.globalVarsObj.TAG,"Fully Invalidating the block: 0x%X" %(self.block))
		self.FullyInvalidatedBlockCount += 1
		self.accessPatternObj.PerformWrites(self.verifyMode, self.__startLba, self.__transferLength)
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		else:
		    self.MaxMLCFreeCountMetaPlane=0		
			
		self.__startLba += self.__transferLength 
		sectorsWritten += self.__transferLength
		sector = 2*self.__fwConfigData.slcMBSize
		i += 1
	    else:
		self.__transferLength = self.__fwConfigData.slcMBSize - self.shift_inMBoffset
		self.accessPatternObj.PerformWrites(self.verifyMode, self.__startLba, self.__transferLength)
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		else:
		    self.MaxMLCFreeCountMetaPlane=0		
		
		self.__startLba += self.__transferLength 
		sectorsWritten += self.__transferLength
		sector = 0
		i += 1
	count = 0
	self.__startLba += self.__transferLength
	self.__transferLength = self.__fwConfigData.slcMBSize - self.shift_inMBoffset
	
	while count < 50:
	    self.accessPatternObj.PerformWrites(self.verifyMode, self.__startLba, self.__transferLength)
	    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	    if self.numberOfMetaPlane>1:
		self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	    else:
		self.MaxMLCFreeCountMetaPlane=0	    
	    self.__startLba += self.__transferLength
	    if self.FullyInvalidatedBlockCount == self.ReleasedBlockCount:
		self.logger.Info(self.globalVarsObj.TAG,"Invalidated blocks got released after writing %d blocks" %(count))
		break
	    count += 1
	self.logger.Info("","number of writes performed :%d" %count)   
	      
	    
	#self.accessPatternObj.PerformWrites(self.verifyMode, self.__startLba + self.__transferLength, 0x1c000)	
            # Check if number of hybrid blocks added exceeds max limit of hybrid block
	if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxLimitOfHybridBlocks:
            raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
                                                    (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxLimitOfHybridBlocks))
            
            # Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
	if self.ClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
						raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
							                                                (self.ClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))	
	#if self.ExpectedHybridBlockCount != self.WaypointReturnedHybridBlockCount:
            #raise ValidationError.TestFailError("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
                                                    #(self.ExpectedHybridBlockCount, self.WaypointReturnedHybridBlockCount))
            
	#self.logger.Info(self.globalVarsObj.TAG, self.globalVarsObj.TAG, "Write with StartLba = %d and TranferLength = %d" % (self.__startLba, self.__transferLength))
	    
        
        #if self.FullyInvalidBlockReleased == False:
	    #raise ValidationError.TestFailError("", "Fully Invalidated block 0x%X is not released" %self.metaBlockList[0])
	#if not self.FullyInvalidBlockReleased:
	    #raise ValidationError.TestFailError("", "Fully invalidated block is not released")
	if self.FullyInvalidatedBlockCount != self.ReleasedBlockCount:
	    raise ValidationError.TestFailError("", "Fully invalidated block count: %d, Released Block Count: %d" %(self.FullyInvalidatedBlockCount, self.ReleasedBlockCount))               

	    #self.logger.Info(self.globalVarsObj.TAG, "Fully invalidated block count: %d, Released Block Count: %d" %(self.FullyInvalidatedBlockCount, self.ReleasedBlockCount))               
        #if self.__GATSyncOccurred :
            #if(self.PartialInvalidBlockCompacted == True ):
                #self.logger.Info(self.globalVarsObj.TAG, "The Partially invalidated hybrid block(0x%X) is compacted during GAT sync time" % self.BlockForPartialInvalidation)
            #else:
                #raise ValidationError.TestFailError("Partially invalidated hybrid block(0x%X) is not compacted" % self.BlockForPartialInvalidation)        
            
            #if (self.FullyInvalidBlockReleased == True):
                #self.logger.Info(self.globalVarsObj.TAG, "The invalidated hybrid block(0x%X) is compacted and released from the Closed hybrid block List." % self.BlockForFullInvalidation)
            #else:
                #raise ValidationError.TestFailError("The invalidated hybrid block(0x%X) is not compacted and  released from the Closed hybrid block List." % self.BlockForFullInvalidation)
            
            #if(self.PartiallyInvalidBlockReleased == True):
                #self.logger.Info(self.globalVarsObj.TAG, ("The invalidated hybrid block(0x%X) is not compacted and  released from the Closed hybrid block List." % self.BlockForPartialInvalidation))
            #else:
                #raise ValidationError.TestFailError("The invalidated hybrid block(0x%X) is not compacted and  released from the Closed hybrid block List." % self.BlockForPartialInvalidation)
    
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)	
                
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
	self.block = args["MBAddress"]
	self.metaBlockList.append(args["MBAddress"])
	
	if len(self.metaBlockList) == 4:
	    self.BlockForFullInvalidation = self.metaBlockList[3]        
        self.ExpectedHybridBlockCount += 1  
        	
	self.new_blk_added = True
	
        self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
	if self.WaypointReturnedHybridBlockCount != (self.ClosedHybridBlockCount + 1):
			raise ValidationError.TestFailError("", "Last Closed Hybrid Block Count: %d. Expected New Hybrid Block Count: %d, Received New Hybrid Block Count: %d" %
				                                            (self.ClosedHybridBlockCount, self.ClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
	
        return
    
    #------------------------------------------------------------------------------------
    def OnHybridBlockRemoved(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount"
        """
        self.ExpectedHybridBlockCount -= 1  
        self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
	if self.WaypointReturnedHybridBlockCount != (self.ClosedHybridBlockCount + 1):
			raise ValidationError.TestFailError("", "Last Closed Hybrid Block Count: %d. Expected New Hybrid Block Count: %d, Received New Hybrid Block Count: %d" %
				                                            (self.ClosedHybridBlockCount, self.ClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
	
        return
    
    #------------------------------------------------------------------------------------
    def OnMBReleasedfromClosedHBDList(self, args):
        """
        "MBAddress", "ClosedHybridBlockCount"
        """
	self.ReleasedBlockCount += 1 
        self.ClosedHybridBlockCount = self.ClosedHybridBlockCount - 1
	self.WaypointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"]
	#self.WaypointReturnedHybridBlockCount = args["ClosedHybridBlockCount"] + 1
	
        if args["MBAddress"] == self.BlockForPartialInvalidation and args["MBAddress"] == self.blockCompacted :
            self.PartiallyInvalidBlockReleased = True
            self.logger.Info(self.globalVarsObj.TAG, "Partially invalidated block is released after the compaction")
	elif args["MBAddress"] == self.BlockForPartialInvalidation:
	    raise ValidationError.TestFailError("Partially Invalidated Block %d is released without compaction" % self.BlockForPartialInvalidation)
        if args["MBAddress"] == self.BlockForFullInvalidation :
            self.FullyInvalidBlockReleased = True
	    self.stop_over_write = True	
            self.logger.Info(self.globalVarsObj.TAG, "The invalidated hybrid block(0x%X) is compacted and released from the Closed hybrid block List." % self.BlockForFullInvalidation)
        
        #self.metaBlockList.remove(args["MBAddress"])
        self.HybridBlockReleased = True
         
	

    #------------------------------------------------------------------------------------
    def OnMLCCompactionBegin(self, args):
        """
        "SrcMB", "VFC", "DestMB", "DestAccessType"
        """
        if args["SrcMB"] ==  self.metaBlockList[0]:
            self.blockCompacted = args["SrcMB"]
            self.logger.Info(self.globalVarsObj.TAG, "Compaction triggerd on partially invalidated Block as expected")
            self.PartialInvalidBlockCompacted = True

    #------------------------------------------------------------------------------------
    def OnEPWRComplete(self,argsDict):
	if self.EPWRStart:
	    self.GetMLCCount=True
	    self.EPWRStart=False
	
    def OnGCCStart(self,args):
	return True
#-----------------------------------------------------------------------------------------
    def OnEPWRStart(self, argsDict):
	"""
	"Block", "Sector", "NumSectors", "MemoryAccess", "Requestor"
	"""
	
	
	self.EPWRStart=True	    
    def OnGCTaskStarted(self, args):
        """
        "Bank", "GCComponentType", "GCCategoryType", "Time"
        """
        if (args["GCComponentType"] == GCConstants.GC_Component_GatCompaction):
            self.__GATSyncOccurred = True

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
		
    def OnUMBlockAllocation(self, args):
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
        self.logger.Info("","UM_BLOCK_ALLOCATION Count %d" %  self.UMCount)	
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
	    self.blktype=True
	    self.count=self.RandomBlkCount	    
	
	    
	#Host block Dictionary ,  primary ->secondary mapping 
	if not self.HostBlkDict.has_key(self.PriMB):
	    self.HostBlkDict[self.PriMB]=[self.SecMB]
    
	if self.SecondSecMB!=self.InvalidMB and self.SecondSecMB not in self.HostBlkDict[self.PriMB] :
	    self.HostBlkDict[self.PriMB].append(self.SecondSecMB)
    
    
	if self.ThirdSecMB!=self.InvalidMB and  self.ThirdSecMB not in self.HostBlkDict[self.PriMB]:
	    self.HostBlkDict[self.PriMB].append(self.ThirdSecMB)  
	    
	
	self.ccmObj.VerifyBlockAllocation(stream=self.stream, count=self.count, CurrentMetaPlane=self.CurrentMetaPlane, MLCFreecountPerMP=self.MLCFreeCountForMMP,MaxMLCFreeCountMetaPlane=self.MaxMLCFreeCountMetaPlane, fwConfig=self.__fwConfigData,Blktype=self.blktype)
	self.blktype=False
	
	if len(self.metaBlockList) == 0:
	    self.metaBlockList.append(self.PriMB)
	    self.block = self.PriMB
	
	
	return
	
