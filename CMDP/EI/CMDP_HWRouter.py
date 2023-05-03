import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap

g_errorType = None

class Router:
    
    __staticPFObj = None

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not Router.__staticPFObj:
            Router.__staticPFObj = super(Router,cls).__new__(cls, *args, **kwargs)

        return Router.__staticPFObj

    def HandleError(self, combinationForCurrentTest, EINCTDobj):
        global g_errorType
        g_errorType = str(combinationForCurrentTest['ErrorType']).upper().strip()
        if combinationForCurrentTest['ErrorType']=='ProgramFailure':
            return self.HandlePF(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], ModeAfterSwitch=combinationForCurrentTest['ModeAfterSwitch'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)
        elif combinationForCurrentTest['ErrorType']=='WriteAbort':
            return self.HandleWA(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], ModeAfterSwitch=combinationForCurrentTest['ModeAfterSwitch'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)
        elif combinationForCurrentTest['ErrorType']=='UncorrectableECC_DecodeFail':
            return self.HandleUECC(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], ModeAfterSwitch=combinationForCurrentTest['ModeAfterSwitch'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)
        elif combinationForCurrentTest['ErrorType']=='WriteAbortSwitch':
            return self.HandleWAswitch(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], ModeAfterSwitch=combinationForCurrentTest['ModeAfterSwitch'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)        
        elif combinationForCurrentTest['ErrorType']=='EraseFailure':
            return self.HandleEF(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], ModeAfterSwitch=combinationForCurrentTest['ModeAfterSwitch'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)        
        elif combinationForCurrentTest['ErrorType'] in ['SLC_BES7', 'SLC_BES5', 'SLC_ReadRetry']:
            return self.HandleCECC(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], ModeAfterSwitch=combinationForCurrentTest['ModeAfterSwitch'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)                
        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandleError(), Error Type does not exist/supported')         
        
    def HandleCECC(self, errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'DuringWriteToMTMBlock'):
            import Control_blocks.CECCHandlingonCONTROLblocks as CECCHandlingonCONTROLblocks
            self.HandlerObj = CECCHandlingonCONTROLblocks.CECChandler()
            return self.HandlerObj.CECCHandlerMTM(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToLogBlock'):
            import Control_blocks.CECCHandlingonCONTROLblocks as CECCHandlingonCONTROLblocks
            self.HandlerObj = CECCHandlingonCONTROLblocks.CECChandler()
            return self.HandlerObj.CECCHandlerLOG(BlockState, **kwargs)        
        
        elif(errorPhase == 'DuringWriteToXORBlock'):
            import Control_blocks.CECCHandlingonCONTROLblocks as CECCHandlingonCONTROLblocks
            self.HandlerObj = CECCHandlingonCONTROLblocks.CECChandler()
            return self.HandlerObj.CECCHandlerXOR(BlockState, **kwargs)
        
    def HandleUECC(self, errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'DuringWriteToMTMBlock'):
            import HW.Control_blocks.UECCHandlingonCONTROLblocks as UECCHandlingonCONTROLblocks
            self.HandlerObj = UECCHandlingonCONTROLblocks.UECChandler()
            return self.HandlerObj.UECCHandlerMTM(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToLogBlock'):
            import Control_blocks.UECCHandlingonCONTROLblocks as UECCHandlingonCONTROLblocks
            self.HandlerObj = UECCHandlingonCONTROLblocks.UECChandler()
            return self.HandlerObj.UECCHandlerLOG(BlockState, **kwargs)

        elif(errorPhase == 'HostSLC'):
            import HW.Host_blocks.UECCHandlingonHOSTblocks as UECCHandlingonHOSTblocks
            self.HandlerObj = UECCHandlingonHOSTblocks.UECChandler()
            return self.HandlerObj.UECCHandlerSLC(BlockState, **kwargs)

        elif(errorPhase == 'HostTLC'):
            import Host_blocks.UECCHandlingonHOSTblocks as UECCHandlingonHOSTblocks
            self.HandlerObj = UECCHandlingonHOSTblocks.UECChandler()
            return self.HandlerObj.UECCHandlerTLC(BlockState, **kwargs)        

        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import HW.Infra_blocks.UECCHandlingonINFRAblocks as UECCHandlingonINFRAblocks
            self.HandlerObj = UECCHandlingonINFRAblocks.UECChandler()
            return self.HandlerObj.UECCHandlerBOOT(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToXORBlock'):
            import Control_blocks.UECCHandlingonCONTROLblocks as UECCHandlingonCONTROLblocks
            self.HandlerObj = UECCHandlingonCONTROLblocks.UECChandler()
            return self.HandlerObj.UECCHandlerXOR(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToFSBlock'):
            import HW.Infra_blocks.UECCHandlingonINFRAblocks as UECCHandlingonINFRAblocks
            self.HandlerObj = UECCHandlingonINFRAblocks.UECChandler()
            return self.HandlerObj.UECCHandlerIFS(BlockState, **kwargs)

        elif str(errorPhase).upper().strip()  == str('DuringSLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        elif str(errorPhase).upper().strip() == str('DuringTLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandleUECC(), Error Phase does not exist/supported')        
    
    
    def HandleWAswitch(self, errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'DuringWriteToMTMBlock'):
            import Control_blocks.WASwitchHandlingonCONTROLblocks as WASwitchHandlingonCONTROLblocks
            self.HandlerObj = WASwitchHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerMTM(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToLogBlock'):
            import Control_blocks.WASwitchHandlingonCONTROLblocks as WASwitchHandlingonCONTROLblocks
            self.HandlerObj = WASwitchHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerLOG(BlockState, **kwargs)

        elif(errorPhase == 'HostSLC'):
            import Host_blocks.WASwitchHandlingonHOSTblocks as WASwitchHandlingonHOSTblocks
            self.HandlerObj = WASwitchHandlingonHOSTblocks.WAhandler()
            return self.HandlerObj.WAHandlerSLC(BlockState, **kwargs)

        elif(errorPhase == 'HostTLC'):
            import Host_blocks.WASwitchHandlingonHOSTblocks as WASwitchHandlingonHOSTblocks
            self.HandlerObj = WASwitchHandlingonHOSTblocks.WAhandler()
            return self.HandlerObj.WAHandlerTLC(BlockState, **kwargs)        

        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import Infra_blocks.WASwitchHandlingonINFRAblocks as WASwitchHandlingonINFRAblocks
            self.HandlerObj = WASwitchHandlingonINFRAblocks.WAhandler()
            return self.HandlerObj.WAHandlerBOOT(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToXORBlock'):
            import Control_blocks.WASwitchHandlingonCONTROLblocks as WASwitchHandlingonCONTROLblocks
            self.HandlerObj = WASwitchHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerXOR(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToFSBlock'):
            import Infra_blocks.WASwitchHandlingonINFRAblocks as WASwitchHandlingonINFRAblocks
            self.HandlerObj = WASwitchHandlingonINFRAblocks.WAhandler()
            return self.HandlerObj.WAHandlerIFS(BlockState, **kwargs)

        elif str(errorPhase).upper().strip()  == str('DuringSLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        elif str(errorPhase).upper().strip() == str('DuringTLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandleWA(), Error Phase does not exist/supported')        
    
    
    def HandleWA(self, errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'DuringWriteToMTMBlock'):
            import Control_blocks.WAHandlingonCONTROLblocks as WAHandlingonCONTROLblocks
            self.HandlerObj = WAHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerMTM(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToLogBlock'):
            import HW.Control_blocks.WAHandlingonCONTROLblocks as WAHandlingonCONTROLblocks
            self.HandlerObj = WAHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerLOG(BlockState, **kwargs)

        elif(errorPhase == 'HostSLC'):
            import HW.Host_blocks.WAHandlingonHOSTblocks as WAHandlingonHOSTblocks
            self.HandlerObj = WAHandlingonHOSTblocks.WAhandler()
            return self.HandlerObj.WAHandlerSLC(BlockState, **kwargs)

        elif(errorPhase == 'HostTLC'):
            import HW.Host_blocks.WAHandlingonHOSTblocks as WAHandlingonHOSTblocks
            self.HandlerObj = WAHandlingonHOSTblocks.WAhandler()
            return self.HandlerObj.WAHandlerTLC(BlockState, **kwargs)        

        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import Infra_blocks.WAHandlingonINFRAblocks as WAHandlingonINFRAblocks
            self.HandlerObj = WAHandlingonINFRAblocks.WAhandler()
            return self.HandlerObj.WAHandlerBOOT(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToXORBlock'):
            import HW.Control_blocks.WAHandlingonCONTROLblocks as WAHandlingonCONTROLblocks
            self.HandlerObj = WAHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerXOR(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToFSBlock'):
            import HW.Infra_blocks.WAHandlingonINFRAblocks as WAHandlingonINFRAblocks
            self.HandlerObj = WAHandlingonINFRAblocks.WAhandler()
            return self.HandlerObj.WAHandlerIFS(BlockState, **kwargs)

        elif str(errorPhase).upper().strip()  == str('DuringSLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        elif str(errorPhase).upper().strip() == str('DuringTLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandleWA(), Error Phase does not exist/supported')        


    def HandlePF(self, errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'DuringWriteToMTMBlock'):
            import HW.Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
            self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
            return self.HandlerObj.PFHandlerMTM(BlockState, **kwargs)
                        
        elif(errorPhase == 'DuringWriteToLogBlock'):
            import HW.Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
            self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
            return self.HandlerObj.PFHandlerLOG(BlockState, **kwargs)

        elif(errorPhase == 'HostSLC'):
            import HW.Host_blocks.PFHandlingonHOSTblocks as PFHandlingonHOSTblocks
            self.HandlerObj = PFHandlingonHOSTblocks.PFhandler()
            return self.HandlerObj.PFHandlerSLC(BlockState, **kwargs)
            
        elif(errorPhase == 'HostTLC'):
            import HW.Host_blocks.PFHandlingonHOSTblocks as PFHandlingonHOSTblocks
            self.HandlerObj = PFHandlingonHOSTblocks.PFhandler()
            return self.HandlerObj.PFHandlerTLC(BlockState, **kwargs)        

        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import HW.Infra_blocks.PFHandlingonINFRAblocks as PFHandlingonINFRAblocks
            self.HandlerObj = PFHandlingonINFRAblocks.PFhandler()
            return self.HandlerObj.PFHandlerBOOT(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToXORBlock'):
            import HW.Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
            self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
            return self.HandlerObj.PFHandlerXOR(BlockState, **kwargs)
        
        elif(errorPhase == 'DuringWriteToFSBlock'):
            import HW.Infra_blocks.PFHandlingonINFRAblocks as PFHandlingonINFRAblocks
            self.HandlerObj = PFHandlingonINFRAblocks.PFhandler()
            return self.HandlerObj.PFHandlerIFS(BlockState, **kwargs)
			
        elif(errorPhase == 'HostTLCEPWRFail'):
            import Host_blocks.EPWRFailInPcie as EPWRFailInPcie
            self.HandlerObj = EPWRFailInPcie.EPWRFAILHandler()
            return self.HandlerObj.EPWRfailonTLCPCIE(BlockState, **kwargs)
        
        elif(errorPhase == 'DestTLCEPWRFail'):
            import Dest_blocks.EPWRFailSDTLC as EPWRFailSDTLC
            self.HandlerObj = EPWRFailSDTLC.EPWRFAILSDHandler()
            return self.HandlerObj.EPWRfailonSDTLC(BlockState, **kwargs)

        elif(errorPhase == 'PCIEDestTLCEPWRFail'):
            import Dest_blocks.EPWRFailonDestTLC as EPWRFailonDestTLC
            self.HandlerObj = EPWRFailonDestTLC.EPWRfailDestTLCHandler()
            return self.HandlerObj.EPWRfailonDestTLC(BlockState, **kwargs)
        
        elif str(errorPhase).upper().strip()  == str('DuringSLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        elif str(errorPhase).upper().strip() == str('DuringTLCtoTLCRelocation').upper().strip():
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandlePF(), Error Phase does not exist/supported')
    
    def HandleEF(self, errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'HostSLC'):
            import Host_blocks.EFHandlingonHOSTblocks as EFHandlingonHOSTblocks
            self.HandlerObj = EFHandlingonHOSTblocks.EFhandler()
            return self.HandlerObj.EFhandlerSLC(BlockState, **kwargs)
            
        elif(errorPhase == 'HostTLC'):
            import Host_blocks.EFHandlingonHOSTblocks as EFHandlingonHOSTblocks
            self.HandlerObj = EFHandlingonHOSTblocks.EFhandler()
            return self.HandlerObj.EFhandlerTLC(BlockState, **kwargs)
        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandlePF(), Error Phase: %s does not exist/supported')%(errorPhase)

    def __del__(self): 
        print('Destructor called, Instance deleted.')             
