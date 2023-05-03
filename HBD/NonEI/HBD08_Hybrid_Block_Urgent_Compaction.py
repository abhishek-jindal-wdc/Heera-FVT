#"""
#********************************************************************************
    # @file       : HBD08_Hybrid_Block_Urgent_Compaction.py
    # @brief      : The test is designed to check Hybrid Block Urgent Compaction
    # @author     : Komala Nataraju
    # @date 	  : 30 APR 2020
    # @copyright  : Copyright (C) 2020 SanDisk Corporation
#********************************************************************************
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


# @brief A class as a structure for HBD08_Hybrid_Block_Urgent_Compaction Test
# @details Test scope is to check Hybrid blocks eviction
class HBD08_Hybrid_Block_Urgent_Compaction(TestCase.TestCase):
    
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
	
		self.__HDWMode = False
		self.__HybridSequentialMode = False
		self.__HDWSwitchHappened = False
	
		self.wayPointDict = {
			"HYBRID_BLOCK_EVICTION_COMPLETE"           : [],
			"HYBRID_BLOCK_EVICTION_IN_PROGRESS"        : [],
			"HYBRID_BLOCK_EVICTION_START"              : [self.OnHybridBlockEvictionStart],
			"MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedtoClosedHBDList],
			"MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBReleasedfromClosedHBDList],
			"READ_ONLY_MODE"                           : [],
			"SEQUENTIAL_MODE_SWITCH"                   : [],
			"UM_WRITE"                                 : [],
		        "UM_BLOCK_ALLOCATION"                     :[self.OnUmBlockAllocation],
			"GC_TASK_STARTED"                          : []
		}
		self.WaypointRegObj.RegisterWP(self.wayPointDict) 
		# Config File Params
		#File14Buf = FileData.FileData.GetFile14Data(self.vtfContainer)
		File21Obj = FileData.ConfigurationFile21Data(self.vtfContainer)
		#MaxLimitOfHybridBlocks = File14Buf["numOfHybridBlocks"] 
		HybridBlockEvictionThreshold = File21Obj.HybridBlocksEvictionThreshold
		#MMP Support
		self.MMP=self.vtfContainer.cmd_line_args.mmp
		self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
		self.HostBlkDict={}		
	
		self.metaBlockList = []
		self.ExpectedHybridBlockCount = 1
    
            
    def OnMBAddedtoClosedHBDList(self, args):
		self.logger.Info(self.globalVarsObj.TAG, "MB_ADDED_TO_CLOSED_HYBRID_LIST waypoint is Hit: MBA=%d, hybridITGCCount=%d"%(args[0],args[1]))
		self.metaBlockList.append(args[0])
		self.ExpectedHybridBlockCount = self.ExpectedHybridBlockCount + 1  
	    
   
    def OnMBReleasedfromClosedHBDList(self, args):
		self.logger.Info(self.globalVarsObj.TAG, "MB_RELEASED_FROM_CLOSED_HYBRID_LIST waypoint is Hit: MBA=%d, hybridITGCCount=%d"%(args[0],args[1]))
		self.metaBlockList.remove(args[0])
		self.ExpectedHybridBlockCount = self.ExpectedHybridBlockCount - 1      
    
    def OnHybridBlockEvictionStart(self, args):
		self.__EvictionStart = True
		return True
	         
    def OnHybridBlockUrgentCompaction(self, args):
	        self.__UrgentCompactionStarted = True
	        return True
	             
    def OnHybridBlockUrgentCompactionCompleted(self, args):
	        self.UrgnetCompactionCompleted = True    

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

	#-------------------------------------------------------------------------------------
    def testHBD08_Hybrid_Block_Urgent_Compaction(self):
	self.ccmObj.SetLbaTracker()
        self.logger.Info(self.globalVarsObj.TAG, "...Writing data sequentially till Eviction triggers...")
        self.executedWrites = []
        sectorsWritten = 0
        reachedEndRange = False
    
        if self.globalVarsObj.vtfContainer.cmd_line_args.startLba == None:
            self.currSector = self.accessPatternObj.GetRandomStartLba(self.lbaRange, self.alignment)
        else:
            self.currSector = self.startLba
        self.sizeInSectors = self.ThresholdMaxLimitOfHybridBlocks * self.__fwConfigData.sectorsPerSlcBlock  
        self.endOfSector =  self.currSector + self.sizeInSectors
    
        self.accessPatternObj.LogStartEndSector(self.currSector, min(self.endOfSector, self.endLba), self.sizeInSectors)
    
        while (sectorsWritten < self.sizeInSectors):
    
            # obtaining the updated transer length
            txferLength = self.accessPatternObj.GetAlignedTransferLength(self.accessPatternObj.GetTransferLength(self.transferLengthMode), self.alignment)
            txferLength = min(txferLength, self.endLba-self.currSector, self.sizeInSectors-sectorsWritten)
    
            # executing the writes
            if txferLength > 0:
                if self.readWriteSelect in ("write", "both"):
                    self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
                self.executedWrites.append(( self.currSector, txferLength))
                sectorsWritten += txferLength
                self.currSector += txferLength  
    
    
        ## Issue writes to check the Urgent compaction 
        for i in range(0,5):
            txferLength = txferLength + 0x800
            self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
            self.currSector += txferLength
            
        if (self.__UrgentCompactionStarted):
            self.logger.Info(self.globalVarsObj.TAG, "The Urgent compaction triggered as expected")
            
        else:
            raise ValidationError.TestFailError("The Urgent compaction not triggered as expected")
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)  	
            
        ## Verify all the Hybrid blocks are compacted and released to MLC Pool
        if self.UrgnetCompactionCompleted :
            if self.ExpectedHybridBlockCount > 0:
                raise ValidationError.TestFailError("All the Hybrid Blocks are not released after the Urgent Compaction")
            else:
                self.logger.Info(self.globalVarsObj.TAG, "All the Hybrid Blocks are released after the Urgent Compaction")
    #_-------------------------------------------------------------------------------------
    def OnUmBlockAllocation(self,args):
	
	if not self.HostBlkDict.has_key(args['PrimaryMB'] ):
	    self.HostBlkDict[args['PrimaryMB']]=[args['SecondaryMB']]
    
	if args['SecondaryMB[2]']!=0x3FFF and args['SecondaryMB[2]'] not in self.HostBlkDict[args['PrimaryMB'] ] :
    
	    self.HostBlkDict[args['PrimaryMB']].append(args['SecondaryMB[2]'])
    
    
