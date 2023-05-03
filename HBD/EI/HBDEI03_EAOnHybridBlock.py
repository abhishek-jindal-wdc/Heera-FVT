#*-------------------------------------------------------------------------------
#* MODULE     : HBD10_EAOnHybridBlock
#* FUNCTION   : This test for Erase Abort on Hybrid block.
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

import SctpUtils
import FwConfig as FwConfig
import Extensions.CVFImports as pyWrap
import Core.ValidationError         as ValidationError
#import FeatureTests.ITGC.ITGC_Lib as ITGC_Lib
import ValidationLib.AddressTypes as AddressTypes
import ConfigParser
import FileData as FileData


#Global Variables
global_logger = None
class_obj     = None

class HBDEI03_EAOnHybridBlock(TestCase.TestCase):
    
   def setUp(self):
      global global_logger,class_obj
      TestCase.TestCase.setUp(self)

      self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
      self.__ccmObj         = self.globalVarsObj.ccmObj
      self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
      self.utilsObj       = Utils.Utils()
      self.sctpUtilsObj = SctpUtils.SctpUtils()
      
      self.__fileObject = FileData.FileData(self.vtfContainer)  
      self.__file14Object = self.__fileObject.GetFile14Data()      

      self.wayPointDict = {
         "BLM_GROWN_BAD_BLOCK_ADDED" : [self.AddedToGrownBadBlockList],
         "ITGC_START" : [],
         "ITGC_STOP" : [],
         "READ_ONLY_MODE" : [],
         "MB_ADDED_TO_CLOSED_HYBRID_LIST" : [self.OnMBAddedtoClosedHBDList],
         "MB_RELEASED_FROM_CLOSED_HYBRID_LIST" : [self.OnMBReleasedfromClosedHBDList],
         "HYBRID_BLOCK_ADDED" : [self.OnHybridBlockAdded],
         "HYBRID_BLOCK_REMOVED" : [self.OnHybridBlockRemoved],
         "FBL_BEFORE_ERASE_OF_ALLOCATED_BLOCK" : [self.OnFBLBeforeEraseOfAllocatedBlock],
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
      self.maxLba = self.__fwConfigObj.maxLba
      self.metaPageSize = self.__fwConfigObj.metaPageSize
      self.diesPerChip = self.__fwConfigObj.diesPerChip
      
      
      self.__randomObj = self.globalVarsObj.randomObj 
      self.__logger.Info(self.globalVarsObj.TAG, "Test objective: Test for error failure on Hybrid block.")

      self.__livet = self.vtfContainer._livet
      self.__livetFlash = self.__livet.GetFlash()
          

      # Register the waypoint callbacks
      #self.__livet.RegisterFirmwareWaypoint("HYBRID_BLOCK_ERASE",OnHybridBlockErase)
      self.__livet.RegisterLivetCallback(self.__livet.lcFlashEraseFail, OnEraseFailure)
          
      global_logger = self.__logger      
      class_obj = self
      g_random = self.__randomObj
      self.__fwConfigData = self.__fwConfigData
      self.metaBlockList=[]
      self.BlmGrownBadBlockArgs=[]
      self.ListOfblocksTobeAddedToFile226=[]
      
      self.__ListofMBsErasedAsSLC = []
      self.HybridBlockErasedAsSLC = False
      self.SLCErasedHybridBlock = 0     
      
      self.numOfEraseFailuresInjected = 0
      fileID=14
      fileSize = self.sctpUtilsObj.GetFileSize(fileID)
      rdbuff=self.sctpUtilsObj.ReadFileSystem(fileID,fileSize)      
      self.maxAllowedEFs = rdbuff.GetByte(0x54) # Max GBBs that can be handled
      
      self.ExpectedHybridBlockCount=0
      self.HybridBlockReleased=False
      isHybridBlock = False    
      self.ExpectedHybridBlockCount = 1
      self.ClosedHybridBlockCount = 0
      self.WaypointReturnedHybridBlockCount = 0      
      self.WaypointReturnedClosedHybridBlockCount=0

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

   def testHBDEI03_EAOnHybridBlock(self):
      """
      Description:
      1.Write sequential data such that �MB_ADDED_TO_CLOSED_BLOCK_FIFO� waypoint is fired.
      2.Keep writing the data such that �MLC_TO_SLC_ADDED� waypoint should be fired indicating that Hybrid blocks are getting created.
      3.Also the sequential data should be kept writing till Hybrid Block Count in the waypoint (�MLC_TO_SLC_ADDED�) reaches the maximum Hybrid block count value.
      4.Inject the erase failure on one of the hybrid blocks. So that the block is included in grown bad block list.
      """ 
      #Erase Options (0 - Retire on First Erase Failure, 1 - Erase Retry, 2 - Double Erase)
      self.sctpUtilsObj.WriteConfigFile(configFileId=21,Offset=0x12B, Value=0, numberOfBytes=1, doPowerCycle=True)
      self.ListOfblocksTobeAddedToFile226=[]
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
         
         #Check if hybrid block was erased as SLC
         if self.HybridBlockErasedAsSLC:
            raise ValidationError.TestFailError("", "Hybrid Block 0x%X was erased as SLC block. Expected to be erased as MLC" % self.SLCErasedHybridBlock)
   
         if self.ListOfblocksTobeAddedToFile226!=[]: 
            for block in self.ListOfblocksTobeAddedToFile226:
               if not block in self.BlmGrownBadBlockArgs:
                  raise ValidationError.TestFailError("", "Block :0x%x not added in File 226." %block)
   
      #Perform one Hybrid block write for counter verification
      transferLength = self.__fwConfigData.slcMBSize
      self.__ccmObj.Write(startLba, transferLength)
      # Check if number of hybrid blocks added exceeds max limit of hybrid block
      if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxLimitOfHybridBlocks:
         raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
                                             (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxLimitOfHybridBlocks))
   
      # Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
      if self.ClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
	    raise ValidationError.TestFailError("", "Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
	                                                                                      (self.ClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))
	  
      
   
      ## Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
      #if self.ExpectedHybridBlockCount != self.WaypointReturnedHybridBlockCount:
         #raise ValidationError.TestFailError("", "Expected Hybrid Block Count: %d, Received Hybrid Block Count: %d" %
                                             #(self.ExpectedHybridBlockCount, self.WaypointReturnedHybridBlockCount))

      
      return
      #end of run
          

   #---------------------------------------------------------------------- 


   def InjectEFError(self, chipNum , addr):
      """
     Name : InjectEFError
     Deescription : Used to inject EF
     Argument : chipNum, address
     Return : None
      """     
      # Get the Error Injection parameters
      flashOperation = self.__livet.foProgram
      errorType = self.__livet.etEraseError
      errorPersistence = self.__livet.epSoft
      delayToOccurence = 0
      delayToRecovery = 1 
      skipCount = 0
      errorByteOffset = 0
      errorByteMask = 0    
      errorDescription = (errorType,errorPersistence,delayToOccurence,delayToRecovery,errorByteOffset,errorByteMask)
      
      # Injecting EF on Physical Location
      if len(addr) == 7:
         self.__logger.Info(self.globalVarsObj.TAG, "Injecting EF at Physical Address: Chip:%d Die:%d Plane:%d Block:0x%04x wordLine:0x%04x string:0x%04x mlcLevel:%d Eccpage:0x%x\n" %(chipNum,addr[0],addr[1],addr[2],addr[3],addr[4],addr[5],addr[6]))
      else:
         self.__logger.Info(self.globalVarsObj.TAG, "Injecting EF at Physical Address: Chip:%d Die:%d Plane:%d Block:0x%04x wordLine:0x%04x mlcLevel:%d Eccpage:0x%x\n" %(chipNum,addr[0],addr[1],addr[2],addr[3],addr[4],addr[5]))    
      self.__livetFlash.InjectError(chipNum,addr,errorDescription)
      return 0
  
   def AddedToGrownBadBlockList(self, args ):
      """
      Args: "Bank","MB"     
      Description: This function check all the grown bad blocks (metablock) list in current command. 
                    These grow bad block should either be created via Program Failue.
      Returns: Raise exception if any Grown block is not part of PF/EF/UPlcc      
      """
      #self.logger.Info(self.globalVarsObj.TAG, "BLM_GROWN_BAD_BLOCK_ADDED BankNum:0x%X BlockNum:0x%x"%(args[0],args[1]))
      self.physicalMB=args["MB"]/ self.__fwConfigData.numberOfMetaPlane
      self.BlmGrownBadBlockArgs.append(self.physicalMB)
      return 0      
   
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
      if args["MBAddress"] in self.__ListofMBsErasedAsSLC:
         self.HybridBlockErasedAsSLC = True
         self.SLCErasedHybridBlock = args["MBAddress"]
         
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
   
   #------------------------------------------------------------------------------------
   def OnFBLBeforeEraseOfAllocatedBlock(self, args):  
      """
      Description:
      * Waypoint to indicate that a block will be erased from FBL/SLC FIFO
      * "Bank", "MBAddr", "BlockType", "Plane"
      """   
      if args["BlockType"] == 0x0: # if SLC Block
         if args["MBAddr"] not in self.__ListofMBsErasedAsSLC:
            self.__ListofMBsErasedAsSLC.append(args["MBAddr"])
         return 0
   
      self.logger.Info(self.globalVarsObj.TAG, "FBLBeforeEraseOfAllocatedBlock Waypoint Triggered.") 
      if self.numOfEraseFailuresInjected < self.maxAllowedEFs:
   
         self.logger.Info(self.globalVarsObj.TAG, "Converting the metablock number of the hybrid block to physical address.")
      
         phyAddr = AddressTypes.PhysicalAddress()
         MBNum = args["MBAddr"]
         bank = args["Bank"]
         phyAddrList = self.livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(MBNum,bank)
         phyAddrIndex = self.__randomObj.randrange(0, len(phyAddrList))
         phyAddr.bank = bank
         phyAddr.chip = phyAddrList[phyAddrIndex][0]
         phyAddr.die = phyAddrList[phyAddrIndex][1]
         phyAddr.plane = phyAddrList[phyAddrIndex][2]
         phyAddr.block = phyAddrList[phyAddrIndex][3]
         phyAddr.wordLine = self.__randomObj.randrange(0, self.__fwConfigData.wordLinesPerPhysicalBlock)
         phyAddr.mlcLevel = 0
         phyAddr.eccPage = 0
         
         if self.__fwConfigData.isBiCS:
            phyAddr.string = self.__randomObj.randrange(0, self.__fwConfigData.stringsPerBlock)
            newStyleAddress = (phyAddr.die,phyAddr.plane,phyAddr.block,phyAddr.wordLine,phyAddr.string,phyAddr.mlcLevel,phyAddr.eccPage)
         else:
            newStyleAddress = (phyAddr.die,phyAddr.plane,phyAddr.block,phyAddr.wordLine,phyAddr.mlcLevel,phyAddr.eccPage)      
         
         self.InjectEFError(phyAddr.chip, newStyleAddress)
         self.numOfEraseFailuresInjected += 1
      
      return 0   

def OnEraseFailure(package,addr):
   """
   Model Call Back Function for Erase Failure
   """
   global global_logger, class_obj
   class_obj.logger.Info("", "#################################################################################")
   if len(addr) == 7:
      class_obj.logger.Info("", "ERASE FAILURE occurred at -> Physical Address: (chip:%d die:%d plane:%d block:0x%04X wordLine:0x%04X string:0x%04X mlcLevel:%d eccPage:%d)"% (package,addr[0],addr[1],addr[2],addr[3],addr[4],addr[5],addr[6]))
   else:
      class_obj.logger.Info("", "ERASE FAILURE occurred at -> Physical Address: (chip:%d die:%d plane:%d block:0x%04X wordLine:0x%04X mlcLevel:%d eccPage:%d)"% (package,addr[0],addr[1],addr[2],addr[3],addr[4],addr[5]))      
   class_obj.logger.Info("", "#################################################################################")  

   class_obj.ListOfblocksTobeAddedToFile226.append(addr[2])
      
   return 0

      



   