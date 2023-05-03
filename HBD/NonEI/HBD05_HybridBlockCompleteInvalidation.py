#"""
#************************************************************************************************************************
    # @file       : HBD05_HybridBlockCompleteInvalidation.py
    # @brief      : The test is designed to check whether there is burst Performance when we write same 5GB data 3 times
    # @author     : Komala Nataraju
    # @date 	  : 30 APR 2020
    # @copyright  : Copyright (C) 2020 SanDisk Corporation
#************************************************************************************************************************
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


# @brief A class as a structure for HBD05_HybridBlockCompleteInvalidation Test
# @details Test scope is to check Hybrid blocks will be used for writing same 5GB data 3 times
class HBD05_HybridBlockCompleteInvalidation(TestCase.TestCase):
    
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
		self.WaypointRegObj   = self.globalVarsObj.WayPointObj
		self.__fileObject = FileData.FileData(self.vtfContainer)  
		self.__file14Object = self.__fileObject.GetFile14Data()	
		self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')
							
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
	
		#self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
	
		self.__HDWMode = False
		self.__HybridSequentialMode = False
		self.__HDWSwitchHappened = False
		self.firstHybridBlockRemoved = False
	
		self.wayPointDict = {
			"MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedToClosedHybridList],
			"MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [self.OnMBRemovedFromClosedHybridList],
			"READ_ONLY_MODE"                           : [],
			"SEQUENTIAL_MODE_SWITCH"                   : [self.OnSequentialModeSwitchBackFunc],
			"UM_WRITE"                                 : [self.OnUmWrite],
		        "EPWR_START"                 : [self.OnEPWRStart],
		        "EPWR_COMPLETE"              : [self.OnEPWRComplete],		
		        
		        "GC_TASK_STARTED"                          : [],
			"HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
		         "UM_BLOCK_ALLOCATION"                     :[self.OnUmBlockAllocation],
			"HYBRID_BLOCK_REMOVED"                     : [self.OnHybridBlockRemoved],			
		}
		self.WaypointRegObj.RegisterWP(self.wayPointDict) 
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
		self.UMBlockAllocation=False
		self.GetMLCCount=True	
		self.InvalidMB=0x3FFF
		self.HybridStream=False	
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		else:
		    self.MaxMLCFreeCountMetaPlane=0		
		
		self.metaBlockList = []
		self.ExpectedHybridBlockCount = 1 #First hybrid is allocated during DLE hence waypoint for that won't hit.
		self.WaypointReturnedHybridBlockCount = 1 #First hybrid is allocated during DLE hence waypoint for that won't hit.
		self.WaypointReturnedClosedHybridBlockCount = 0
		self.ExpectedClosedHybridBlockCount = 0
    def OnEPWRComplete(self,argsDict):
	if self.EPWRStart:
	    self.GetMLCCount=True
	    self.EPWRStart=False
	    
