#
#********************************************************************************
    # @file       : HBD01_BasicTestCase.py
    # @brief      : The test is designed to check whether Hybrid blocks will be used for writing first 5GB to get
    #                the burst performance & HDW for the subsequent data to get the sustained sequential performance.
    # @author     : Komala Nataraju
    # @date 	  : 28 APR 2020
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


# @brief A class as a structure for HBD01 Test
# @details Test scope is to check Hybrid blocks will be used for writing first 5GB to get the burst performance
class HBD01_BasicTest(TestCase.TestCase):
    
    # @details Here we instantiate objects of GlobalVars and Common Code Manager modules.
    # Also read the input parameters from the XML Config file and assign it to local variables
    def setUp(self):
        # Call the base class setUp function.
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
        self.amountOfData    = self.currCfg.variation.amountOfData
        self.readWriteSelect = self.currCfg.variation.readWriteSelect        
        self.verifyMode      = self.currCfg.variation.verifyMode
        
        # For short stroking only. i.e. CMD Line: "--lbaRange=0-1024"
        self.startLba, self.endLba = self.utilsObj.AdjustStartAndEndLBA()
        self.lbaRange = [self.startLba, self.endLba]
        self.transferLength = self.__fwConfigData.sectorsPerSlcBlock

	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	        
        self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')
	#self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()       
        self.__HDWMode              = False
        self.__HybridSequentialMode = False
        self.__HDWSwitchHappened    = False
        self.ExpectedHybridBlockCount       = 1

        # Waypoints            
        self.wayPointDict = {
		    "HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
		    "HYBRID_BLOCK_REMOVED"                     : [self.OnHybridBlockRemoved],
		    "MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [],
		    "MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [],
		    "READ_ONLY_MODE"                           : [],
		    "SEQUENTIAL_MODE_SWITCH"                   : [self.OnSequentialModeSwitchBackFunc],
	            "UM_BLOCK_ALLOCATION"  :[self.OnUMBlockAllocation],
		    "UM_WRITE"                                 : [self.OnUmWrite],
	            "EPWR_START"                 : [self.OnEPWRStart],
	            "EPWR_COMPLETE"              : [self.OnEPWRComplete],	            
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict)           
        
	#mmp support
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}	
	
	self.globalVarsObj.printWaypointArgs = False
        self.CurrentMetaPlane=None

        self.NextMetaPlane=None	
	self.UMCount=0
	self.HybridStream=False
	self.HDWStreamSeq_0=False
	self.HDWStreamSeq_1=False
	self.UMBlockAllocation=False
	self.HDWBlkCountSeq_0=0
	self.HDWBlkCountSeq_1=0
	self.HybridBlkCount=0
	self.RandomBlkCount=0
	self.RandomStream=False
	self.GetMLCCount=True
	self.InvalidMB=0x3FFF
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	else:
	    self.MaxMLCFreeCountMetaPlane=0	
	
		
	
        
	
    def OnEPWRComplete(self,argsDict):
	if self.EPWRStart:
	    self.GetMLCCount=True
	    self.EPWRStart=False
	    

    def OnEPWRStart(self, argsDict):
	"""
	"Block", "Sector", "NumSectors", "MemoryAccess", "Requestor"
	"""
	
	
	self.EPWRStart=True        		                                   
    #--------------------------------------------------------------------------------------------------------------
    def testHBD01_BasicTest(self):
	
        self.logger.Info(self.globalVarsObj.TAG, "", "...Writing 5 GB data sequentially...")
		#self.WaypointRegObj.DisableWPprintFlag()	
        #import time
        #startTime = time.time()
        #self.utilsObj.InsertDelay(5000)
        #self.logger.Info("", "%s" % (time.time()-startTime))

        self.executedWrites = []
        sectorsWritten = 0
        reachedEndRange = False
        
        self.currSector = self.startLba
        self.sizeInSectors = 5 * 1024 * 1024 * 2
        self.endOfSector =  self.currSector + self.sizeInSectors
    
        self.accessPatternObj.LogStartEndSector(self.currSector, min(self.endOfSector, self.endLba), self.sizeInSectors)
    
        while sectorsWritten < self.sizeInSectors:
            txferLength = self.transferLength
    
            self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
	    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	    if self.numberOfMetaPlane>1:
		self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	    else:
		self.MaxMLCFreeCountMetaPlane=0	    
            self.executedWrites.append(( self.currSector, txferLength))
            sectorsWritten += txferLength
            self.currSector += txferLength 
			
            self.logger.Info(self.globalVarsObj.TAG, "Percent Write completed(in GB): %s" % 
								 format(float(sectorsWritten)/(Constants.SectorsPerGB), '.8f'))				

            if (self.__HDWMode or self.__HDWSwitchHappened):
				raise ValidationError.TestFailError("", "The Stream is changed to HDW before reaching 5 GB. Current Hybrid Block Count = %d" %
										                (self.ExpectedHybridBlockCount))
						
        self.logger.Info(self.globalVarsObj.TAG, "...Completed writing 5 GB data...")  
        
        ## Issue writes to check the Stream Change           
        while self.UMCount != self.ThresholdMaxLimitOfHybridBlocks+1:
            txferLength = txferLength + 0x800
            self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
	    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	    if self.numberOfMetaPlane>1:
		self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	    else:
		self.MaxMLCFreeCountMetaPlane=0                        
            self.currSector += txferLength
        
        if (self.__HDWMode or self.__HDWSwitchHappened):
            self.logger.Info("", "The Stream changed to HDW after 5GB writes as expected")
        else:
            raise ValidationError.TestFailError("", "The Stream not changed to HDW after 5GB writes as expected")
    
        #verification is done with reads
        if not self.verifyMode == Constants.IMMEDIATE_VERIFY and self.readWriteSelect in ("read", "both"):
            self.accessPatternObj.VerifyModes(self.verifyMode, self.executedWrites)

        self.logger.Info(self.globalVarsObj.TAG, "", "Completed %s Variation of the test" % self.variationName)
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)		
		
    #-------------------------------------------------------------------------------------
    
    def OnUMBlockAllocation(self,args):
	""" 
	    "StreamType","StreamID","PrimaryMB","SecondaryMB","SecondaryMB[2]","SecondaryMB[3]"
	"""
	
	#arguments 
	self.UMBlockAllocation =True
	self.UMCount+=1
	self.PriMB=args['PrimaryMB'] 
	self.SecMB=args['SecondaryMB']
	self.SecondSecMB=args['SecondaryMB[2]']
	self.ThirdSecMB=args['SecondaryMB[3]']	
	
	#mmp support
	self.PriMBMetaplane= self.PriMB  % self.numberOfMetaPlane
	self.SecMBMetaplane=self.SecMB % self.numberOfMetaPlane
        self.CurrentMetaPlane=self.PriMBMetaplane
        self.logger.Info("","Block Allocated from MetaPlane %d " % self.CurrentMetaPlane)
        self.logger.Info("","UM_Block_ALLOACTION  Count %d" %  self.UMCount)	
	if args["StreamType"] == Constants.StreamTypes.STREAM_HOST_SEQUENTIAL and not self.HostBlkDict.has_key(self.PriMB) :
	    if  args["StreamID"]==0:	
		
		self.HDWStreamSeq_0 =True
		self.HDWBlkCountSeq_0+=1
		self.stream="HDW "
		self.count=self.HDWBlkCountSeq_0
		self.blktype=True
	    else:
		self.HDWStreamSeq_1 =True
		self.HDWBlkCountSeq_1+=1
		self.stream="HDW" 
		self.count=self.HDWBlkCountSeq_1	
		self.blktype=True
	if args["StreamType"] == ST.STREAM_HOST_SEQUENTIAL_HYBRID_BLOCK:
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
	    self.blktype=self.RandomBlkCount
	    		    
	    
	
	#Host block Dictionary , primary ->secondary mapping 
	if not self.HostBlkDict.has_key(self.PriMB):
	    self.HostBlkDict[self.PriMB]=[self.SecMB]
    
	if self.SecondSecMB!=self.InvalidMB and self.SecondSecMB not in self.HostBlkDict[self.PriMB ] :
	    self.HostBlkDict[self.PriMB].append(self.SecondSecMB)
    
	if self.ThirdSecMB!=self.InvalidMB and  self.ThirdSecMB not in self.HostBlkDict[self.PriMB]:
	    self.HostBlkDict[self.PriMB].append(self.ThirdSecMB)                                                                                

	self.ccmObj.VerifyBlockAllocation(stream=self.stream, count=self.count, CurrentMetaPlane=self.CurrentMetaPlane,MLCFreecountPerMP=self.MLCFreeCountForMMP, MaxMLCFreeCountMetaPlane=self.MaxMLCFreeCountMetaPlane,fwConfig=self.__fwConfigData,Blktype=self.blktype)
        self.blktype=False
	    
    def OnSequentialModeSwitchBackFunc(self, args):
        self.__HDWSwitchHappened = True
        return True
    
    #-------------------------------------------------------------------------------------    
    def OnUmWrite(self, args):
        """
        Args: "Bank","LG","LGOffset","transferLength","StreamType","StreamID","MB","MBOffset","primary"
        """
        if (args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_HYBRID ):
            self.__HybridSequentialMode = True
        if (args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_SEQUENTIAL_0 or 
		    args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_SEQUENTIAL_1 ): ## HDW write
            self.__HDWMode = True
        return True    

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

	#--------------------------------------------------------------------------------------
    def tearDown(self):
	self.ccmObj.DataVerify()
    	if self.globalVarsObj.manualDoorbellMode:
    		tempAvailableSQList = list(set(self.ccmObj.usedSQIDs))

    		for tempSqID in tempAvailableSQList:
    			self.ccmObj.RingDoorBell(tempSqID)
    		status = self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762

    		if status == False:
    			raise ValidationError.CVFGenericExceptions(self.variationName, 'WaitForCompletion Failed')
    	self.utilsObj.DrawGraph(self.variationName)
    	self.utilsObj.CalculateStatistics()
    	super(type(self), self).tearDown()	