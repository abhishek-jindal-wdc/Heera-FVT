#*--------------------------------------------------------------------------------
#* MODULE     : HBD11_HybridBlockNotReused
#* FUNCTION   : This test validates the Hybrid Block is not reused.
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
import AddressTranslation as AddressTranslation
import SctpUtils
import FwConfig as FwConfig
import Extensions.CVFImports as pyWrap
import Core.ValidationError         as ValidationError
#import FeatureTests.ITGC.ITGC_Lib as ITGC_Lib
import ConfigParser

#Global Variables



class HBDEI04_HybridBlockNotReused(TestCase.TestCase):
    
   def setUp(self):
      TestCase.TestCase.setUp(self)
   
      self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
      self.__ccmObj         = self.globalVarsObj.ccmObj
      self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
      self.utilsObj       = Utils.Utils()
      self.sctpUtilsObj = SctpUtils.SctpUtils()
   
      self.wayPointDict = {
         "HYBRID_BLOCK_ADDED" : [],
         "HYBRID_BLOCK_REMOVED" : [],
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
             objApplicationRunAttributes  : Application Run Attributes object
         Return : None
      """      
      
      self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)
  
  
      self.__logger = self.logger 
      
      self.__fwConfigData = FwConfig.FwConfig(self.vtfContainer)
            
      
      self.sectorsPerSlcBlock = self.__fwConfigObj.sectorsPerSlcBlock
      self.sectorsPerLg = self.__fwConfigObj.sectorsPerLg
      self.lgsInCard = self.__fwConfigObj.lgsInCard
      self.slcMBSize = self.__fwConfigObj.slcMBSize
      self.maxLba = self.__fwConfigObj.maxLba
      self.diesPerChip = self.__fwConfigObj.diesPerChip
      
      
      self.__randomObj = self.globalVarsObj.randomObj 
      self.__addrTranslatnObj = AddressTranslation.AddressTranslator(self.vtfContainer)
      self.__logger.Info(self.globalVarsObj.TAG, "Test objective: Test case validates the Hybrid Block is not reused.")

      self.__livet = self.vtfContainer._livet
      self.__livetFlash = self.__livet.GetFlash()
      

      self.logger = self.__logger
      self.metaBlockListA=[]
      self.metaBlockListB=[]
      self.hybStartAddresslba={}
      self.StartAddresslba={}
      self.ExpectedHybridBlockCount = 1
      self.ClosedHybridBlockCount = 0
      self.WaypointReturnedHybridBlockCount = 0       
      self.WaypointReturnedClosedHybridBlockCount=0
      
      self.ExpectedHybridBlockCount=0
      self.HybridBlockReleased=False
      self.firstMetaBlockList=True      

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

   def testHBDEI04_HybridBlockNotReused(self):
      """
      Description:
      1.Write sequential data such that �MB_ADDED_TO_CLOSED_BLOCK_FIFO� waypoint is fired
      2.Keep writing the data such that �MLC_TO_SLC_ADDED� waypoint should be fired indicating that Hybrid blocks are getting created.
      3.Also the sequential data should be kept writing till Hybrid Block Count in the waypoint (�MLC_TO_SLC_ADDED�) reaches the maximum Hybrid block count value
      4.Continue Sequential writes until Folding (FG) is triggered. (�FOLDING_BEFORE_BLK_ALLOCATION� waypoint should be fired). When Folding (FG) is triggered, make sure Hybrid ITGC FIFO is full.
      5.Maintain a list in the test of all the blocks available in Hybrid FIFO.Invalidate the Hybrid blocks.
      6.Now again write the data to the hybrid block. And Invalidate the hybrid blocks.
      7.Make sure the same blocks are not used again as Hybrid blocks.
      """

      
      #Get the hybrid block count from the file 14 (Offset 0x40).    
      self.__ccmObj.SetLbaTracker()
      self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()

      if not self.ThresholdMaxLimitOfHybridBlocks:
         raise ValidationError.TestFailError("", "Test case Applicable only For Anisha Non Dual Write Feature Enabled(File 14 offset 0x40).")

      maxHybridBlockCount = self.sctpUtilsObj.GetMaxHybridBlockCount()
      
      if maxHybridBlockCount == 0:
         maxHBCount = self.__randomObj.randint(1, self.ThresholdMaxLimitOfHybridBlocks)
         self.sctpUtilsObj.SetMaxHybridBlockCount( maxHBCount)
         self.ThresholdMaxLimitOfHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
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
      thresholdexceeded = False
      self.firstMetaBlockList=True
      slcBlockCount = 0
      
      #while (slcBlockCount <= NoOfSLCBlocksCount):
         #if (startLba + transferLength) >= self.maxLba:
            #self.logger.Info(self.globalVarsObj.TAG, "choosing another random LG as it exeeds maximum capacity of card")
            #Lg = self.__randomObj.randint(0, self.lgsInCard)
            #startLba = self.sectorsPerLg * Lg   
         ##Perform writes with the chosen transfer length
         #self.__ccmObj.Write(startLba, transferLength)
         #startLba = startLba + transferLength
         #slcBlockCount = slcBlockCount + 1


      self.logger.Info(self.globalVarsObj.TAG, "*********************************************************")
      self.logger.Info(self.globalVarsObj.TAG, "Start writing the data sequentially to the Hybrid blocks.")
      self.logger.Info(self.globalVarsObj.TAG, "*********************************************************")

      Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
      startLba = self.sectorsPerLg*Lg

      while (self.ExpectedHybridBlockCount < self.ThresholdMaxLimitOfHybridBlocks):
         if (startLba + transferLength) >= self.maxLba:
            self.logger.Info(self.globalVarsObj.TAG, "choosing another random LG as it exeeds maximum capacity of card")
            Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
            startLba = self.sectorsPerLg * Lg   
         #Perform writes with the chosen transfer length
         self.__ccmObj.Write(startLba, transferLength)
         startLba = startLba + transferLength
    
      
      self.logger.Info(self.globalVarsObj.TAG, "**********************************************************************************")
      self.logger.Info(self.globalVarsObj.TAG, "Convert the metablock number to physical address and invalidate the hybrid blocks.")
      self.logger.Info(self.globalVarsObj.TAG, "**********************************************************************************")

      mblenA = len(self.metaBlockListA)      

      for blk in range(mblenA):      
         MBAddress = self.__addrTranslatnObj.TranslateMBNumtoMBA(self.metaBlockListA[blk])
         PhyAddr = (self.__addrTranslatnObj.TranslateMetaToPhy(MBAddress)[0])    
         package = PhyAddr.chip
         if self.__fwConfigData.isBiCS:
            address = (PhyAddr.die, PhyAddr.plane, PhyAddr.block, PhyAddr.wordLine, PhyAddr.string, PhyAddr.mlcLevel, PhyAddr.eccPage)    
         else:
            address = (PhyAddr.die, PhyAddr.plane, PhyAddr.block, PhyAddr.wordLine, PhyAddr.mlcLevel, PhyAddr.eccPage)  
            self.GetWordlineLbas(package,address)
            self.logger.Info(self.globalVarsObj.TAG, "Invalidating the %d Hybrid Block" %(blk+1))
            self.__ccmObj.Write(self.errorAffectedLbaListTemp[0], transferLength)
      
 
      self.firstMetaBlockList=False

      self.logger.Info(self.globalVarsObj.TAG, "*********************************************************")
      self.logger.Info(self.globalVarsObj.TAG, "Start writing the data sequentially to the Hybrid blocks.")
      self.logger.Info(self.globalVarsObj.TAG, "*********************************************************")

      Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
      startLba = self.sectorsPerLg*Lg

      while (self.ExpectedHybridBlockCount < (self.ThresholdMaxLimitOfHybridBlocks-1)):
         if (startLba + transferLength) >= self.maxLba:
            self.logger.Info(self.globalVarsObj.TAG, "choosing another random LG as it exeeds maximum capacity of card")
            Lg = self.__randomObj.randint(0, self.lgsInCard-self.ThresholdMaxLimitOfHybridBlocks)
            startLba = self.sectorsPerLg * Lg   
         #Perform writes with the chosen transfer length
         self.__ccmObj.Write(startLba, transferLength)
         startLba = startLba + transferLength


      self.logger.Info(self.globalVarsObj.TAG, "**********************************************************************************")
      self.logger.Info(self.globalVarsObj.TAG, "Convert the metablock number to physical address and invalidate the hybrid blocks.")
      self.logger.Info(self.globalVarsObj.TAG, "**********************************************************************************")

      mblenB = len(self.metaBlockListB)      

      for blk in range(mblenB):      
         MBAddress = self.__addrTranslatnObj.TranslateMBNumtoMBA(self.metaBlockListB[blk])
         PhyAddr = (self.__addrTranslatnObj.TranslateMetaToPhy(MBAddress)[0])    
         package = PhyAddr.chip
         if self.__fwConfigData.isBiCS:
            address = (PhyAddr.die, PhyAddr.plane, PhyAddr.block, PhyAddr.wordLine,PhyAddr.string, PhyAddr.mlcLevel, PhyAddr.eccPage)  
         else:
            address = (PhyAddr.die, PhyAddr.plane, PhyAddr.block, PhyAddr.wordLine, PhyAddr.mlcLevel, PhyAddr.eccPage)  
         self.GetWordlineLbas(package,address)
         self.logger.Info(self.globalVarsObj.TAG, "Invalidating the %d Hybrid Block" %(blk+1))
         self.__ccmObj.Write(self.errorAffectedLbaListTemp[0], transferLength)
      
      
      #Now compare the list of metaBlocks got from the two instances.
      #If they match that indicates that the hybrid blocks are getting reused.
      for hybridblk1 in range(mblenA):
         for hybridblk2 in range(mblenB):
            assert(self.metaBlockListA[hybridblk1] != self.metaBlockListB[hybridblk2])," Hybrid block %d getting reused."%(self.metaBlockListA[hybridblk1])

       
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
	  
      
      ## Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
      #if self.ExpectedHybridBlockCount != self.WaypointReturnedHybridBlockCount:
         #raise ValidationError.TestFailError("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
                                             #(self.ExpectedHybridBlockCount, self.WaypointReturnedHybridBlockCount))

      
      return
      #end of run
      
      
   #----------------------------------------------------------------------
   def GetWordlineLbas(self,package,addr):
      """
      Description:
         * Gets the wordline lbas
      """
      self.errorAffectedLbaListTemp = []
      wordLineLbas = self.__livetFlash.GetWordlineLBAs(package,addr)
      startIndex = wordLineLbas[0] + 1
      self.logger.Info(self.globalVarsObj.TAG, "wordline lbas :: %s"%(list(wordLineLbas)))
      # Form a list with valid lba's
      for lba in range(startIndex,len(wordLineLbas)):
         if not wordLineLbas[lba] < 0:
            self.errorAffectedLbaListTemp.append(wordLineLbas[lba]) 
       
   
   #----------------------------------------------------------------------
   def RegisterLivetFirmwareWaypoint(self):
      """
      """
      global dictionaryOfEventKeys
      assert EventKey>0,"ITGC_START waypoint is not registered"
      dictionaryOfEventKeys["ITGC_START"]=EventKey

      assert EventKey>0,"ITGC_STOP Waypoint is not registered"
      dictionaryOfEventKeys["ITGC_STOP"]=EventKey

      #EventKey=self.__livet.RegisterFirmwareWaypoint("MB_ADDED_TO_CLOSED_BLOCK_FIFO",WaypointCallBackFunc)
      #assert EventKey>0,"MB_ADDED_TO_CLOSED_BLOCK_FIFO waypoint is not registered"
      #dictionaryOfEventKeys["MB_ADDED_TO_CLOSED_BLOCK_FIFO"]=EventKey

      assert EventKey>0,"MLC_TO_SLC_ADDED waypoint is not registered"
      dictionaryOfEventKeys["MLC_TO_SLC_ADDED"]=EventKey
      
      #EventKey=self.__livet.RegisterFirmwareWaypoint("MLC_TO_SLC_REMOVED",WaypointCallBackFunc)
      #assert EventKey>0,"MLC_TO_SLC_REMOVED waypoint is not registered"
      #dictionaryOfEventKeys["MLC_TO_SLC_REMOVED"]=EventKey

      assert EventKey>0,"HYBRID_BLOCK_ADDED waypoint is not registered"
      dictionaryOfEventKeys["HYBRID_BLOCK_ADDED"]=EventKey

      assert EventKey>0,"HYBRID_BLOCK_REMOVED waypoint is not registered"
      dictionaryOfEventKeys["HYBRID_BLOCK_REMOVED"]=EventKey
     
      return    
   

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
      #self.metaBlockList.append(args["MBAddress"])
      self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
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
      self.ExpectedHybridBlockCount -= 1
      #self.metaBlockList.remove(args["MBAddress"])
      self.HybridBlockReleased = True
      self.ClosedHybridBlockCount = self.ClosedHybridBlockCount - 1   
      self.WaypointReturnedClosedHybridBlockCount=args[ "ClosedHybridBlockCount"]
   
      return 0