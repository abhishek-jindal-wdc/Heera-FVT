"""
************************************************************************************
* MODULE     : HBD16_HybridOpenBlockPF
* FUNCTION   : This test is to check Program Failure on open hybrid blocks
* PROGRAMMER : Aarshiya Khandelwal
* DATE(ORG)  : 02 Dec'2019
* REMARKS    : This assumes that the hardware and framework have been set up
* COPYRIGHT  : Copyright (C) 2019 SanDisk Corporation 
*----------------------------------------------------------------------------------*
*  Revision History
*----------------------------------------------------------------------------------*
* Sl.No:  Date  : Description                                 - Programmer
*----------------------------------------------------------------------------------*
*   1: 02/12/2019 : Programmed and Release for script testing - Aarshiya Khandelwal
************************************************************************************
"""
import Protocol.SCSI.Basic.TestCase as TestCase
import SCSIGlobalVars
import WaypointReg
import FwConfig as FwConfig
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

class HBDEI07_HybridOpenBlockPF(TestCase.TestCase):
    
    def setUp(self):
        TestCase.TestCase.setUp(self)

        self.globalVarsObj  = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)
        self.__ccmObj         = self.globalVarsObj.ccmObj
        self.WaypointRegObj = WaypointReg.WaypointReg(self.livet, self.logger, self.globalVarsObj)
        self.utilsObj       = Utils.Utils()
        self.sctpUtilsObj = SctpUtils.SctpUtils()

        self.wayPointDict = {
            "DLM_GROWN_BAD_BLOCK_ADDED" : [self.OnDlmGrownbadblockAdded],
            "EPWR_COMPLETE" : [],
            "EPWR_START" : [],
            "HYBRID_BLOCK_ADDED" : [self.OnHybridBlockAdded],
            "READ_ONLY_MODE" : [self.OnReadOnlyMode],
            "UM_WRITE" : [self.OnUmWrite],
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
        self.numHybridBlocks = 0
        self.isHybridBlock = False
        self.injectError = False
        self.injectOnSecondary = False        
        self.currentHybridBlock = 0
        self.hybridBlocksList = []
        self.errorInjectedLbaList = []
        self.errorOccurred = []
	self.PFCallBackMbs=[]   
	self.MMPList = list(range(0, self.__fwConfigObj.numberOfMetaPlane))        
        #self.SLCBlocksCount = ITGC_Lib.GetITGCfile21params( "ITGC_FIFOsize")
        self.__fileObject = FileData.FileData(self.vtfContainer)  
        self.__file14Object = self.__fileObject.GetFile14Data()	
        self.ThresholdMaxHybridBlocks = self.__file14Object.get('numOfHybridBlocks')
        #self.ThresholdMaxHybridBlocks = self.sctpUtilsObj.GetMaxHybridBlockCount()
        self.lbaToInjectError = self.__randomObj.sample(range(1, self.ThresholdMaxHybridBlocks), 5)
        #path = os.environ["SANDISK_FW_VALIDATION"]
        #self.fileName = os.path.join(path, "BiCS4STM\\SLC\\UECC\\SLC_UECC.STM")        
        
        
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

    def testHBDEI07_HybridOpenBlockPF(self):
        self.__ccmObj.SetLbaTracker()
	self.lbaToInjectError = self.globalVarsObj.randomObj.sample(range(1, self.ThresholdMaxHybridBlocks-20), 5)
	self.lbaToInjectError = [3, 8, 9, 11, 12]
        Lg = self.globalVarsObj.randomObj.randint(0, self.__fwConfigObj.lgsInCard)
        startLba = self.sectorsPerLg*Lg
        transferLength = self.__fwConfigObj.slcMBSize
        OneGBLen = 0x1FF800
        startAddress = startLba
        self.__logger.Info(self.globalVarsObj.TAG, "...Writing 1 GB data sequentially...")
        self.__logger.Info(self.globalVarsObj.TAG, "-"*100)        
        
	while (len(self.MMPList)):
            self.__ccmObj.Write(startLba, transferLength)
            startLba += transferLength
	    self.__ccmObj.Write(startLba, 0x100)   #to open a hybrid block
	    startLba += 0x100
	    self.injectError = True # On UM_Write
	    self.__ccmObj.Write(startLba, 0x100)
	    self.injectError = False
            
        self.__logger.Info(self.globalVarsObj.TAG, "...Completed writing 1 GB data...")
        self.__logger.Info(self.globalVarsObj.TAG, "-"*100)   
        
	for InjectedMbs in self.PFCallBackMbs:
	    if InjectedMbs not in self.errorInjectedLbaList:
		raise ValidationError.TestFailError("", "MB: %d occured with PF but not injected" %InjectedMbs)        

    def RegisterWaypoints(self):
        #Register Firmware Waypoints required
        
        self.__eiObj.RegisterProgramFailureCallback(self.OnProgramFailure)
        
    def OnHybridBlockAdded(self , args):
        """
        Args       : "Bank", "MBAddress", "HybridBlockCount", "StreamID"
        """
        self.hybridBlocksList.append(args["MBAddress"])
        self.numHybridBlocks += 1
                
    def OnDlmGrownbadblockAdded(self , args):
        """
        Args       : "Bank", "MBAddr", "BlockType", "PhyBlock0", "PhyBlock1", "PhyBlock2","PhyBlock3",
						"PhyBlock4", "PhyBlock5", "PhyBlock6", "PhyBlock7"
        """
        self.errorOccurred.append(args["MBAddr"])
        
    def OnUmWrite(self , args):
        """
        Args: "Bank","LG","LGOffset","transferLength","StreamType","StreamID","MB","MBOffset","primary","numSectorsToPrepad","numSectorsToPostpad","startWriteOffset"
        """
        if args["MB"] not in self.errorInjectedLbaList and args["MB"] % self.__fwConfigObj.numberOfMetaPlane in self.MMPList:
            if self.injectError and (args["primary"]==0x1):     #Inject 4 PFs on Primary
                phyAddr = AddressTypes.PhysicalAddress()
                phyAddrList = self.__livet.GetFirmwareInterface().GetPhysicalBlocksFromMetablockAddress(args["MB"],0)
                phyAddrIndex = self.__randomObj.randrange(0, len(phyAddrList))
            
                phyAddr.chip = phyAddrList[phyAddrIndex][0]
                phyAddr.die = phyAddrList[phyAddrIndex][1]
                phyAddr.plane = phyAddrList[phyAddrIndex][2]
                phyAddr.block = phyAddrList[phyAddrIndex][3]  
                
                self.wordlines = [] 
                secondaryWL = []
                # Inject PFs on 4 wordlines for block to retire not within guardband(+/- 1 wordline)
                self.wordlines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+8)) #no hardcoding
                self.wordlines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2+10,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+18))
                self.wordlines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2+20,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+28))
                self.wordlines.append(self.__randomObj.randrange(self.__fwConfigObj.wordLinesPerPhysicalBlock/2+30,self.__fwConfigObj.wordLinesPerPhysicalBlock/2+38))
                
                for i in range(0,4):   
                    phyAddr.wordLine = self.wordlines[i]
                    self.__eiObj.InjectProgramFailureError(errorPhyAddress=phyAddr)
                self.errorInjectedLbaList.append(args["MB"])
                    
            
    def OnProgramFailure(self, package, addr):
        """
        Description:
        * Waypoint to indicate if program failure has occured.
        * chip = package, die = addr[0], plane = addr[1], block = addr[2], 
        * wordLine = addr[3], mlcLevel = addr[4], eccPage = addr[5]
        """
	self.logger.Info(self.globalVarsObj.TAG,"***************PROGRAM FAILURE CALL BACK RECIEVED******")
	Mb = addr[2] * self.__fwConfigObj.numberOfMetaPlane + package
	if package in self.MMPList:
	    self.MMPList.remove(package)
	if Mb not in self.PFCallBackMbs:
	    self.PFCallBackMbs.append(Mb)	
        return 0
    
    def OnReadOnlyMode(self , args):
        self.__logger.Info(self.globalVarsObj.TAG, "PF injected on %d LBAs: " % len(self.errorInjectedLbaList)) 
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

        