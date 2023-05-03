#* MODULE     : HBD16_HybridOpenBlockPF
#* FUNCTION   : This test is to check CECC on secondary hybrid blocks
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
import FwConfig as FwConfig
import Utils as Utils
import os
from random import sample
import Extensions.CVFImports as pyWrap
#import FeatureTests.ITGC.ITGC_Lib as ITGC_Lib
import ValidationLib.AddressTypes as AddressTypes
import SctpUtils
import ValidationLib.EIMediator as EIMediator
import FwConfig as FwConfig
import Core.ValidationError         as ValidationError
import FileData
from ValidationLib import FWConfigData
import random
class HBDEI10_CECCOnSecHybridBlock(TestCase.TestCase):
    
    def setUp(self):
        TestCase.TestCase.setUp(self)

        self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
        self.__ccmObj         = self.globalVarsObj.ccmObj
        self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
        self.utilsObj       = Utils.Utils()
        self.sctpUtilsObj = SctpUtils.SctpUtils()

        self.wayPointDict = {
           
            "EPWR_COMPLETE" : [],
            "EPWR_START" : [],
            "MB_ADDED_TO_CLOSED_HYBRID_LIST" : [self.OnMBAddedtoClosedHBDList],
            "MB_RELEASED_FROM_CLOSED_HYBRID_LIST" : [self.OnMBReleasedfromClosedHBDList],
           
            "HYBRID_BLOCK_REMOVED" : [self.OnHybridBlockRemoved],            
	
            "UM_WRITE" : [self.OnUmWrite],
	    "UM_READ" : [self.OnUmRead],
	    "UM_BLOCK_ALLOCATION"     :[self.OnUMBlocksAllocation],
	    "GCC_START"                  : [],
	    "UECC_DETECTED" : [self.OnUECCDetected],
	    "EPWR_PHY_ADDRESS" : [self.OnEPWRPhyAddr],
	    
	   
	    
        }
        self.WaypointRegObj.RegisterWP(self.wayPointDict)
                
        self.__fwConfigObj = FwConfig.FwConfig(self.vtfContainer)

        self.__livet = self.vtfContainer._livet
        self.__livetFlash = self.__livet.GetFlash()             
        
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
	self.fwConfigDataObj = FWConfigData.FWConfigData(self.vtfContainer)
	configBuf = self.fwConfigDataObj.ReadConfigurationParameters()          
	self.__fileObject = FileData.FileData(self.vtfContainer)  
	self.__file14Object = self.__fileObject.GetFile14Data()	
	self.ThresholdMaxHybridBlocks = self.__file14Object.get('numOfHybridBlocks')  
	self.FileObj = FileData.FileData(self.vtfContainer)
	configParameter = self.FileObj.GetFile14Data()    
	self.ShiftInWLFromFile14 = configParameter["shiftInWordlines"]	
	self.wordLinesPerPhysicalBlock_BiCS = configBuf["WordlinesPerBlock_BiCS"]
	self.wordLinesInSecBlock= self.wordLinesPerPhysicalBlock_BiCS - self.ShiftInWLFromFile14-1
        self.choosenPageType=-1
	#print(choosenPageType)
        
    def tearDown(self):
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

    def testHBDEI10_CECCOnSecHybridBlock(self):
        self.__ccmObj.SetLbaTracker()
        Lg = self.globalVarsObj.randomObj.randint(0, self.__fwConfigObj.lgsInCard)
        startLba = 0
        transferLength = self.__fwConfigObj.slcMBSize/2
        startAddress = startLba
        
        self.__logger.Info(self.globalVarsObj.TAG, "-"*100)        
        self.lbaList= []
	self.sectorsWritten=0
	self.sectorsToWrite = 4*self.__fwConfigObj.sectorsPerSlcMetaBlock
        while (startLba < self.sectorsToWrite):
	    self.__ccmObj.Write(startLba, transferLength)
	    self.lbaList.append((startLba,transferLength))
	    startLba += transferLength 
	    self.sectorsWritten+=transferLength
	    
	    
	    if self.sectorsWritten >=self.__fwConfigObj.sectorsPerSlcMetaBlock/2: #reading the partial block
		for lba, transferLength in self.lbaList:
		    self.__ccmObj.Read(lba,transferLength)	
		self.sectorsWritten=0
		self.lbaList=[]		  
              
	
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

    def OnUECCDetected(self,args):
	return
    
    def OnCECCDetected(self,args):
	return
		   
    def OnUMBlocksAllocation(self,argDict):
	self.logger.Info("",'OnUMBlocksAllocation done')
	
	return
    
    def OnEPWRPhyAddr(self, argsDict):
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
	        
	    if (args["primary"]==0x0):    # CECC on secondary
		phyAddr=self.__eiObj.GetPhysicalAddress(args["MB"], args["MBOffset"])
		self.wordLines = list(range(0,self.wordLinesInSecBlock/2))
		self.wordLinesToInject = sample(self.wordLines,3) #choosing less than max uecc stms, max is 4
		choiceType=[0,1]  
		self.choosenPageType = random.choice(choiceType)			
		for i in range(len(self.wordLinesToInject)):
		    phyAddr.wordLine=self.wordLinesToInject[i]
		    if self.choosenPageType==0:
			self.__eiObj.InjectCECCErrorWithSTM(phyAddr, applyOnlyToPhysicalPage=True,blktype='slc')  
		    elif self.choosenPageType==1:
			self.__eiObj.InjectCECCErrorWithSTM(phyAddr, applyOnlyToEccPage=True,blktype='slc') 
		    elif self.choosenPageType==2:
			self.__eiObj.InjectCECCErrorWithSTM(phyAddr, entireBlock=True,blktype='slc') 
		self.errorInjectedLbaList.append(args["MB"])
		   
	    if (args["primary"]==0x1):   #uecc on primary 
		phyAddr=self.__eiObj.GetPhysicalAddress(args["MB"], args["MBOffset"])
		for i in range(len(self.wordLinesToInject)):
		    phyAddr.wordLine=self.wordLinesToInject[i] +self.ShiftInWLFromFile14
		    if self.choosenPageType==0:
			self.__eiObj.InjectUECCErrorWithSTM(phyAddr, blktype='slc', applyOnlyToPhysicalPage=True)
		    elif self.choosenPageType==1:
			self.__eiObj.InjectUECCErrorWithSTM(phyAddr, blktype='slc', applyOnlyToEccPage=True)
		    elif self.choosenPageType==2:
			self.__eiObj.InjectUECCErrorWithSTM(phyAddr, blktype='slc', isToBeAppliedToBlock=True)
			
		self.errorInjectedLbaList.append(args["MB"]) 
		    
            
    def OnWriteAbort(self, package, addr):
        """
        Description:
        * Waypoint to indicate if program failure has occured.
        * chip = package, die = addr[0], plane = addr[1], block = addr[2], 
        * wordLine = addr[3], mlcLevel = addr[4], eccPage = addr[5]
        """
        return 0
       
    def OnUmRead(self,args):
	return
        
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

        