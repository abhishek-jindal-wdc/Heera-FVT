#"""
#********************************************************************************
    # @file       : HBD10_HybridBlockEviction.py
    # @brief      : The test is designed to check Hybrid Block eviction
    # @author     : Komala Nataraju
    # @date       : 28 APR 2020
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
import CTFServiceWrapper as PyServiceWrap

#FVT Imports goes here
import GlobalVars as GlobalVars
from Constants import StreamTypes as ST


# @brief A class as a structure for HBD10 Test
# @details Test scope is to check Hybrid blocks eviction
class HBD10_HybridBlockEviction(TestCase.TestCase):
    
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
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()
	self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')

        self.__HDWMode = False
        self.__HybridSequentialMode = False
        self.__EvictionStart = False
    
        self.wayPointDict = {
            #"HYBRID_BLOCK_URGENT_COMPACTION_START"     : [self.OnHybridBlockUrgentCompaction],
            #"HYBRID_BLOCK_URGENT_COMPACTION_COMPLETE"  : [self.OnHybridBlockUrgentCompactionCompleted],
            "HYBRID_BLOCK_EVICTION_COMPLETE"           : [],
            "HYBRID_BLOCK_EVICTION_IN_PROGRESS"        : [],
            "HYBRID_BLOCK_EVICTION_START"              : [self.OnHybridBlockEvictionStart],
            "MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedToClosedHybridBlockList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBReleasedFromClosedHybridList],
            "READ_ONLY_MODE"                           : [],
            "SEQUENTIAL_MODE_SWITCH"                   : [],
            "UM_WRITE"                                 : [],
	    "EPWR_START"                 : [self.OnEPWRStart],
	    "EPWR_COMPLETE"              : [self.OnEPWRComplete],		    
            "GC_TASK_STARTED"                          : [],
	    "UM_BLOCK_ALLOCATION":[self.OnUmBlockAllocation],
	    "ITGC_START"                               : [self.OnITGCStart],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict)
	#MMP Support
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}	
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	else:
	    self.MaxMLCFreeCountMetaPlane=0	  	
	
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
	self.UMBlockAllocation=False        
       
	  	
	
	
        #self.globalVarsObj.printWaypointArgs = False
                
        #Get eviction threshold from File 21
        File21Obj = FileData.ConfigurationFile21Data(self.vtfContainer)
        FileID = 21
        Offset = 0x1DE  #Eviction threshold offset
        File21Size = self.sctpUtilsObj.GetFileSize(FileID)
        File21Buffer = self.sctpUtilsObj.GetReadFileBuf(FileID) 
        self.__evictionThreshold = File21Buffer.GetTwoBytesToInt(Offset)  
	self.currentMLCFreeCount = self.sctpUtilsObj.GetMLCFreeCount()
        #Tweaking eviction threshold for testing
	self.sctpUtilsObj.WriteConfigFile(FileID, Offset, self.currentMLCFreeCount-6, 2)
        self.utilsObj.PowerCycle()
        File21Buffer = self.sctpUtilsObj.GetReadFileBuf(FileID)
        self.__newEvictionThreshold = File21Buffer.GetTwoBytesToInt(Offset)      

        File21Obj = FileData.ConfigurationFile21Data(self.vtfContainer)
        self.HybridBlockEvictionThreshold = File21Obj.HybridBlocksEvictionThreshold
    
        self.metaBlockList = []
        self.ExpectedHybridBlockCount = 1
        
    #--------------------------------------------------------------------------------    
    def testHBD10_HybridBlockEviction(self):
	self.ccmObj.SetLbaTracker()
        self.logger.Info(self.globalVarsObj.TAG, "...Writing data sequentially till Eviction triggers...")
        self.executedWrites = []
        sectorsWritten = 0
        reachedEndRange = False
        self.amountOfData = self.HybridBlockEvictionThreshold  # Eviction Threshold
        self.logger.Info(self.globalVarsObj.TAG, "Hybrid Block Eviction Threshold: 0x%X" % self.HybridBlockEvictionThreshold)
    
        if self.globalVarsObj.vtfContainer.cmd_line_args.startLba == None:
            self.currSector = self.accessPatternObj.GetRandomStartLba(self.lbaRange, self.alignment)
        else:
            self.currSector = self.startLba
        self.sizeInSectors = self.amountOfData * 1024 * 1024 * 2
        self.endOfSector =  self.currSector + self.sizeInSectors
    
        self.accessPatternObj.LogStartEndSector(self.currSector, min(self.endOfSector, self.endLba), self.sizeInSectors)
        
        self.blockWritten = 0
	#newMLCCount = 0x100
        #self.sctpUtilsObj.SetMLCFreeCount(newMLCCount)
        #self.logger.Info("", "New MLC Free Count : %d" % newMLCCount)
        
        #currentMLCFreeCount = self.sctpUtilsObj.GetMLCFreeCount()
        blocksToWrite = self.currentMLCFreeCount - self.__newEvictionThreshold
        while (self.blockWritten <  blocksToWrite):
    
            txferLength = self.__fwConfigData.mlcMBSize
            currentMLCFreeCount = self.sctpUtilsObj.GetMLCFreeCount()
            # executing the writes
            if txferLength > 0:
                txferLength = self.__fwConfigData.metaPageSize * 8
                sectorsToWrite = self.__fwConfigData.mlcMBSize
                sectorsWritten = 0
                while sectorsWritten<sectorsToWrite:
		    if (self.__EvictionStart):
			break
                    if self.readWriteSelect in ("write", "both"):
                        self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
			self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
			if self.numberOfMetaPlane>1:
			    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
			else:
			    self.MaxMLCFreeCountMetaPlane=0	                          
                    self.executedWrites.append(( self.currSector, txferLength))
                    sectorsWritten += txferLength
                    self.currSector += txferLength 
                               
        if (self.__EvictionStart):
            self.logger.Info(self.globalVarsObj.TAG, "The eviction triggered as expected")
            
        else:
            self.logger.Info("", "The eviction is not triggered as expected")
            
        ## Issue writes to check the eviction 
        for i in range(0,5):
            txferLength = self.__fwConfigData.metaPageSize
            sectorsWritten=0
            sectorsToWrite=txferLength + 0x800
            while sectorsWritten<sectorsToWrite:
                self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		
		else:
		    self.MaxMLCFreeCountMetaPlane=0		
		
		
                self.currSector+=txferLength
                sectorsWritten+=txferLength
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)	
                
                
            #self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
            #self.currSector += txferLength   
            
    # @brief  A waypoint callback 
    # @details HybridBlockEviction Waypoint
    # @return None
    # @exception:     
    def OnHybridBlockEvictionStart(self, args):
            self.__EvictionStart = True
            return True
        
    #-------------------------------------------------------------------------------------
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
    #--------------------------------------------------------------------------------------------    
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
	    self.stream="Hybird"
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
#-------------------------------------------------------------------------------------------
    def OnMBAddedToClosedHybridBlockList(self, args):
        """
            MBAddress, ClosedHybridBlockCount
        """
        self.blockWritten = args["ClosedHybridBlockCount"] 
        return  
    
    def OnITGCStart(self, args):
	return
    def OnMBReleasedFromClosedHybridList(self, args):
	return
        
    #--------------------------------------------------------------------------------    
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