#"""
#********************************************************************************************************************************************
    # @file       : HBD03_HybridStreamCheck.py
    # @brief      : The test is designed to check there are 2 sequential Streams for HDW and 1 Sequential stream for Hybrid Block writes
    # @author     : Komala Nataraju
    # @date       : 05 MAY 2020
    # @copyright  : Copyright (C) 2020 SanDisk Corporation
#********************************************************************************************************************************************
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

#FVT Imports goes here
import GlobalVars as GlobalVars


# @brief A class as a structure for HBD03_HybridStreamCheck Test
# @details Test scope is to check stream change between Hybrid Sequential and random stream
class HBD03_HybridStreamCheck(TestCase.TestCase):

    # @details Here we instantiate objects of GlobalVars and Common Code Manager modules.
    # Also read the input parameters from the XML Config file and assign it to local variables
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
    
        self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
    
        self.__IsHDWMode = False
        self.__IsHybridSequentialMode = False
        self.__HDWSwitchHappened = False
    
        self.wayPointDict = {
            #"HYBRID_BLOCK_URGENT_COMPACTION_START"     : [self.OnHybridBlockUrgentCompaction],
            #"HYBRID_BLOCK_URGENT_COMPACTION_COMPLETE"  : [self.OnHybridBlockUrgentCompactionCompleted],
            "HYBRID_BLOCK_EVICTION_COMPLETE"           : [],
            "HYBRID_BLOCK_EVICTION_IN_PROGRESS"        : [],
            "HYBRID_BLOCK_EVICTION_START"              : [self.OnHybridBlockEvictionStart],
	     "UM_BLOCK_ALLOCATION"                     :[self.OnUmBlockAllocation],
            #"MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedtoClosedHBDList],
            #"MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBReleasedfromClosedHBDList],
            "READ_ONLY_MODE"                           : [],
            "SEQUENTIAL_MODE_SWITCH"                   : [],
            "UM_WRITE"                                 : [self.OnUmWrite],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict) 
        #MMP Support
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}	
        
        # Config File Params
        #File14Buf = FileData.FileData.GetFile14Data(self.vtfContainer)
        File21Obj = FileData.ConfigurationFile21Data(self.vtfContainer)
        #MaxLimitOfHybridBlocks = File14Buf["numOfHybridBlocks"] 
        HybridBlockEvictionThreshold = File21Obj.HybridBlocksEvictionThreshold
        
    #-----------------------------------------------------------------------------------------
    def testHBD03_HybridStreamCheck(self):
        self.ccmObj.SetLbaTracker()
        self.logger.Info(self.globalVarsObj.TAG, "...Writing data sequentially...")
        self.executedWrites = []
        sectorsWritten = 0
        reachedEndRange = False
        self.__maxWrites = self.globalVarsObj.maxLba
        self.startLba = 0 
        
        if self.globalVarsObj.vtfContainer.cmd_line_args.startLba == None:
            self.currSector_1 = self.accessPatternObj.GetRandomStartLba(self.lbaRange, self.alignment)
        else:
            self.currSector_1 = self.startLba
        self.currSector_2  = self.__maxWrites/2 
        
        self.sizeInSectors = self.utilsObj.ConvertAmountOfDataToSectors(self.amountOfData)  
        self.endOfSector =  self.currSector_1 + self.sizeInSectors

        self.accessPatternObj.LogStartEndSector(self.currSector_1, min(self.endOfSector, self.endLba), self.sizeInSectors)

        # Set number of Hybrid Blocks to 2
        self.sctpUtilsObj.SetMaxHybridBlockCount(2)
        
            
        # obtaining the updated transer length
        hybridTransferferLength = self.__fwConfigData.sectorsPerSlcBlock
	self.dataWritten=0
                 
        # executing first writes
        if self.readWriteSelect in ("write", "both"):
	    while self.dataWritten<self.__fwConfigData.sectorsPerSlcBlock:
		self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector_1, hybridTransferferLength)
		self.dataWritten+=hybridTransferferLength
        self.executedWrites.append(( self.currSector_1, hybridTransferferLength))
        sectorsWritten += hybridTransferferLength
        self.currSector_1 += hybridTransferferLength
            
        # executing second writes 
        if self.readWriteSelect in ("write", "both"):
            self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector_2, txferLength_2)
        self.executedWrites.append(( self.currSector_2, txferLength))
        sectorsWritten += txferLength_2
        self.currSector_2 += txferLength_2  
                
        if (sectorsWritten < self.ThresholdMaxLimitOfHybridBlocks):
            if not self.__IsHybridSequentialMode :
                raise ValidationError.TestFailError("","The hybrid writes are not routed to hybrid stream")
        else:
            if not self.__IsHDWMode:                        
                raise ValidationError.TestFailError("","The HDW writes are not routed to HDW streams")
	    
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)	

    # @brief  A waypoint callback 
    # @details This waypoint hit when the stream changed from HybridSequential to HDW
    # @return None
    # @exception: None      
    def OnSequentialModeSwitchBackFunc(self):
        self.__HDWSwitchHappened = True
        return True

    # @brief  A waypoint callback 
    # @details UMWrite Waypoint
    # @return None
    # @exception: None
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

    def OnUmBlockAllocation(self,args):
	
	if not self.HostBlkDict.has_key(args['PrimaryMB'] ):
	    self.HostBlkDict[args['PrimaryMB']]=[args['SecondaryMB']]
    
	if args['SecondaryMB[2]']!=0x3FFF and args['SecondaryMB[2]'] not in self.HostBlkDict[args['PrimaryMB'] ] :
    
	    self.HostBlkDict[args['PrimaryMB']].append(args['SecondaryMB[2]'])
    
    
    
	if args['SecondaryMB[3]']!=0x3FFF and  args['SecondaryMB[3]'] not in self.HostBlkDict[args['PrimaryMB']]:
	    self.HostBlkDict[args['PrimaryMB']].append(args['SecondaryMB[3]'])                                                                                

	    
    # @brief  A waypoint callback 
    # @details MB_ADDED_TO_CLOSED_HYBRID_LIST Waypoint
    # @return None
    # @exception: None          
    def OnMBAddedtoClosedHBDList(self):
        self.logger.Info(self.globalVarsObj.TAG, "MB_ADDED_TO_CLOSED_HYBRID_LIST waypoint is Hit: MBA=%d, hybridITGCCount=%d"%(args[0],args[1]))
        self.metaBlockList.append(args[0])
        self.ExpectedHybridBlockCount = self.ExpectedHybridBlockCount + 1  

    # @brief  A waypoint callback 
    # @details MB_RELEASED_FROM_CLOSED_HYBRID_LIST Waypoint
    # @return None
    # @exception: None
    def OnMBReleasedfromClosedHBDList(self):
        self.logger.Info(self.globalVarsObj.TAG, "MB_RELEASED_FROM_CLOSED_HYBRID_LIST waypoint is Hit: MBA=%d, hybridITGCCount=%d"%(args[0],args[1]))
        self.metaBlockList.remove(args[0])
        self.ExpectedHybridBlockCount = self.ExpectedHybridBlockCount - 1      

    # @brief  A waypoint callback 
    # @details HybridBlockEviction Waypoint
    # @return None
    # @exception: None  
    def OnHybridBlockEvictionStart(self):
        self.__EvictionStart = True
        return True

    # @brief  A waypoint callback 
    # @details HYBRID_BLCOK_URGENT_FOLDING Waypoint
    # @return None
    # @exception: None      
    def OnHybridBlockUrgentCompaction(self):
        self.__UrgentCompactionStarted = True
        return True

    # @brief  A waypoint callback 
    # @details COMPACTION_BEGIN Waypoint
    # @return None
    # @exception: None        
    def OnHybridBlockUrgentCompactionStart(self):
        self.UrgnetCompactionstart = True  

    # @brief  A waypoint callback 
    # @details COMPACTION_COMPLETE Waypoint
    # @return None
    # @exception:          
    def OnHybridBlockUrgentCompactionCompleted(self):
        self.UrgnetCompactionCompleted = True  

    # @brief A punit style method that defines the actual logic of the test
    # @details
    # @return None
    # @exception: Throw exception  if there are 2 streams for Hybrid block writes    

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