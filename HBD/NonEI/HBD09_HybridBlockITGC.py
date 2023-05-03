#"""
#********************************************************************************
    # @file       : HBD09_HybridBlockITGC.py
    # @brief      : The test is designed to check Hybrid Block ITGC
    # @author     : Komala Nataraju
    # @date       : 29 APR 2020
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
from Constants import StreamTypes as ST

##
# @brief A class as a structure for HBD09_HybridBlockITGC Test
# @details Test scope is to check whether the invalid blocks will be During idle time  
class HBD09_HybridBlockITGC(TestCase.TestCase):

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
        File21Obj             = FileData.ConfigurationFile21Data(self.vtfContainer)
                
    
        # Variation variables
        self.amountOfData       = self.currCfg.variation.amountOfData
        self.transferLength     = self.accessPatternObj.GetTransferLength(self.currCfg.variation.transferLengthMode)
        self.transferLengthMode = self.currCfg.variation.transferLengthMode
        self.alignment          = self.accessPatternObj.GetAlignment(self.currCfg.variation.alignmentMode, self.transferLength)
        self.readWriteSelect    = self.currCfg.variation.readWriteSelect
        self.verifyMode         = self.currCfg.variation.verifyMode
    
        # For short stroking only. i.e. CMD Line: "--lbaRange=0-1024"
        self.startLba, self.endLba = self.utilsObj.AdjustStartAndEndLBA()
        self.lbaRange              = [self.startLba, self.endLba]
        
        # Test Variables            
        self.HybridBlockEvictionThreshold    = File21Obj.HybridBlocksEvictionThreshold  
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	        
        self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')          
        #self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.ClosedMBList      = []
        self.ListOfCompactedMBs= []
        self.compactionStarted = False  
        self.ITGCStarted       = False
        self.ITGCStopped       = False
        self.ExpectedHybridBlockCount  = 1
        self.closedHybridBlockCount = 0
    
        self.wayPointDict = {
            "MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedtoClosedHBDList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBReleasedfromClosedHBDList],
            "READ_ONLY_MODE"                           : [],
            "SLC_COMPACTION_DATA_TRANSFER_BEGIN"       : [],
            "GC_TASK_STARTED"                          : [],
	    "EPWR_START"                 : [self.OnEPWRStart],
	    "EPWR_COMPLETE"              : [self.OnEPWRComplete],		    
            "MLC_COMPACTION_DATA_TRANSFER_BEGIN"       : [self.OnMLCCompactionDataTransferBegin],   
            "HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED"                     : [self.OnHybridBlockRemoved],
	    "UM_BLOCK_ALLOCATION":[self.OnUmBlockAllocation],
            "ITGC_START"                               : [self.OnITGCStart],
            "ITGC_STOP"                                : [self.OnITGCStop],         
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict) 

	#MMP Support
	self.MMP=self.vtfContainer.cmd_line_args.mmp
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
	self.GetMLCCount=True
	self.HybridStream=False	
	self.RandomStream=False
	self.UMBlockAllocation=False
	self.InvalidMB=0x3FFF	
	self.UMCount=0		
	self.UMBlockAllocation=False
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	else:
	    self.MaxMLCFreeCountMetaPlane=0	  	
	
 
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
    def testHBD09_HybridBlockITGC(self):
	self.ccmObj.SetLbaTracker()
        self.__transferLength = self.__fwConfigData.slcMBSize
        self.__startLba       = self.globalVarsObj.randomObj.randint(0, self.globalVarsObj.maxLba)
        self.__numWrites      = 0
        
        countOfHybridBlocksToWrite = self.globalVarsObj.randomObj.randint(3, self.ThresholdMaxLimitOfHybridBlocks)
       
        while (self.ExpectedHybridBlockCount < countOfHybridBlocksToWrite):
	    sectorsToWrite=0
	    sectorsWritten=self.__fwConfigData.slcMBSize
	    self.txlength=0x100
	    
	    while sectorsToWrite<sectorsWritten:
		
		if (self.__startLba +self.txlength) > self.globalVarsObj.maxLba:
		    self.__startLba = 0
		self.ccmObj.Write(self.__startLba, self.txlength)  
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		else:
		    self.MaxMLCFreeCountMetaPlane=0	  		
		
		sectorsToWrite+=self.txlength
		self.__startLba += self.txlength
            
        # Insert delay of 5 seconds
        delayTime = 5000
        if self.closedHybridBlockCount > 1:
            self.utilsObj.InsertDelay(delayTime)
        
        if self.ITGCStarted:
            self.logger.Info("", "Hybrid ITGC Trigerred after injecting delay!")
            if self.compactionStarted:
                self.logger.Info(self.globalVarsObj.TAG, "The compaction started during ITGC as expected")
            else:
                raise ValidationError.TestFailError("", "Compaction on Hybrid Stream has not triggered during ITGC. Current Closed Hybrid Block Count = %d" % self.closedHybridBlockCount)            
        else:
            raise ValidationError.TestFailError("", "ITGC did not start on giving %d milliseconds delay" % delayTime)
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)		
        
        return
    #-------------------------------------------------------------------------------------------                
    def OnMLCCompactionDataTransferBegin(self, args):
        self.compactionStarted = True
        if args["SrcMB"] in self.ClosedMBList:
            self.ListOfCompactedMBs.append(args["SrcMB"])   
        
        return
    
    #-------------------------------------------------------------------------------------------                 
    def OnMBAddedtoClosedHBDList(self, args):
        self.ClosedMBList.append(args['MBAddress'])
        self.closedHybridBlockCount = args["ClosedHybridBlockCount"]
        
        return
                        
    #-------------------------------------------------------------------------------------------                 
    def OnHybridBlockAdded(self, args):             
        self.ExpectedHybridBlockCount = self.ExpectedHybridBlockCount + 1  
        
        return
    
    #-------------------------------------------------------------------------------------------
    def OnMBReleasedfromClosedHBDList(self, args):
        #self.ClosedMBList.remove(args['MBAddress'])
        self.HybridBlockReleased = True
        return
    
    #-------------------------------------------------------------------------------------------
    def OnITGCStart(self, args):
        self.ITGCStarted = True
                
        return
            
    #-------------------------------------------------------------------------------------------                
    def OnITGCStop(self, args):
        self.ITGCStopped = True
        return
     
                
    #-------------------------------------------------------------------------------------------                 
    def OnHybridBlockRemoved(self, args):       
        self.ExpectedHybridBlockCount = self.ExpectedHybridBlockCount - 1  
        return
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
	    self.count=self.RandomBlkCount	
	    self.blktype=True
	
	
	#Host block Dictionary ,  primary ->secondary mapping 
	if not self.HostBlkDict.has_key(self.PriMB  ):
	    self.HostBlkDict[self.PriMB ]=[self.SecMB]
    
	if self.SecondSecMB!=self.InvalidMB and self.SecondSecMB not in self.HostBlkDict[self.PriMB  ] :  
	    self.HostBlkDict[self.PriMB ].append(self.SecondSecMB)
    
     
	if self.ThirdSecMB!=self.InvalidMB and  self.ThirdSecMB not in self.HostBlkDict[self.PriMB ]:
	    self.HostBlkDict[self.PriMB ].append(self.ThirdSecMB)                                                                                
        
	self.ccmObj.VerifyBlockAllocation(stream=self.stream, count=self.count, CurrentMetaPlane=self.CurrentMetaPlane,MLCFreecountPerMP=self.MLCFreeCountForMMP, MaxMLCFreeCountMetaPlane=self.MaxMLCFreeCountMetaPlane,fwConfig=self.__fwConfigData,Blktype=self.blktype)
        self.blktype=False
    
    #-------------------------------------------------------------------------------
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