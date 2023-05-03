#* MODULE     : HBDEI01_PFOnHybridBlock
#* FUNCTION   : This test for error injection particularly program failure on Hybrid block.
#* PROGRAMMER : Veerendrakumar
#* DATE(ORG)  : 22Jun'2015
#* REMARKS    : This assumes that the hardware and framework have been set up
#* COPYRIGHT  : Copyright (C) 2015 SanDisk Corporation 
#*------------------------------------------------------------------------------*
#*  Revision History
#*------------------------------------------------------------------------------*
#* Sl.No:  Date  : Description                                 - Programmer
#*------------------------------------------------------------------------------*
#*   1: 22/06/2015 : Programmed and Release for script testing - Veerendrakumar
#********************************************************************************


import Protocol.SCSI.Basic.TestCase as TestCase
import SCSIGlobalVars
import WaypointReg
import FwConfig as FwConfig
import Utils as Utils
import ValidationLib.EIMediator as EIMediator
import FileData as FileData
import SctpUtils
import FwConfig as FwConfig
import Extensions.CVFImports as pyWrap
import Core.ValidationError         as ValidationError
#import FeatureTests.ITGC.ITGC_Lib as ITGC_Lib
import ConfigParser



class HBDEI01_PFOnHybridBlock(TestCase.TestCase):
    
   def setUp(self):
      TestCase.TestCase.setUp(self)

      self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
      self.__ccmObj         = self.globalVarsObj.ccmObj
      self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
      self.utilsObj       = Utils.Utils()
      self.sctpUtilsObj = SctpUtils.SctpUtils()
      self.__fileObject = FileData.FileData(self.vtfContainer)  
      self.__file14Object = self.__fileObject.GetFile14Data()	      

      self.wayPointDict = {
         
         "BLM_GROWN_BAD_BLOCK_ADDED" : [self.OnDLMGrownBadBlockAdded],
         "ITGC_START" : [],
         "ITGC_STOP" : [],
         "MB_ADDED_TO_CLOSED_HYBRID_LIST" : [self.OnMBAddedtoClosedHBDList],
         "MB_RELEASED_FROM_CLOSED_HYBRID_LIST" : [self.OnMBReleasedfromClosedHBDList],
         "HYBRID_BLOCK_ADDED" : [self.OnHybridBlockAdded],
         "HYBRID_BLOCK_REMOVED" : [self.OnHybridBlockRemoved],
      }
      self.WaypointRegObj.RegisterWP(self.wayPointDict)
      """
         Name : __init__
         Description : Initialise the object        
         Argument : 
                   self.currCfg.variation.randomSeed        : Random seed used by the test
              objApplicationRunAttributes : Application Run Attributes object
         Return : None
      """      
      
      self.__eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
      self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)


      self.__logger = self.logger       
      self.__fwConfigData = FwConfig.FwConfig(self.vtfContainer)
            
      
      self.sectorsPerSlcBlock = self.__fwConfigObj.sectorsPerSlcBlock
      self.sectorsPerLg = self.__fwConfigObj.sectorsPerLg
      self.lgsInCard = self.__fwConfigObj.lgsInCard
      self.slcMBSize = self.__fwConfigObj.slcMBSize
      self.metaPageSize = self.__fwConfigObj.metaPageSize
      self.maxLba = self.__fwConfigObj.maxLba
      self.diesPerChip = self.__fwConfigObj.diesPerChip
      
      
      self.__randomObj = self.globalVarsObj.randomObj       
      self.__logger.Info(self.globalVarsObj.TAG, "Test objective: Test for error injection particularly program failure on Hybrid block.")

      self.__livet = self.vtfContainer._livet
      self.__livetFlash = self.__livet.GetFlash()

      # Register the call back for Program Failure
      self.__eiObj.RegisterProgramFailureCallback(self.OnProgramFailure)
      self.__logger.Info(self.globalVarsObj.TAG, "Waypoint for the event PROGRAM FAILURE has been registered successfully.")
            
                                             
      #self.__livetFlash.TraceOn('error_injected')
      #self.__livetFlash.TraceOn('error_occurred')
      #self.__livetFlash.TraceOn('data_write')
      
      #Test variables
      self.BlmGrownBadBlockArgs = []
      self.ClosedHybridBlockCount = 0
      self.WaypointReturnedClosedHybridBlockCount = 0
      self.metaBlockList = []
      self.ListOfblocksTobeAddedToFile226   = []
      self.WaypointReturnedHybridBlockCount = 0 #First hybrid allocated during DLE hence waypoint for that won't hit.
      
      self.ExpectedHybridBlockCount = 1 #First hybrid allocated during DLE hence waypoint for that won't hit.
      self.HybridBlockReleased=False
      self.__IsPFOccured=False
      g_IsHybridBlockCreated=False
            

   #----------------------------------------------------------------------
   def tearDown(self):
      """
         Name : OperationToPerformAtEndOfTest
    Description : Used to call at the end of the test 
         Argument : None
         Return : None
      """
      #Operations to perform during at the end of test
      self.__ccmObj.DataVerify()
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

   def testHBDEI01_PFOnHybridBlock(self):
      """
      Description:
      1.Keep writing the data such that �MLC_TO_SLC_ADDED� waypoint should be fired indicating that Hybrid blocks are getting created.
      2.Also the sequential data should be kept writing till Hybrid Block Count in the waypoint (�MLC_TO_SLC_ADDED�) reaches the maximum Hybrid block count value.
      3.Inject the program failure on the hybrid block.
      4.Write the hybrid blocks again. Make sure to make one of the blocks invalidated partially so that the blocks are added to grown bad block list.
      """
      self.ListOfblocksTobeAddedToFile226 = []
      self.BlmGrownBadBlockArgs = []
      self.__ccmObj.SetLbaTracker()

      
      #Get the hybrid block count from the file 14 (Offset 0x40).    
      
      self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')

      if not self.ThresholdMaxLimitOfHybridBlocks:
         raise ValidationError.TestFailError("", "Test case Applicable only For Anisha Non Dual Write Feature Enabled(File 14 offset 0x40).")

      maxHybridBlockCount = self.__file14Object.get('numOfHybridBlocks')
      
      if maxHybridBlockCount == 0:
         maxHBCount = self.__randomObj.randint(1, self.ThresholdMaxLimitOfHybridBlocks)
         self.sctpUtilsObj.SetMaxHybridBlockCount( maxHBCount)
         self.ThresholdMaxLimitOfHybridBlocks = self.__file14Object.get('numOfHybridBlocks')
      else:
         self.ThresholdMaxLimitOfHybridBlocks = maxHybridBlockCount

      self.logger.Info(self.globalVarsObj.TAG, "Number of Hybrid Blocks = %d" % self.ThresholdMaxLimitOfHybridBlocks)
      
      self.logger.Info(self.globalVarsObj.TAG, "******************************************************")
      self.logger.Info(self.globalVarsObj.TAG, "Start writing the data sequentially to the slc blocks.")
      self.logger.Info(self.globalVarsObj.TAG, "******************************************************")
      
      #Get the total no of SLC Count from the File 21
      
      
      Lg = self.__randomObj.randint(0, self.lgsInCard)
      startLba = self.sectorsPerLg*Lg
      transferLength = self.slcMBSize/2
      slcBlockCount = 0
      
      while (self.ExpectedHybridBlockCount < self.ThresholdMaxLimitOfHybridBlocks):
         if (startLba + transferLength) >= self.maxLba:
            self.logger.Info(self.globalVarsObj.TAG, "choosing another random LG as it exeeds maximum capacity of card")
            Lg = self.__randomObj.randint(0, self.lgsInCard)
            startLba = self.sectorsPerLg * Lg
         #Perform writes with the chosen transfer length
         self.__ccmObj.Write(startLba, transferLength)
         startLba = startLba + self.slcMBSize/2
    
         if self.ExpectedHybridBlockCount >= 2:
            transferLength = 0x100
            while (self.ExpectedHybridBlockCount < self.ThresholdMaxLimitOfHybridBlocks):
               if (startLba + transferLength) >= self.maxLba:
                  self.logger.Info(self.globalVarsObj.TAG, "choosing another random LG as it exeeds maximum capacity of card")
                  Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
                  startLba = self.sectorsPerLg * Lg  
               #Perform writes with the chosen transfer length 
	       #if self.__IsPFOccured:
				# self.__ccmObj.Write(startLba, self.slcMBSize/2)	       
               self.__ccmObj.Write(startLba, transferLength)
               self.__eiObj.InjectProgramFailureError(errorLba = startLba+0x100)
	       
               
               if (startLba + transferLength+(self.slcMBSize/2 - 0x100)) >= self.maxLba:
                  self.logger.Info(self.globalVarsObj.TAG, "choosing another random LG as it exeeds maximum capacity of card")
                  Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
                  startLba = self.sectorsPerLg * Lg        
               self.__ccmObj.Write(startLba+transferLength, (self.slcMBSize/2 - 0x100))  # 0x3F00 = self.slcMBSize-0x100, this is considered to complete one slc block
               startLba = startLba + self.slcMBSize/2

    
      self.logger.Info(self.globalVarsObj.TAG, "**************************************************")
      self.logger.Info(self.globalVarsObj.TAG, "Start writing the data sequentially to the blocks.")
      self.logger.Info(self.globalVarsObj.TAG, "**************************************************")

      Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
      startLba = self.sectorsPerLg*Lg
      transferLength = self.slcMBSize/2
      blockCount = 0
      MAX_WRITE_COUNT = 100
      
      while (blockCount < MAX_WRITE_COUNT):
         if (startLba + transferLength) >= self.maxLba:
            self.logger.Info(self.globalVarsObj.TAG, "choosing another random LG as it exeeds maximum capacity of card")
            Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
            startLba = startLba + transferLength
         #Perform writes with the chosen transfer length
         self.__ccmObj.Write(startLba, transferLength)
         if blockCount == 10 :
            self.__ccmObj.Write(startLba, self.metaPageSize)       #Invalidate one of the blocks partially.
            startLba = startLba + transferLength
         blockCount = blockCount + 1

      #Perform one Hybrid block write for counter verification
      transferLength = self.__fwConfigData.slcMBSize
      self.__ccmObj.Write(startLba, transferLength)
      # Check if number of hybrid blocks added exceeds max limit of hybrid block
      if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxLimitOfHybridBlocks:
         raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
                                             (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxLimitOfHybridBlocks))
   
      # Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
      if self.ClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
         raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
									                    (self.ClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))


      if self.__IsPFOccured == False:
         raise ValidationError.TestFailError("", "Test Failed as Program Failure did not occur.")

      if self.ListOfblocksTobeAddedToFile226!=[]: 
         if self.BlmGrownBadBlockArgs != []:
            for block in self.ListOfblocksTobeAddedToFile226:
               if not block in self.BlmGrownBadBlockArgs:
                  raise ValidationError.TestFailError("", "Block :0x%X not added in File 226." %block) 

      return
      #end of run
    
   

   #---------------------------------------------------------------------- 

      
   def OnProgramFailure(self, package,addr):
      """
      Description:
    * Waypoint to indicate if program failure has occured.
    * chip = package, die = addr[0], plane = addr[1], block = addr[2], 
    * wordLine = addr[3], mlcLevel = addr[4], eccPage = addr[5]
      """
      self.logger.Info(self.globalVarsObj.TAG, "#" * 115)
      if len(addr) == 7:
         self.logger.Info(self.globalVarsObj.TAG, "PROGRAM FAILURE occurred at -> Physical Address: (chip:%d die:%d plane:%d block:0x%04X wordLine:0x%04X string:0x%04X mlcLevel:%d eccPage:%d)"% (package,addr[0],addr[1],addr[2],addr[3],addr[4],addr[5],addr[6]))
      else:
         self.logger.Info(self.globalVarsObj.TAG, "PROGRAM FAILURE occurred at -> Physical Address: (chip:%d die:%d plane:%d block:0x%04X wordLine:0x%04X mlcLevel:%d eccPage:%d)"% (package,addr[0],addr[1],addr[2],addr[3],addr[4],addr[5]))  
      self.logger.Info(self.globalVarsObj.TAG, "#" * 115)
      
      self.__IsPFOccured = True
      self.ListOfblocksTobeAddedToFile226.append(addr[2])
      
      return 0

   
   def OnDLMGrownBadBlockAdded(self, args):
      """
      "Bank", "MBAddr", "BlockType", "PhyBlock0", "PhyBlock1", "PhyBlock2","PhyBlock3",
						"PhyBlock4", "PhyBlock5", "PhyBlock6", "PhyBlock7"    
      """
      self.BlmGrownBadBlockArgs.append(args["MBAddr"])
      
      return None  
   
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
      self.ExpectedHybridBlockCount += 1  
      self.metaBlockList.append(args["MBAddress"])
      self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
     # if self.WaypointReturnedHybridBlockCount != (self.ClosedHybridBlockCount + 1):
	# raise ValidationError.TestFailError("", "Last Closed Hybrid Block Count: %d. Expected New Hybrid Block Count: %d, Received New Hybrid Block Count: %d" %
	#				                                                     (self.ClosedHybridBlockCount, self.ClosedHybridBlockCount+1, self.WaypointReturnedHybridBlockCount))
      
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
   def OnMBReleasedfromClosedHBDList(self, args):
      """
      "MBAddress", "ClosedHybridBlockCount"
      """
      #self.metaBlockList.remove(args["MBAddress"])
      self.HybridBlockReleased = True
      self.ClosedHybridBlockCount = self.ClosedHybridBlockCount - 1  
      self.WaypointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"]
      #self.WaypointReturnedHybridBlockCount = args["ClosedHybridBlockCount"] + 1
   
      return 0
