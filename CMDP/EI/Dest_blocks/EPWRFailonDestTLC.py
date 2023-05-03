import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WaypointReg
import SDUtils
import Extensions.CVFImports as pyWrap
import random
import CMDP.CMDP_AccessPattern_Lib as CMDP_AP_Lib

class EPWRfailDestTLCPFHandler:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not EPWRfailDestTLCPFHandler.__staticPFObj:
            EPWRfailDestTLCPFHandler.__staticPFObj = super(EPWRfailDestTLCPFHandler,cls).__new__(cls, *args, **kwargs)

        return EPWRfailDestTLCPFHandler.__staticPFObj

    def __init__(self):
        #Condition to check if the class instance was already created
        #Objects
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
        self.logger = self.globalVarsObj.logger
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet
        self.sctputilsobj = SctpUtils.SctpUtils()
        self.errorInjObj = ErrorInjectorLib.ErrorInjectorLib(self.vtfContainer, self.logger)
        self.SDutilsObj = SDUtils.SDUtils
        self.cmdpAPLib = CMDP_AP_Lib.CMDP_AccessPattern_Lib()
        self.startLba = self.globalVarsObj.startLba
        self.endLba = self.globalVarsObj.endLba        
        
        
        if self.vtfContainer.isModel is True:
            self.livetObj = self.vtfContainer._livet 
            self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj, self.logger)
            self.wayPointDict = {
                "WP_PS_PF_DETECTED"                 : [self.WP_PS_PF_DETECTED, 'PrintArguments'],
                "WP_PS_BBM_PH_BLOCK_RELINK"         : [self.WP_PS_BBM_PH_BLOCK_RELINK, 'PrintArguments'], 
                "WP_FTL_HWD_WRITE_JB_VBA"           : [self.WP_FTL_HWD_WRITE_JB_VBA,'PrintArguments'],
                "WP_FTL_RLC_WRITE_JB_VBA"           : [self.WP_FTL_RLC_WRITE_JB_VBA,'PrintArguments'],
                "WP_FTL_BML_PARTIAL_BLOCK_ADDED"    : [self.WP_FTL_BML_PARTIAL_BLOCK_ADDED, 'PrintArguments'],
                "WP_PS_EPWR_Failure"                : [self.WP_PS_EPWR_Failure_Callback, 'PrintArguments'],
                "WP_PS_OTG_PROG_FLASH_ADDR"         : [self.WP_PS_OTG_PROG_FLASH_ADDR]
                
              }
            self.WaypointRegObj.RegisterWP(self.wayPointDict)        
        
        self.ResetVariables()
        
    def WP_PS_OTG_PROG_FLASH_ADDR(self,eventKey,args, pid):
        print('OTG PROGRAM')
        print('VBA : %d, Block Type: %d'%(args[0],args[1]))
        print('DEVBA0 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[2],args[3],args[4],args[5],args[6]))
        print('DEVBA1 Die : %d, Plane: %d, Block: %d, Wordline: %d, String:%d'%(args[7],args[8],args[9],args[10],args[11]))
        if(args[1] == 1 and self.vtfContainer.getActiveProtocol() == "NVMe_OF_SDPCIe"):
            self.TLCvbaWritten.append(args[0])
            
            
    def InjectErrorFromWP(self,vba,die,plane,block,wl,string,channel):
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramAbort ,errorPersistence,0,1,0,0)
        package = channel
        phyAddress=[die,plane,block,wl,string,0,0]            
        self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)
        self.logger.Info(self.globalVarsObj.TAG, "Injected Write Abort on VBA: %d"% (vba))
        self.logger.Info(self.globalVarsObj.TAG, "Physical Address -> Die: %d, Plane: %d, PhysicalBlock: %d, Wordline: %d, String: %d" \
                         % (die,plane,block,wl,string))
        self.logger.Info(self.globalVarsObj.TAG, "*"*100)        
        
        
    def WP_FTL_BML_PARTIAL_BLOCK_ADDED(self,eventKey,args, pid):
        self.BlockAddedToPartialList = args[0]
    
    def WP_FTL_RLC_WRITE_JB_VBA(self,eventKey,args, pid):
        self.TLCvbaWritten.append(args[1])       
        self.TLCjbWritten.append(args[0])
        
    def WP_FTL_HWD_WRITE_JB_VBA(self,eventKey,args, pid):
        self.SLCvbaWritten.append(args[1])       
        self.SLCjbWritten.append(args[0])
       
    def WP_PS_PF_DETECTED(self,eventKey,args, pid):
        self.PFdetected = True
        
    def WP_PS_EPWR_Failure(self, eventKeys, arg, processorID):
        self.EPWRFail = True   
    
    def WP_PS_BBM_PH_BLOCK_RELINK(self,eventKey,args, pid):
        if(args[4]== self.AddressBeforePFHandling['physicalblock'] and args[3]== self.AddressBeforePFHandling['plane']):
            self.RelinkingnotHappened = False
        else:
            self.RelinkingHappened = True
    
    def PFinjector(self,VBA):
        physical_address = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(VBA, 1)        
        phyAddress=[physical_address['die'],physical_address['plane'],physical_address['physicalblock'],physical_address['wordline'],physical_address['stringnumber'],0,0]
        errorPersistence = 1 
        paerrorDescription = (self.vtfContainer._livet.etProgramError ,errorPersistence,0,1,0,0)
        self.livetObj.GetFlash().InjectError(physical_address['channel'], phyAddress, paerrorDescription)
        self.logger.Info(self.globalVarsObj.TAG, 'PF is injected to ',physical_address)
                
    
    def ResetVariables(self):
        self.writtendata = []
        self.PFdetected = False
        self.EPWRFail = False
        self.RelinkingHappened = False
        self.VBAtowhichErrorwasinjected = None
        self.AddressAfterPFHandling = None
        self.AddressBeforePFHandling = None
        self.SLCvbaWritten = []
        self.SLCjbWritten = []
        self.TLCvbaWritten = []
        self.TLCjbWritten = []   
        self.BlockAddedToPartialList = -1
    
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)
               
    
    
    def EPWRfailonTLC(self, Blockstate, **kwargs):
        startLba = 0
        self.logger.Info(self.globalVarsObj.TAG, '************* ENTERING Dest TLC PF HANDLER *************')
        
        if ('startLba' in kwargs.keys()):
            startLba = kwargs['ErrorVBA']
        else:
            startLba = 0
        
        if('ErrorVBA' in kwargs.keys()):
            #Already have a VBA to inject error
            VBAtowhichErrorwasinjected = kwargs['ErrorVBA'] + 48
            
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.PFinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforePFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection :',self.AddressBeforePFHandling)
        
        else:
            #Trigger Host Writes
            #########################
            self.cmdpAPLib.DoMeasuredSequentialWrite(startLba=startLba, numberOfWrites=None, sectorsToBeWritten=1024 * 1024 * 10 +1000, txLenThreshold=None)
            ########################            
            
            VBAtowhichErrorwasinjected = self.TLCvbaWritten[-1] + 48
            self.VBAtowhichErrorwasinjected = VBAtowhichErrorwasinjected
            self.PFinjector(self.VBAtowhichErrorwasinjected)
            self.logger.Info(self.globalVarsObj.TAG, 'VBA to which error is injected :',self.VBAtowhichErrorwasinjected)
            self.AddressBeforePFHandling = self.globalVarsObj.sctpUtilsObj.TranslateVbaToDeVbaAndPba(self.VBAtowhichErrorwasinjected, 1)
            self.logger.Info(self.globalVarsObj.TAG, 'Physical Address before PF Detection :',self.AddressBeforePFHandling)
            

        #########################
        self.cmdpAPLib.DoMeasuredSequentialWrite(startLba=startLba, numberOfWrites=None, sectorsToBeWritten=1000, txLenThreshold=None)
        
        ######################## 
        
        
        if(not self.PFdetected):
            self.logger.Info(self.globalVarsObj.TAG, "PF wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False
        
        if(not self.EPWRFail):
            self.logger.Info(self.globalVarsObj.TAG, "EPWR fail wasn't detected")
            self.logger.Info(self.globalVarsObj.TAG, '***************** EXITING HANDLER *******************')
            self.ResetVariables()
            self.DeregisterAllWaypoint()
            return False                     
        
        
        self.logger.Info(self.globalVarsObj.TAG, "############ TLC EPWR fail handling SUCCESSFULL###############")
        self.ResetVariables()
        self.DeregisterAllWaypoint()
        return True            
        
