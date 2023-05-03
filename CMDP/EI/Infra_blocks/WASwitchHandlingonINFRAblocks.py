import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
import IFS
import Boot
import SDExpressWrapper as SDExWrap
import CTFServiceWrapper as ServiceWrap
import CMDP.CMDP_History as History

WriteAbortDetected = False

def OnWriteAbort(package, addr):
    """
    Write Abort callback function
    Arguments: 
    """
    global WriteAbortDetected
    WriteAbortDetected = True
    print('DETECTED WRITE ABORT')


class WAhandler:
    
    __staticWAObj = None

    ##
    # @brief A method to create a singleton object of LOG WA HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not WAhandler.__staticWAObj:
            WAhandler.__staticWAObj = super(WAhandler,cls).__new__(cls, *args, **kwargs)

        return WAhandler.__staticWAObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = GlobalVars.GlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.SDutilsObj = SDUtils.SDUtils
        self.IFSObj = IFS.IFS_Framework()        
        self.livetObj.UnregisterLivetCallback(self.livetObj.lcFlashProgramAbort)        
        self.livetObj.RegisterLivetCallback(self.livetObj.lcFlashProgramAbort, OnWriteAbort)                        
        
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger)
            self.wayPointDict = {
                "WP_PS_PF_DETECTED"                 : [self.WP_PS_PF_DETECTED],
                "WP_INFRA_IFS_IN_WRITE_FILE"        : [self.WP_INFRA_IFS_IN_WRITE_FILE],
                "WP_INFRA_IFS_IN_BOOTPAGE_UPDATE"   : [self.WP_INFRA_IFS_IN_BOOTPAGE_UPDATE],
                "WP_FWR_LOG_WRITE_REQ"              : [self.WP_FWR_LOG_WRITE_REQ],                
            }
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)        
        
        self.BootObj = Boot.BOOT_Framework()
        self.ResetVariables()
        self.Session = self.vtfContainer.device_session
        self.errorManager = self.Session.GetErrorManager()
        self.errorManager.RegisterCallback(self.ErrorHandlerFunction)        

        
    def ErrorHandlerFunction(self,statusCodeType,statusCode):	
        self.logger.Info(self.globalVarsObj.TAG, "Callback received with received status code: %d and status code type: %d"%(statusCode,statusCodeType))       
        self.KWARGS['EINobj'].cmdpScsiFeLib.inLowVoltageMode = False
        
        if(WriteAbortDetected or (statusCode == 144) or (statusCode == 5) or (statusCode == 11)) and not self.AlreadySwitched:
            self.errorManager.ClearAllErrors() 
            self.AlreadySwitched = True
            self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762                            
            SDExWrap.SwitchProtocol(shutdownType=ServiceWrap.UNGRACEFUL)  
            #self.vtfContainer.switchProtocol(powerCycleType="UGSD")
            if(self.vtfContainer.activeProtocol == 'SD_OF_SDPCIe'):
                self.vtfContainer.activeProtocol = 'NVMe_OF_SDPCIe'
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode = False
            else:
                self.vtfContainer.activeProtocol = 'SD_OF_SDPCIe'
                self.globalVarsObj.vtfContainer.cmd_line_args.isSdMode = True
        else:
            self.errorManager.ClearAllErrors() 
        
        self.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762 
            
    def WP_INFRA_IFS_IN_BOOTPAGE_UPDATE(self,eventKey,args, pid):
        self.BootObj.WP_INFRA_IFS_IN_BOOTPAGE_UPDATE_callback(eventKey,args,pid)            
        #args -> channel, chip, die, plane, block, currPage, SecondaryBB/PrimaryBB, BootPageRevCount
        #[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
        if(self.PrimaryBootBlock):
            self.PhysicalAddressOfPrimaryBootBlock = [args[2],args[3],args[4],args[5]>>2,args[5] & 3,0,0]
            if(self.InBOOTWAHandling and not self.BootWAinjected):
                self.BootObj.InjectWAonPhysicalBlock(self.PhysicalAddressOfPrimaryBootBlock,args[0])
                self.BootWAinjected = True
                self.WAdetected = False
        else:
            self.PhysicalAddressOfSecondaryBootBlock = [args[2],args[3],args[4],args[5]>>2,args[5] & 3,0,0]
            #self.BootObj.InjectWAonPhysicalBlock(self.PhysicalAddressOfSecondaryBootBlock)
        
        self.PrimaryBootBlock = not self.PrimaryBootBlock
    
    def WP_FWR_LOG_WRITE_REQ(self,eventKeys, args, processorID):
        #jba.jumboBlockId, jba.fmuInBlock, vbaList->vba32, fmuCount
        if(self.WriteStarted):
            self.RecentlyWrittenLogJb = args[0]
            self.RecentlyWrittenLogVba = args[2]
            
    def WP_INFRA_IFS_IN_WRITE_FILE(self,eventKey,args, pid):
        #fileId, byteCount, pba.channel, pba.chip, pba.die, pba.plane, pba.block, currentpage 
        if(not args[-1] and self.CorruptPrimary):
            #PRIMARY IFS WRITE
            if(not self.WAInjected or self.BacktoBackWA):
                print('BEFORE WA : BLOCK: %d, die:%d ,plane:%d ,block:%d ,wordline:%d ,string:%d ,chip:%d, channel:%d'%(args[-1], args[4], args[5], args[6],  args[7]>>2 , args[7] & 3,args[3],args[2]))
                self.IFSObj.InjectWAonPhysicalAddress(args[4], args[5], args[6],  args[7]>>2 , args[7] & 3, channel= args[2])
                (self.PlaneBeforeWAinjection,self.DieBeforeWAinjection,self.BlockBeforeWAinjection)=(args[5],args[4],[6])
                self.WAInjected = True
                self.bad_blocks.append({'die':args[4],'plane':args[5],'block':args[6],'chip':args[3],'channel':args[2],'Type':'PRIMARY'})
                
            else:
                if(self.BacktoBackWA):
                    print('BEFORE WA : BLOCK: %d, die:%d ,plane:%d ,block:%d ,wordline:%d ,string:%d ,chip:%d, channel:%d'%(args[-1], args[4], args[5], args[6],  args[7]>>2 , args[7] & 3,args[3],args[2]))
                    self.IFSObj.InjectWAonPhysicalAddress(args[4], args[5], args[6],  args[7]>>2 , args[7] & 3, channel= args[2])
                    (self.PlaneBeforeWAinjection,self.DieBeforeWAinjection,self.BlockBeforeWAinjection)=(args[5],args[4],[6])
                    self.WAInjected = True
                    self.bad_blocks.append({'die':args[4],'plane':args[5],'block':args[6],'chip':args[3],'channel':args[2],'Type':'PRIMARY'})
                    
                else:
                    print('NO WA : BLOCK: %d, die:%d ,plane:%d ,block:%d ,wordline:%d ,string:%d ,chip:%d, channel:%d'%(args[-1], args[4], args[5], args[6],  args[7]>>2 , args[7] & 3,args[3],args[2]))            
            
        elif(self.CorruptSecondary and args[-1]):
            #SECONDARY IFS WRITE
            if(not self.WAInjectedSec or self.BacktoBackWA):
                print('BEFORE WA : BLOCK: %d, die:%d ,plane:%d ,block:%d ,wordline:%d ,string:%d ,chip:%d, channel:%d'%(args[-1], args[4], args[5], args[6],  args[7]>>2 , args[7] & 3,args[3],args[2]))
                self.IFSObj.InjectWAonPhysicalAddress(args[4], args[5], args[6],  args[7]>>2 , args[7] & 3, channel= args[2])
                (self.PlaneBeforeWAinjection,self.DieBeforeWAinjection,self.BlockBeforeWAinjection)=(args[5],args[4],[6])
                self.bad_blocks.append({'die':args[4],'plane':args[5],'block':args[6],'chip':args[3],'channel':args[2],'Type':'SECONDARY'})
                self.WAInjectedSec = True
            else:
                if(self.BacktoBackWA):
                    print('BEFORE WA : BLOCK: %d, die:%d ,plane:%d ,block:%d ,wordline:%d ,string:%d ,chip:%d, channel:%d'%(args[-1], args[4], args[5], args[6],  args[7]>>2 , args[7] & 3,args[3],args[2]))
                    self.IFSObj.InjectWAonPhysicalAddress(args[4], args[5], args[6],  args[7]>>2 , args[7] & 3, channel= args[2])
                    (self.PlaneBeforeWAinjection,self.DieBeforeWAinjection,self.BlockBeforeWAinjection)=(args[5],args[4],[6])
                    self.WAInjectedSec = True
                    self.bad_blocks.append({'die':args[4],'plane':args[5],'block':args[6],'chip':args[3],'channel':args[2],'Type':'SECONDARY'})
                    
                else:
                    print('NO WA : BLOCK: %d, die:%d ,plane:%d ,block:%d ,wordline:%d ,string:%d ,chip:%d, channel:%d'%(args[-1], args[4], args[5], args[6],  args[7]>>2 , args[7] & 3,args[3],args[2]))            
     
    
    def WP_PS_PF_DETECTED(self,eventKey,args, pid):
        self.PFdetected = True
    
        
    def ResetVariables(self):
        self.writtendata = []
        self.PFdetected = False
        self.XorDumpHappened = False
        self.RelinkingnotHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterWAHandling = None
        self.LogDumpHappened = False
        self.MTMconsolidationHappened = False
        self.FileId = None
        self.DieBeforeWAinjection = None
        self.PlaneBeforeWAinjection = None
        self.BlockBeforeWAinjection = None
        self.WAInjected =False
        self.SwitchedFromPRIMARYtoSECONDARY = False
        self.WAInjectedSec = False 
        self.bad_blocks = []     
        self.CorruptPrimary = True
        self.CorruptSecondary = True
        self.BacktoBackWA = False        
        self.InBOOTWAHandling = False
        self.PrimaryBootBlock = False
        self.AddressBeforeWAwasInjected = None
        self.AddressAfterWAwasInjected = None
        self.PhysicalAddressOfPrimaryBootBlock = None
        self.PhysicalAddressOfSecondaryBootBlock = None
        self.WriteStarted = []
        self.InjectedLogPF = False
        self.RecentlyWrittenLogJb = None
        self.BootWAinjected = False
        self.SetSwitchDuringAbort(setFlag=1)
        self.KWARGS = {}
        self.AlreadySwitched = False
        
    def DeregisterAllWaypoint(self):
        self.wayPointHandlerObj.UnRegisterWP(self.wayPointDict)
        
    def SetSwitchDuringAbort(self, setFlag = 0):
        self.globalVarsObj.configParser.SetValue("Switch_protocol_after_abort", setFlag)
            
    def WAHandlerIFS(self, Blockstate, **kwargs):
        global WriteAbortDetected
        self.KWARGS = kwargs
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)                
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING IFS WA HANDLER *************')
        #kwargs keys -> BlocksToFail(max 10), PrimaryBlockFail, SecondaryBlockFail, PrimarySecondaryBlockFail
        self.InBOOTWAHandling = False
        (bootBlockListBEFORE, partitionListBEFORE) = self.IFSObj.GetFSBlockInfo()              
        partitionListBEFORE = self.IFSObj.BeutifyPartitionBlockArray(partitionListBEFORE)
        
        if(self.FileId == None):
            self.readFileBuffer,self.lengthOfDirectoryFileInSectors = self.IFSObj.ReadFileID(File_id=1)
            self.FileId = self.globalVarsObj.randomObj.randint(170, 180) 
        
        try:
            if('BlocksToFail' in kwargs.keys()):
                for Block in range(kwargs['BlocksToFail']):
                    self.CorruptPrimary = True
                    self.CorruptSecondary = False
                    self.BacktoBackWA = False
                    self.IFSObj.InitiateIFSWrite(1, self.readFileBuffer, self.FileId, self.lengthOfDirectoryFileInSectors)
                    
            elif('BlocksToFail' not in kwargs.keys() and 'PrimaryBlockFail' in kwargs.keys()):
                self.CorruptPrimary = True
                self.CorruptSecondary = False
                self.BacktoBackWA = False
                self.IFSObj.InitiateIFSWrite(1, self.readFileBuffer, self.FileId, self.lengthOfDirectoryFileInSectors)
            
            elif('BlocksToFail' not in kwargs.keys() and 'SecondaryBlockFail' in kwargs.keys()):
                self.CorruptPrimary = True
                self.CorruptSecondary = False
                self.BacktoBackWA = False
                self.IFSObj.InitiateIFSWrite(1, self.readFileBuffer, self.FileId, self.lengthOfDirectoryFileInSectors)
            
            elif('BlocksToFail' not in kwargs.keys() and 'PrimarySecondaryBlockFail' in kwargs.keys()):
                self.CorruptPrimary = True
                self.CorruptSecondary = True
                self.BacktoBackWA = False
                self.IFSObj.InitiateIFSWrite(1, self.readFileBuffer, self.FileId, self.lengthOfDirectoryFileInSectors)
            
            else:
                self.CorruptPrimary = True
                self.CorruptSecondary = False
                self.BacktoBackWA = False
                #self.IFSObj.InitiateIFSWrite(1, self.readFileBuffer, self.FileId, self.lengthOfDirectoryFileInSectors)
                self.WriteSequentiallyTillBootFlushHappens()
                
        except:
            self.errorManager.ClearAllErrors() 
            #self.ErrorHandlerFunction(0,144)
            
        (bootBlockList, partitionList) = self.IFSObj.GetFSBlockInfo()              
        partitionList = self.IFSObj.BeutifyPartitionBlockArray(partitionList)
        #PREPARE BAD BLOCKS LIST
        self.LocalListDiag = [{'block': i['block'], 'channel': i['channel'], 'chip': i['chip'], 'die': i['die'], 'plane': i['plane']} for i in partitionList['FAIL_BLOCK']]
        self.LocalListBB = [{'block': i['block'], 'channel': i['channel'], 'chip': i['chip'], 'die': i['die'], 'plane': i['plane']} for i in self.bad_blocks]
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "WA wasn't detected"
        
        #compare bad blocks list
        if(partitionList == partitionListBEFORE):
            self.logger.Info(self.globalVarsObj.TAG, "Mismatch in Block lists")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "Mismatch in Block lists"
        
        self.logger.Info(self.globalVarsObj.TAG, "############ IFS WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True
    
    def WriteSequentiallyTillBootFlushHappens(self):
        self.currentLBA = self.globalVarsObj.startLba
        self.MaxTransfer = 1024
        for self.currentLBA in range(self.globalVarsObj.startLba, self.globalVarsObj.endLba, self.MaxTransfer):
            self.globalVarsObj.ccmObj.Write(self.currentLBA, self.MaxTransfer)
            self.WriteStarted = True            
            if(self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
                self.globalVarsObj.ccmObj.DoFlushCache()            
            if(self.PFdetected):
                return
            
            if(not self.InjectedLogPF):
                if(self.RecentlyWrittenLogJb != None):
                    self.InjectPFonblock(self.RecentlyWrittenLogVba + 8) 
    
    def InjectPFonblock(self,VBA):
        try:
            physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1)
            self.AddressBeforeWAinjection = physical_address.copy()
            self.AddressBeforeWAinjection['VBA'] = VBA
            
            phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
            errorPersistence = 1 
            paerrorDescription = (self.vtfContainer._livet.etProgramError ,errorPersistence,0,1,0,0)
            package = physical_address['channel'] 
            self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
            self.logger.Info(self.globalVarsObj.TAG, 'PF is injected to {}'.format(str(physical_address)))
            self.InjectedLogPF = True
        except:
            raise ValidationError.TestFailError(self.globalVarsObj.TAG, "PF not injected (Error in injection), check the injection or Physical address")    

    
    def WAHandlerBOOT(self, Blockstate, **kwargs):
        global WriteAbortDetected  
        self.KWARGS = kwargs
        
        try:
            self.DeregisterAllWaypoint()
        except:
            pass
        
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)                
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING BOOT WA HANDLER *************')
        #kwargs keys -> BlocksToFail(max 10), PrimaryBlockFail, SecondaryBlockFail, PrimarySecondaryBlockFail
        self.InBOOTWAHandling = True
        
        #To Avoid IFS clash
        self.CorruptPrimary = False 
        self.CorruptSecondary = False
        self.BacktoBackWA = False        
        #################################
        
        #self.sctputilsobj.ForceBootUpdate()   
        try:            
            self.WriteSequentiallyTillBootFlushHappens()
        except:
            self.errorManager.ClearAllErrors() 
            
        self.InBOOTWAHandling = False
        self.BootBlockInfo = self.BootObj.getRecentBootPage()
        
        self.BootBlockPrimaryAddressBeforeWA = self.BootBlockInfo['PrimaryBootPage']     
        self.BootBlockSecondaryAddressBeforeWA = self.BootBlockInfo['SecondaryBootPage']       
        self.BootPagePrimaryBeforeWA = self.BootBlockInfo['LatestPageNumberPrimary']
        self.BootPageSecondaryBeforeWA = self.BootBlockInfo['LatestPageNumberSecondary']
        self.VersionNumberPrimaryBeforeWA = self.BootBlockInfo['LatestRevisionCountPrimary']
        self.VersionNumberSecondaryBeforeWA = self.BootBlockInfo['LatestRevisionCountSecondary']        
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "WA wasn't detected"
        
        self.BootBlockInfoAfterWA = self.BootObj.getRecentBootPage()
    
        self.LatestBootBlockPrimaryAddress = self.BootBlockInfoAfterWA['PrimaryBootPage']     
        self.LatestBootBlockSecondaryAddress = self.BootBlockInfoAfterWA['SecondaryBootPage']       
        self.latestBootPagePrimary = self.BootBlockInfoAfterWA['LatestPageNumberPrimary']
        self.latestBootPageSecondary = self.BootBlockInfoAfterWA['LatestPageNumberSecondary']
        self.latestVersionNumberPrimary = self.BootBlockInfoAfterWA['LatestRevisionCountPrimary']
        self.latestVersionNumberSecondary = self.BootBlockInfoAfterWA['LatestRevisionCountSecondary']
        
        if(self.latestVersionNumberPrimary != self.latestVersionNumberSecondary):
            self.logger.Info(self.globalVarsObj.TAG, "Firmware Version numbers are not corrected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "Firmware Version numbers are not corrected"        
        
        if(not WriteAbortDetected):
            self.logger.Info(self.globalVarsObj.TAG, "WA wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "WA wasn't detected"
        
        if(self.LatestBootBlockPrimaryAddress == self.BootBlockPrimaryAddressBeforeWA):
            self.logger.Info(self.globalVarsObj.TAG, "New Boot block wasnt allocated even after WA was detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()            
            return "New Boot block wasnt allocated even after WA was detected"             
        
        self.logger.Info(self.globalVarsObj.TAG, "############ BOOT WA handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True    
          
             
    def __del__(self): 
        print('Destructor called, Instance deleted.')     
        
