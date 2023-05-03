#
#********************************************************************************
    # @file       : HBD11_SeqWritesAfterHybridEviction.py
    # @brief      : The test performs Sequential Writes untill all Hybrid Blocks are consumed.
    #               Forces Hybrid Eviction and continues Sequential writes on HDW.
    #               Checks if HDW Free block count decrementes for every new block allocated.
    #
    # @author     : Aarshiya Khandelwal
    # @date       : 22 APR 2021
    # @copyright  : Copyright (C) 2020 SanDisk Corporation
#********************************************************************************
#--------------------------------------------------------------------------------
# Updated for Testing on Heera CVF    -     Aarshiya Khandelwal   -   Apr 22 2021
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
class HBD11_SeqWritesAfterHybridEviction(TestCase.TestCase):
    
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
	
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	        
        self.MaxHybridBlocks = self.__file14Object.get('numOfHybridBlocks')          
        #self.MaxHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.MaxMLCFreeCount = self.sctpUtilsObj.GetMLCFreeCount()
        self.__HDWMode              = False
        self.__HybridSequentialMode = False
        self.__HDWSwitchHappened    = False
        self.writtenMBList          = []
        self.HDWBlockAllocationCount = 0
        self.HybridBlockAllocationCount = 0

        # Waypoints            
        self.wayPointDict = {
            "UM_BLOCK_ALLOCATION"                      : [self.OnUMBlockAllocation],
            "HYBRID_BLOCK_EVICTION_COMPLETE"           : [],
            "HYBRID_BLOCK_EVICTION_IN_PROGRESS"        : [],
            "HYBRID_BLOCK_EVICTION_START"              : [],
            "SEQUENTIAL_MODE_SWITCH"                   : [self.OnSequentialModeSwitchBackFunc],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict)      
	#MMP Support
	self.MMP=self.vtfContainer.cmd_line_args.mmp
	self.numberOfMetaPlane=self.__fwConfigData.numberOfMetaPlane
	self.HostBlkDict={}	
        
    #-------------------------------------------------------------------------------------
    def testHBD11_SeqWritesAfterHybridEviction(self):
        self.logger.Info(self.globalVarsObj.TAG, "", "Performing Sequential Writes")
        randomLG       = self.globalVarsObj.randomObj.randint(0, self.__fwConfigData.lgsInCard)
        startLba       = randomLG * self.__fwConfigData.sectorsPerLg         
        sectorsWritten = 0
        sectorsToWrite = self.__fwConfigData.mlcMBSize
        transferlength = 0x800
        
        currentMLCFreeCount = self.sctpUtilsObj.GetMLCFreeCount()
        MLCBlocksToWrite    = self.MaxMLCFreeCount*3/4 # (Writes upto 25% blocks written, 75% free)
        
        while currentMLCFreeCount > MLCBlocksToWrite:
            sectorsWritten = 0
            currentMLCFreeCount = self.sctpUtilsObj.GetMLCFreeCount()
            self.logger.Info("", "Current MLC Free Count: %d" % currentMLCFreeCount)
            while sectorsWritten < sectorsToWrite:
                # Perform Writes
                self.ccmObj.Write(startLba, transferlength)
                sectorsWritten += transferlength
                startLba += transferlength 
                
                if (self.__HDWMode or self.__HDWSwitchHappened):
                    self.logger.Info("", "Force Hybrid Eviction")
                    self.sctpUtilsObj.ForceHybridEviction()
            self.logger.Info("", "Current MLC Free Count: %d | HDW Block Allocation Count: %d" % 
                             (currentMLCFreeCount, self.HDWBlockAllocationCount))
	    
	if self.MMP:
	    try:
		self.utilsObj.MetaPlaneVerification(HostBlkDict=self.HostBlkDict, noOfMMP=self.numberOfMetaPlane)
	    except Exception as e:
		raise (e)	
        
        return
                                
    #-------------------------------------------------------------------------------------
    def OnSequentialModeSwitchBackFunc(self, args):
        self.__HDWSwitchHappened = True
        return True
    
    #-------------------------------------------------------------------------------------    
    def OnUMBlockAllocation(self, args):
        """ 
        "StreamType","StreamID","PrimaryMB","SecondaryMB","SecondaryMB[2]","SecondaryMB[3]"
        """
	if not self.HostBlkDict.has_key(args['PrimaryMB'] ):
	    self.HostBlkDict[args['PrimaryMB']]=[args['SecondaryMB']]
    
	if args['SecondaryMB[2]']!=0x3FFF and args['SecondaryMB[2]'] not in self.HostBlkDict[args['PrimaryMB'] ] :
    
	    self.HostBlkDict[args['PrimaryMB']].append(args['SecondaryMB[2]'])
    
    
    
	if args['SecondaryMB[3]']!=0x3FFF and  args['SecondaryMB[3]'] not in self.HostBlkDict[args['PrimaryMB']]:
	    self.HostBlkDict[args['PrimaryMB']].append(args['SecondaryMB[3]'])   	
        # Block Allocation matches Variation Stream
        if args["StreamType"] == ST.STREAM_HOST_SEQUENTIAL:
            if args["PrimaryMB"] not in self.writtenMBList:
                self.HDWBlockAllocationCount += 1
                self.writtenMBList.append(args["PrimaryMB"])            
                self.__HDWMode = True
                self.logger.Info("", "HDW Block Allocation Count : %d" % self.HDWBlockAllocationCount)
                
        #if args["StreamType"] == ST.STREAM_HOST_SLC_RANDOM and self.stream=='Random':
            #self.blockAllocationCount += 1  
            #if args["PrimaryMB"] not in self.writtenMBList:
                #self.currentMLCCount += 1
                #self.writtenMBList.append(args["PrimaryMB"])              

        if args["StreamType"] == ST.STREAM_HOST_SEQUENTIAL_HYBRID_BLOCK:
            if args["PrimaryMB"] not in self.writtenMBList:
                self.HybridBlockAllocationCount += 1
                self.writtenMBList.append(args["PrimaryMB"]) 
                self.logger.Info("", "Hybrid Block Allocation Count : %d" % self.HybridBlockAllocationCount)

    #--------------------------------------------------------------------------------------
    def tearDown(self):
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