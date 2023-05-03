#"""
#************************************************************************************************************************
    # @file       : HBD12_AppsCDMPattern.py
    # @brief      : The test is designed to check whether is burst Performance is met when we write 5GB data 3 times
    # @author     : Aarshiya Khandelwal
    # @date 	  : 25 August 2021
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


# @brief A class as a structure for HBD12_AppsCDMPattern Test
# @details Test scope is to check Hybrid blocks will be used for writing same 5GB data 3 times
class HBD12_AppsCDMPattern(TestCase.TestCase):

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
            "GC_TASK_STARTED"                          : [],
            "HYBRID_BLOCK_ADDED"                       : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED"                     : [self.OnHybridBlockRemoved],			
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict) 
        self.metaBlockList = []
        self.ExpectedHybridBlockCount = 1 #First hybrid is allocated during DLE hence waypoint for that won't hit.
        self.WaypointReturnedHybridBlockCount = 1 #First hybrid is allocated during DLE hence waypoint for that won't hit.
        self.WaypointReturnedClosedHybridBlockCount = 0
        self.ExpectedClosedHybridBlockCount = 0

    #-----------------------------------------------------------------------------
    def testHBD12_AppsCDMPattern(self):
        ''' 
            1. Write 4GB Data Once
            2. Read the written 4GB data twice
            3. Invalidate the 4GB data twice
            4. Insert delay for 10 seconds
            5. Perform Power Cycle
        '''        

        self.WaypointRegObj.DisableWPprintFlag()
        cycles = 5
        self.startLba = self.globalVarsObj.randomObj.randint(0, self.globalVarsObj.maxLba-1)
        
        for i in range(cycles):
            self.logger.Info("", "------------------ Start of Cycle %d ------------------" % i)
            self.logger.Info(self.globalVarsObj.TAG, "...Writing 4 GB data sequentially ...")	
            self.sizeInSectors = 4 * 1024 * 1024 * 2 # Sectors in 4GB 
            sectorsWritten = 0
            self.currentLba = self.startLba
            transferlength = 0x400
        
            # Writing 4GB Data
            while sectorsWritten < self.sizeInSectors:
                if self.currentLba + transferlength >= self.globalVarsObj.maxLba:
                    self.currentLba = 0x0
                self.ccmObj.Write(self.currentLba, transferlength)
    
                # Check if number of hybrid blocks added exceeds max limit of hybrid block
                if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxLimitOfHybridBlocks:
                    raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
                                                        (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxLimitOfHybridBlocks))
    
                # Check if number of closed hybrid blocks returned by waypoint matches expected closed hybrid block count
                elif self.ExpectedClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
                    raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
                                                        (self.ExpectedClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))
                # Check is stream switched to HDW
                elif (self.__HDWMode or self.__HDWSwitchHappened):
                    raise ValidationError.TestFailError(self.globalVarsObj.TAG, "The Stream is changed to HDW before 5GB Writes")
         
                # PASS		                        
                else:
                    self.logger.Info("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
                                     (self.ExpectedClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
    
                sectorsWritten += transferlength
                self.currentLba += transferlength  
                self.logger.Info(self.globalVarsObj.TAG, "Percent Write completed(in GB): %s" % 
                                 format(float(sectorsWritten)/(Constants.SectorsPerGB), '.8f'))				
    
    
            self.logger.Info(self.globalVarsObj.TAG, "...Completed writing 4 GB data...") 
        
            # Reading twice
            for i in range(0,2):
                self.logger.Info("", "-"*100)
                self.logger.Info("", "Hybrid Read Count: %d" % i)
                self.logger.Info("", "-"*100)
                self.currentLba = self.startLba
                sectorsRead = 0
                while sectorsRead < self.sizeInSectors:
                    if self.currentLba + transferlength >= self.globalVarsObj.maxLba:
                        self.currentLba = 0x0                    
                    self.ccmObj.Read(self.currentLba, transferlength) 
                    self.currentLba += transferlength
                    sectorsRead += transferlength                

            # Invalidating twice
            self.logger.Info(self.globalVarsObj.TAG, "...Writing same 4GB data two more times to check the Burst Performance...") 
            for i in range(0,2):
                self.logger.Info("", "-"*100)
                self.logger.Info("", "Hybrid Invalidation Count: %d" % i)
                self.logger.Info("", "-"*100)
                self.currentLba = self.startLba
                sectorsWritten = 0
                while sectorsWritten < self.sizeInSectors:
                    if self.currentLba + transferlength >= self.globalVarsObj.maxLba:
                        self.currentLba = 0x0
                    self.ccmObj.Write(self.currentLba, transferlength)
    
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
                    
                    self.currentLba += transferlength
                    sectorsWritten += transferlength
    
            # Inserting delay of 10 seconds
            self.utilsObj.InsertDelay(10000)
            
            # Perform Power Cycle
            self.utilsObj.PowerCycle()
            
            self.logger.Info("", "------------------ End of Cycle %d ------------------" % i)
        
        
    #------------------------------------------------------------------------------------			
        
    def OnSequentialModeSwitchBackFunc(self, args):
        self.__HDWSwitchHappened = True
        return True

    #------------------------------------------------------------------------------------        
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
        if self.WaypointReturnedHybridBlockCount != (self.WaypointReturnedClosedHybridBlockCount + 1):
            raise ValidationError.TestFailError("", "Last Closed Hybrid Block Count: %d. Expected New Hybrid Block Count: %d, Received New Hybrid Block Count: %d" %
                                                (self.WaypointReturnedClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))

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