#-----------------------------------------------------------------------------------------
    def OnEPWRStart(self, argsDict):
	"""
	"Block", "Sector", "NumSectors", "MemoryAccess", "Requestor"
	"""
	
	
	self.EPWRStart=True   			
	#-----------------------------------------------------------------------------
    def testHBD05_HybridBlockCompleteInvalidation(self):
		#self.logger.Info("", "Hybrid Block Eviction Threshold: 0x%X" % self.HybridBlockEvictionThreshold)
	        self.ccmObj.SetLbaTracker()
		self.logger.Info(self.globalVarsObj.TAG, "...Writing 5 GB data sequentially ...")

		self.executedWrites = []
		sectorsWritten = 0
		reachedEndRange = False
	
		self.currSector = self.accessPatternObj.GetRandomStartLba(self.lbaRange, self.alignment)
		self.sizeInSectors = 5 * 1024 * 1024 * 2 # Sectors in 5GB 
		self.endOfSector =  self.currSector + self.sizeInSectors
	
		self.accessPatternObj.LogStartEndSector(self.currSector, min(self.endOfSector, self.endLba), self.sizeInSectors)
	
		while sectorsWritten < self.sizeInSectors:
	
			# obtaining the updated transer length
			txferLength = self.accessPatternObj.GetAlignedTransferLength(self.accessPatternObj.GetTransferLength(self.transferLengthMode), self.alignment)
			if self.MMP:
			    txferLength=0x100
			    
                        #if transfer length is greater than 0x80 then the stream is in Hybrid sequential stream.
			#Here if transferlength is greater than 0x80 then only allowings writes 
			#by doing these to make sure stream is in Hybrid sequenital           			
			if txferLength > 0x80:
			    txferLength = min(txferLength, self.endLba-self.currSector, self.sizeInSectors-sectorsWritten)
			    
			    # executing the writes
			    if txferLength > 0:
				    self.accessPatternObj.PerformWrites(self.verifyMode, self.currSector, txferLength)
				    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
				    if self.numberOfMetaPlane>1:
					self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
				    else:
					self.MaxMLCFreeCountMetaPlane=0								    
				    # Check if number of hybrid blocks added exceeds max limit of hybrid block
				    if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxLimitOfHybridBlocks:
					    raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
						                                    (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxLimitOfHybridBlocks))
			    
				    # Check if number of closed hybrid blocks returned by waypoint matches expected closed hybrid block count
				    elif self.ExpectedClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
					    raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
						                                                    (self.ExpectedClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))
				    # PASS		                        
				    else:
					    self.logger.Info("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
						                                                            (self.ExpectedClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
						    
				    self.executedWrites.append(( self.currSector, txferLength))
				    sectorsWritten += txferLength
				    self.currSector += txferLength  
				    self.logger.Info(self.globalVarsObj.TAG, "Percent Write completed(in GB): %s" % 
					                         format(float(sectorsWritten)/(Constants.SectorsPerGB), '.8f'))				

			if (self.__HDWMode or self.__HDWSwitchHappened):
				raise ValidationError.TestFailError(self.globalVarsObj.TAG, "The Stream is changed to HDW before 5GB Writes")

		self.logger.Info(self.globalVarsObj.TAG, "...Completed writing 5 GB data...")  
		
		self.logger.Info(self.globalVarsObj.TAG, "...Writing same 5GB data two more times to check the Burst Performance...") 
		for i in range(0,2):
			self.logger.Info("", "-"*100)
			self.logger.Info("", "Hybrid Invalidation Count: %d" % i)
			self.logger.Info("", "-"*100)
			for lba in self.executedWrites:
				self.accessPatternObj.PerformWrites(Constants.DO_NOT_VERIFY,lba[0], lba[1])
				self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
				if self.numberOfMetaPlane>1:
				    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
				else:
				    self.MaxMLCFreeCountMetaPlane=0			
				# Check if number of hybrid blocks added exceeds max limit of hybrid block
				if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxLimitOfHybridBlocks:
					raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
									                (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxLimitOfHybridBlocks))
			
				# Check if number of closed hybrid blocks returned by waypoint matches expected closed hybrid block count
				elif self.ExpectedClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
					raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
									                    (self.ExpectedClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))
				# PASS
				else:
					self.logger.Info("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
																	(self.ExpectedClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
										
				if ((self.__HDWSwitchHappened or self.__HybridSequentialMode)):
						raise ValidationError.TestFailError(self.globalVarsObj.TAG,"The Stream changed to HDW before writing 5GB writes")				
		
		# Perform Sequential write to check Stream switched to Sequential after Hybrid invalidation
		self.logger.Info("", "-"*100)
		self.logger.Info("", "Performing Sequential Write on random lba to check Sequential Stream Switch!")
		self.logger.Info("", "-"*100)
				
		startlba = self.globalVarsObj.randomObj.randint(0, self.__fwConfigData.maxLba)
		transferlength = 0x100
		self.ccmObj.Write(startlba, transferlength)
		self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
		if self.numberOfMetaPlane>1:
		    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
		else:
		    self.MaxMLCFreeCountMetaPlane=0		
		
		
		## Verify Stream Change
		#if (self.__HDWSwitchHappened or self.__HybridSequentialMode):
			#self.logger.Info(self.globalVarsObj.TAG, "The Stream changed to HDW after 5GB writes as expected")
		#else:
			#raise ValidationError.TestFailError(self.globalVarsObj.TAG,"The Stream not changed to HDW after 5GB writes!")
		
		#verification is done with reads
		if not self.verifyMode == Constants.IMMEDIATE_VERIFY and self.readWriteSelect in ("read", "both"):
			self.accessPatternObj.VerifyModes(self.verifyMode, self.executedWrites)

		self.logger.Info(self.globalVarsObj.TAG, self.globalVarsObj.TAG, "Completed %s Variation of the test" % self.variationName) 
		if self.MMP:
		    try:
			self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
		    except Exception as e:
			raise (e)				
				
	# @brief  A waypoint callback 
	# @details This waypoint hit when the stream changed from HybridSequential to HDW
	# @return None
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
	    self.count=self.RandomBlkCount
	    self.blktype=True
	
	    
	#Host block Dictionary ,  primary ->secondary mapping 
	if not self.HostBlkDict.has_key(self.PriMB):
	    self.HostBlkDict[self.PriMB]=[self.SecMB]
    
	if self.SecondSecMB!=self.InvalidMB and self.SecondSecMB not in self.HostBlkDict[self.PriMB] :
	    self.HostBlkDict[self.PriMB].append(self.SecondSecMB)
    
    
	if self.ThirdSecMB!=self.InvalidMB and  self.ThirdSecMB not in self.HostBlkDict[self.PriMB]:
	    self.HostBlkDict[self.PriMB].append(self.ThirdSecMB)     
	self.ccmObj.VerifyBlockAllocation(stream=self.stream, count=self.count, CurrentMetaPlane=self.CurrentMetaPlane,MLCFreecountPerMP=self.MLCFreeCountForMMP, MaxMLCFreeCountMetaPlane=self.MaxMLCFreeCountMetaPlane,fwConfig=self.__fwConfigData,Blktype=self.blktype)
	self.blktype=False

        
	
    def OnSequentialModeSwitchBackFunc(self, args):
		self.__HDWSwitchHappened = True
		return True

	# @brief  A waypoint callback 
	# @details UMWrite Waypoint
	# @return None
	# @exception:     

    def OnUmWrite(self, args):
		if (args["StreamType"] == Constants.StreamTypes.STREAM_HOST_SEQUENTIAL): ## HDW write
			self.__HDWMode = True
		return True    
			
    #------------------------------------------------------------------------------------
    def OnHybridBlockAdded(self, args):
	"""
	Args: "Bank", "MBAddress", "HybridBlockCount", "StreamID"
	"""
	self.ExpectedHybridBlockCount += 1  
	self.metaBlockList.append(args["MBAddress"])
	self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
	# Check if new Hybrid Block Count is one more than last Closed Hybrid Block Count
	if self.WaypointReturnedHybridBlockCount != (self.ExpectedClosedHybridBlockCount + 1):
		raise ValidationError.TestFailError("", "Last Closed Hybrid Block Count: %d. Expected New Hybrid Block Count: %d, Received New Hybrid Block Count: %d" %
					                            (self.ExpectedClosedHybridBlockCount, self.ExpectedClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
		
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
    def OnMBRemovedFromClosedHybridList(self, args):
	"""
	Args: "MBAddress", "ClosedHybridBlockCount"
	"""
	self.GetMLCCount=True
	self.ExpectedClosedHybridBlockCount -= 1	
	self.WaypointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"]
	return	
	
	#------------------------------------------------------------------------------------
    def OnMBAddedToClosedHybridList(self, args):
		"""
		Args: "MBAddress", "ClosedHybridBlockCount"
		"""	
		self.ExpectedClosedHybridBlockCount += 1
		self.WaypointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"]
	
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