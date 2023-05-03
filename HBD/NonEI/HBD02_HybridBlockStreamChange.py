#"""
#********************************************************************************
    # @file       : HBD02_HybridBlockStreamChange.py
    # @brief      : The test is designed to check correct Stream change for Hybrid sequential and Random writes
    # @author     : Komala Nataraju
    # @date       : 04 MAY 2020
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

# @brief A class as a structure for HBD02_HybridBlockStreamChange Test
# @details Test scope is to check stream change between Hybrid Sequential and random stream
class HBD02_HybridBlockStreamChange(TestCase.TestCase):

    # @details Here we instantiate objects of GlobalVars and Common Code Manager modules.
    # Also read the input parameters from the XML Config file and assign it to local variables
    #------------------------------------------------------------------------------------
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
        self.executedWrites = []
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	        
        self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')   
	#self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()

        self.__IsHybridStream     = False
        self.__IsRandomstream     = False
        self.__IsSequentialStream = False
        self.HybridBlockClosed    = False
        self.HybridBlockCount     = 1
        self.hybridBlock          = None
        self.ClosedHybridBlockCount = 0
        self.__HDWSwitchHappened  = False
        
        self.wayPointDict = {
            "HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED"                     : [],
            "MB_ADDED_TO_CLOSED_HYBRID_LIST"           : [self.OnMBAddedtoClosedHBDList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST"      : [],
            "READ_ONLY_MODE"                           : [],
            "SEQUENTIAL_MODE_SWITCH"                   : [self.OnSequentialModeSwitch],
	    "UM_BLOCK_ALLOCATION"                     :[self.OnUmBlockAllocation],
            "UM_WRITE"                                 : [self.OnUmWrite],
            'UM_READ'                                  : [],
	    "EPWR_START"                 : [self.OnEPWRStart],
	                     "EPWR_COMPLETE"              : [self.OnEPWRComplete],		    
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict) 
	#mmp support
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}	
	self.globalVarsObj.printWaypointArgs=False
	
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
    
    def OnEPWRComplete(self,argsDict):
	if self.EPWRStart:
	    self.GetMLCCount=True
	    self.EPWRStart=False
	    
    #----------------------------------------------------------------------------------------------------------------------
    def OnEPWRStart(self, argsDict):
	"""
	"Block", "Sector", "NumSectors", "MemoryAccess", "Requestor"
	"""
	
	self.EPWRStart=True        
     #-------------------------------------------------------------------------------------------------------------------
    
    def testHBD02_HybridBlockStreamChange(self):
        
        self.ccmObj.SetLbaTracker()
        self.logger.Info(self.globalVarsObj.TAG, "...Writing data sequentially...")
        self.sctpUtilsObj.SetMaxHybridBlockCount(2)
        newHybridCount = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.logger.Info("", "-"*100)
        self.logger.Info("", "New Max Hybrid Block Count = %d" % newHybridCount)
        self.logger.Info("", "-"*100)
        
        # Write half hybrid block
        self.currSector = self.globalVarsObj.randomObj.randint(0x1000, self.globalVarsObj.maxLba/2)
        transferlength = self.__fwConfigData.sectorsPerSlcBlock/2        
        self.ccmObj.Write(self.currSector, transferlength)
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	else:
	    self.MaxMLCFreeCountMetaPlane=0		

	
        self.executedWrites.append((self.currSector, transferlength))
        
        # Check if Hybrid write routed to random stream
        if not self.__IsHybridStream:        
            raise ValidationError.TestFailError(self.globalVarsObj.TAG, "Sequential writes not routed to Sequential Stream")
        else:
            self.logger.Info(self.globalVarsObj.TAG, "Sequential writes routed to Hybrid Stream as expected...")

        # Perform Random Write
        transferlength = 0x10
        # Choose random sector To avoid invalidation
        self.randomSector = self.globalVarsObj.randomObj.randint(0, self.currSector-0x10)
        self.ccmObj.Write(self.randomSector, transferlength)
	self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	if self.numberOfMetaPlane>1:
	    self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 	 #Metaplane with max MLC FreeBlk Count 	  
	else:
	    self.MaxMLCFreeCountMetaPlane=0		
	
        self.executedWrites.append((self.randomSector, transferlength))
        
        # Check if Random write routed to random stream
        if not self.__IsRandomstream:        
            raise ValidationError.TestFailError(self.globalVarsObj.TAG, "Random Writes not routed to Random Stream!")
        else:
            self.logger.Info(self.globalVarsObj.TAG, "Random writes routed to Random Stream as expected")
        
        # Write (hybrid blocks + 1) Sequentially to check Stream switch
        self.currSector = self.currSector + self.__fwConfigData.sectorsPerSlcBlock
        transferlength = self.__fwConfigData.sectorsPerSlcMetaBlock
        self.seqSector = self.globalVarsObj.randomObj.randint(self.currSector, self.globalVarsObj.maxLba)
        
        while self.ClosedHybridBlockCount < newHybridCount:
            self.ccmObj.Write(self.seqSector, transferlength)
	    self.MLCFreeCountForMMP=self.sctpUtilsObj.GetMLCFreeCount(self.numberOfMetaPlane)
	    if self.numberOfMetaPlane>1:
		self.MaxMLCFreeCountMetaPlane=self.MLCFreeCountForMMP.index(max(self.MLCFreeCountForMMP) ) 		    
	    else:
		self.MaxMLCFreeCountMetaPlane=0		    
	    
            self.executedWrites.append((self.seqSector, transferlength))
            self.seqSector += transferlength
            if self.__HDWSwitchHappened:
                break

        # Check if Sequential writes routed to Sequential Stream
        if not self.__IsSequentialStream:        
            raise ValidationError.TestFailError("", "Stream not switched to Sequential after Hybrid Block count crossed max count set in test")
        else:
            self.logger.Info(self.globalVarsObj.TAG, "Writes routed to Sequential stream after max hybrid count crossed.")
        
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)	    
    
    def OnUmBlockAllocation(self,args):
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
	if args["StreamType"] != Constants.StreamTypes.STREAM_HOST_SLC_RANDOM :
	    self.CurrentMetaPlane=self.PriMBMetaplane
        self.logger.Info("","Block Allocated from MetaPlane %d " % self.CurrentMetaPlane)
        self.logger.Info("","UM_Block_ALLOACTION Count %d" %  self.UMCount)	
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
	if not self.HostBlkDict.has_key(self.PriMB ):
	    self.HostBlkDict[self.PriMB]=[self.SecMB]
    
	if self.SecondSecMB!=self.InvalidMB and self.SecondSecMB not in self.HostBlkDict[self.PriMB ] :
	    self.HostBlkDict[self.PriMB].append(self.SecondSecMB)
    
    
	if self.ThirdSecMB!=self.InvalidMB and  self.ThirdSecMB not in self.HostBlkDict[self.PriMB]:
	    self.HostBlkDict[self.PriMB].append(self.ThirdSecMB)                                                                                

	self.ccmObj.VerifyBlockAllocation(stream=self.stream, count=self.count, CurrentMetaPlane=self.CurrentMetaPlane,MLCFreecountPerMP=self.MLCFreeCountForMMP, MaxMLCFreeCountMetaPlane=self.MaxMLCFreeCountMetaPlane,fwConfig=self.__fwConfigData,Blktype=self.blktype)
	self.blktype=False
	
    #------------------------------------------------------------------------------------        
    def OnSequentialModeSwitch(self, args):
        self.__HDWSwitchHappened = True
        return True
    
    #------------------------------------------------------------------------------------
    def OnUmWrite(self, args):
        if (args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_HYBRID):                   
            self.__IsHybridStream = True
        elif (args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_SEQUENTIAL_0 or 
              args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_SEQUENTIAL_1 ): 
            self.__IsSequentialStream = True
        elif(args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_RANDOM or
             args["StreamID"] == Constants.StreamIDs.STREAM_ID_HOST_RANDOM_INTERMEDIATE):                   ## Random write
            self.__IsRandomstream =True
        return True
        
    #------------------------------------------------------------------------------------
    def OnMBAddedtoClosedHBDList(self, args):
        """
        Args: ClosedHybridBlockCount
        """
        self.HybridBlockClosed = False
        self.ClosedHybridBlockCount = args["ClosedHybridBlockCount"]
        if args["MBAddress"] == self.hybridBlock:
            self.HybridBlockClosed = True
        return
        
    #------------------------------------------------------------------------------------
    def OnHybridBlockAdded(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount", "StreamID"
        """
        self.hybridBlock = args["MBAddress"]
        self.HybridBlockCount = args["HybridBlockCount"]
         
        return True
    
    #------------------------------------------------------------------------------------
    def tearDown(self):
        # Verify the data written
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