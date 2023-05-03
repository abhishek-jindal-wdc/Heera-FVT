#* MODULE     : HBD16_HybridOpenBlockPF
#* FUNCTION   : This test is to check Program Failure on Secondary hybrid blocks
#* PROGRAMMER : Aarshiya Khandelwal
#* DATE(ORG)  : 02 Dec'2019
#* REMARKS    : This assumes that the hardware and framework have been set up
#* COPYRIGHT  : Copyright (C) 2019 SanDisk Corporation 
#*----------------------------------------------------------------------------------*
#*  Revision History
#*----------------------------------------------------------------------------------*
#* Sl.No:  Date  : Description                                 - Programmer
#*----------------------------------------------------------------------------------*
#*   1: 02/12/2019 : Programmed and Release for script testing - Aarshiya Khandelwal
#************************************************************************************
#"""
import Protocol.SCSI.Basic.TestCase as TestCase
import SCSIGlobalVars
import WaypointReg

import Utils as Utils
import os

import Extensions.CVFImports as pyWrap
#import FeatureTests.ITGC.ITGC_Lib as ITGC_Lib
import ValidationLib.AddressTypes as AddressTypes
import SctpUtils
import ValidationLib.EIMediator as EIMediator
import FwConfig as FwConfig
import Core.ValidationError         as ValidationError
import FileData
from ValidationLib import FWConfigData
class HBDEI09_WAOnSecHybridBlock(TestCase.TestCase):
    
    def setUp(self):
        TestCase.TestCase.setUp(self)

        self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
        self.__ccmObj         = self.globalVarsObj.ccmObj
        self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
        self.utilsObj       = Utils.Utils()
        self.sctpUtilsObj = SctpUtils.SctpUtils()
	self.fwConfig = FwConfig.FwConfig(self.vtfContainer)
        self.wayPointDict = {
            "EPWR_COMPLETE" : [],
            "EPWR_START" : [],
            "MB_ADDED_TO_CLOSED_HYBRID_LIST" : [self.OnMBAddedtoClosedHBDList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST" : [self.OnMBReleasedfromClosedHBDList],
            "HYBRID_BLOCK_ADDED" : [self.OnHybridBlockAdded],
            "HYBRID_BLOCK_REMOVED" : [self.OnHybridBlockRemoved],            
            "READ_ONLY_MODE" : [self.OnReadOnlyMode],
            "UM_WRITE" : [self.OnUmWrite],
	    "UM_BLOCK_ALLOCATION"     :[self.OnUMBlocksAllocation],
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict)
                
        self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)

        self.__livet = self.vtfContainer._livet
        self.__livetFlash = self.__livet.GetFlash()             
	self.FileObj = FileData.FileData(self.vtfContainer)
	  
        self.__logger = self.logger
        
        self.__randomObj = self.globalVarsObj.randomObj
        self.__eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
        
        self.diesPerChip = self.__fwConfigObj.diesPerChip 
        self.lgsInCard = self.__fwConfigObj.lgsInCard
        self.maxLba = self.__fwConfigObj.maxLba
        self.metaPageSize = self.__fwConfigObj.metaPageSize
        self.sectorsPerLg = self.__fwConfigObj.sectorsPerLg   
        self.sectorsPerSlcBlock = self.__fwConfigObj.sectorsPerSlcBlock        
        self.slcMBSize = self.__fwConfigObj.slcMBSize
	#self.fwConfigDataObj = fwConfig.fwConfig(self.vtfContainer)
	#configBuf = self.__fwConfigObj.ReadConfigurationParameters()   
	self.fwConfigDataObj = FWConfigData.FWConfigData(self.vtfContainer)
	configBuf = self.fwConfigDataObj.ReadConfigurationParameters()
	configParameter = self.FileObj.GetFile14Data()    
	self.ShiftInWLFromFile14 = configParameter["shiftInWordlines"]	
	self.wordLinesPerPhysicalBlock_BiCS = configBuf["WordlinesPerBlock_BiCS"]
	self.wordLinesInSecBlock= self.wordLinesPerPhysicalBlock_BiCS - self.ShiftInWLFromFile14-1	
        self.RegisterWaypoints()
        self.ExpectedHybridBlockCount = 1
        self.ClosedHybridBlockCount = 0
        self.WaypointReturnedHybridBlockCount = 0
	self.WaypointReturnedClosedHybridBlockCount=0
        self.isHybridBlock = False
        self.injectError = False
        self.injectOnSecondary = False        
        self.currentHybridBlock = 0
        self.hybridBlocksList = []
        self.errorInjectedLbaList = []
        self.errorOccurred = []
        self.isWATriggered = False
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	
	self.ThresholdMaxHybridBlocks = self.__file14Object.get('numOfHybridBlocks')        
        #self.SLCBlocksCount = ITGC_Lib.GetITGCfile21params( "ITGC_FIFOsize")
        #self.ThresholdMaxHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.UmBlockCount=0
        #self.lbaToInjectError = 3#self.__randomObj.sample(range(1, self.ThresholdMaxHybridBlocks), 5)
        #path = os.environ["SANDISK_FW_VALIDATION"]
        #self.fileName = os.path.join(path, "BiCS4STM\\SLC\\UECC\\SLC_UECC.STM")        
        self.__eiObj.RegisterWriteAbortCallback(self.OnWriteAbort)
        self.WAMbs=self.WACallBackMbs=[]
	self.count=0
	self.injecterrorOnWL0=True
	self.LivetObj = self.vtfContainer._livet
    def tearDown(self):
	self.WaypointRegObj.UnRegisterWP(self.wayPointDict) 
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

    def testHBDEI09_WAOnSecHybridBlock(self):
        self.__ccmObj.SetLbaTracker()
	self.__ccmObj.SetLbaTracker()
        Lg = self.globalVarsObj.randomObj.randint(0, self.__fwConfigObj.lgsInCard)
        startLba = self.sectorsPerLg*Lg
        transferLength = 0x100#self.__fwConfigObj.slcMBSize
        OneGBLen = 0x1FF800
        self.lbaToInjectError = self.__randomObj.sample(range(1, self.ThresholdMaxHybridBlocks-20), 5)
	
        startAddress = startLba
        self.__logger.Info(self.globalVarsObj.TAG, "...Writing 1 GB data sequentially...")
        self.__logger.Info(self.globalVarsObj.TAG, "-"*100)        
        
        while (startLba < OneGBLen+startAddress):
            self.__ccmObj.Write(startLba, transferLength)
            startLba += transferLength    
            
            if self.ExpectedHybridBlockCount in self.lbaToInjectError:
                self.injectError = True
	    
	    phyAddr=self.sctpUtilsObj.TranslateLogicalToPhy(startLba)

		
	if self.isWATriggered==True:
	    self.isWATriggered=False
	    for InjectedMBs in self.errorInjectedLbaList:	
		if InjectedMBs not in self.WACallBackMbs:
		    if phyAddr.block ==self.secMB  and phyAddr.wordLine > self.phyAddr.wordLine:   #open block check if injected WL is not written			    
			raise ValidationError.TestFailError("", "MB: %d injected with WA but not occured" %InjectedMBs)	
	
        self.__logger.Info(self.globalVarsObj.TAG, "...Completed writing 1 GB data...")
        self.__logger.Info(self.globalVarsObj.TAG, "-"*100)   
	self.sctpUtilsObj.ForceHybridEviction()
        
        #Perform one Hybrid block write for counter verification
        transferLength = self.__fwConfigObj.slcMBSize
        self.__ccmObj.Write(startLba, transferLength)
        # Check if number of hybrid blocks added exceeds max limit of hybrid block
        if self.WaypointReturnedHybridBlockCount > self.ThresholdMaxHybridBlocks:
            raise ValidationError.TestFailError("", "Hybrid Block Count returned by waypoint(Received Hybrid Block Count: %d) exceeds Max allowed Hybrid Blocks (%d)" %
                                                (self.WaypointReturnedHybridBlockCount, self.ThresholdMaxHybridBlocks))
            
	# Check if number of hybrid blocks returned by waypoint matches expected hybrid block count
	if self.ClosedHybridBlockCount != self.WaypointReturnedClosedHybridBlockCount:
	    raise ValidationError.TestFailError("", "Expected Closed Hybrid Block Count: %d, Received Closed Hybrid Block Count: %d" %
	                                                                                      (self.ClosedHybridBlockCount, self.WaypointReturnedClosedHybridBlockCount))
            

    def RegisterWaypoints(self):
        #Register Firmware Waypoints required
        
        self.__eiObj.RegisterWriteAbortCallback(self.OnWriteAbort)
        
    #------------------------------------------------------------------------------------                  
    def OnMBAddedtoClosedHBDList(self, args):
        """
        MBAddress, ClosedHybridBlockCount
        """
        self.ClosedHybridBlockCount = self.ClosedHybridBlockCount + 1
	self.WaypointReturnedClosedHybridBlockCount = args["ClosedHybridBlockCount"]
        return
    
    
    def OnWriteAbort(self,Package,Addr):
	"""
					       
	Model Call Back Function for PreWriteAbort
	"""      
	self.logger.Info(self.globalVarsObj.TAG,"***************WRITE ABORT CALL BACK RECIEVED******")
	self.logger.Info(self.globalVarsObj.TAG,"***************CLEARING ERROR INJECTED*************")
	self.isWATriggered = True 
	if Addr[2] not in self.WACallBackMbs:
	    self.WACallBackMbs.append(Addr[2])
    #------------------------------------------------------------------------------------
    def OnHybridBlockAdded(self, args):
        """
        Args: "Bank", "MBAddress", "HybridBlockCount", "StreamID"
        """
        self.ExpectedHybridBlockCount += 1  
        #self.metaBlockList.append(args["MBAddress"])
        self.WaypointReturnedHybridBlockCount = args["HybridBlockCount"]
        return
    #----------------------------------------------------------------------------
    
    def InjectError(self,MB,wl):
	self.__phyAdd =  AddressTypes.PhysicalAddress()
	self.phyAddrList = self.LivetObj.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(MB,0)
	self.__chosen = self.phyAddrList[0]
	self.__phyAdd.chip     = self.__chosen[0]
	self.__phyAdd.die      = self.__chosen[1]
	self.__phyAdd.plane    = self.__chosen[2]
	self.__phyAdd.block    = self.__chosen[3]
	self.__phyAdd.wordLine = wl						
	self.__phyAdd.string   = self.__randomObj.randrange(0,self.fwConfig.stringsPerBlock)
	#self.__phyAdd.mlcLevel = 2   
	self.__eiObj.InjectWriteAbortError(errorPhyAddress = self.__phyAdd,errorType="wrab")
	self.injecterrorOnWL0=False
    #----------------------------------------------------------------------
    def OnUMBlocksAllocation(self,argDict):
	self.secMB=argDict["SecondaryMB"]
	self.logger.Info("",'OnUMBlocksAllocation done')
	if self.injecterrorOnWL0==True:
	    wordLineOfSecondary =0 #injecting on 0th WL 
	    self.InjectError(argDict["SecondaryMB"],wordLineOfSecondary)	    
	    self.errorInjectedLbaList.append(argDict["SecondaryMB"])
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
    def OnUmWrite(self , args):
        """
        Args: "Bank","LG","LGOffset","transferLength","StreamType","StreamID","MB","MBOffset","primary","numSectorsToPrepad","numSectorsToPostpad","startWriteOffset"
        """
	
        if args["MB"] not in self.errorInjectedLbaList:  
            if (args["primary"]==0x0 ) and self.injectError==True: 
		if self.count==0:  
		    self.phyAddr=self.__eiObj.GetPhysicalAddress(args["MB"], args["MBOffset"])                
		    self.phyAddr.wordLine = self.wordLinesInSecBlock  #injecting on last WL only once so kept count
		    self.__eiObj.InjectWriteAbortError(errorType="wrab",errorPhyAddress=self.phyAddr)
		    self.errorInjectedLbaList.append(args["MB"])
		    self.count+=1
		    self.injectError==False
		else:
		    self.phyAddr=self.__eiObj.GetPhysicalAddress(args["MB"], args["MBOffset"])  
		    if self.phyAddr.wordLine !=self.wordLinesInSecBlock-2:  #making sure not choosing last wordline 
			self.phyAddr.wordLine = self.globalVarsObj.randomObj.randint(self.phyAddr.wordLine+1,self.wordLinesInSecBlock) 
			self.__eiObj.InjectWriteAbortError(errorType="wrab",errorPhyAddress=self.phyAddr)
			self.errorInjectedLbaList.append(args["MB"])
			self.injectError==False
	
    
    def OnReadOnlyMode(self , args):
        self.__logger.Info(self.globalVarsObj.TAG, "WA injected on %d LBAs: " % len(self.errorInjectedLbaList)) 
        #for lba in self.errorInjectedLbaList:
            #self.__logger.Info("0x%X" % lba) 
        
    def GetWordlineLbas(self,package,addr):
        """
        Description:
           * Gets the wordline lbas
        """
        self.errorAffectedLbaListTemp = []
        wordLineLbas = self.__livetFlash.GetWordlineLBAs(package,addr)
        startIndex = wordLineLbas[0] + 1
        #self.logger.Info("wordline lbas :: %s"%(list(wordLineLbas)))
        # Form a list with valid lba's
        for lba in range(startIndex,len(wordLineLbas)):
            if not wordLineLbas[lba] < 0:
                self.errorAffectedLbaListTemp.append(wordLineLbas[lba]) 

        