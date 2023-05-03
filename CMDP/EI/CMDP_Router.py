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
            return self.HandlePF(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)
        elif combinationForCurrentTest['ErrorType']=='WriteAbort':
            return self.HandleWA(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)
        elif combinationForCurrentTest['ErrorType']=='UECC':
            return self.HandleUECC(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)
        elif combinationForCurrentTest['ErrorType']=='WriteAbortSwitch':
            return self.HandleWAswitch(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)        
        elif combinationForCurrentTest['ErrorType']=='EraseFailure':
            return self.HandleEF(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)        
        elif combinationForCurrentTest['ErrorType'] in ['HB', 'SB1', 'SB2', 'CECC']:
            return self.HandleCECC(errorPhase=combinationForCurrentTest['ErrorPhase'], BlockState=combinationForCurrentTest['BlockState'], combination_=combinationForCurrentTest, EINobj = EINCTDobj)                
        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandleError(), Error Type does not exist/supported')         
        
    def HandleCECC(self,errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'DuringWriteToMIPBlock'):
            import Control_blocks.CECCHandlingonCONTROLblocks as CECCHandlingonCONTROLblocks
            self.HandlerObj = CECCHandlingonCONTROLblocks.CECChandler()
            return self.HandlerObj.CECCHandlerMIP(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToGATBlock'):
            import Control_blocks.CECCHandlingonCONTROLblocks as CECCHandlingonCONTROLblocks
            self.HandlerObj = CECCHandlingonCONTROLblocks.CECChandler()
            return self.HandlerObj.CECCHandlerGAT(BlockState, **kwargs)       
        
        elif(errorPhase == 'DuringWriteToXORBlock'):
            import Control_blocks.CECCHandlingonCONTROLblocks as CECCHandlingonCONTROLblocks
            self.HandlerObj = CECCHandlingonCONTROLblocks.CECChandler()
            return self.HandlerObj.CECCHandlerXOR(BlockState, **kwargs)
        
        elif(errorPhase == 'HostSLC'):
            import Host_blocks.CECCHandlingonHOSTblocks as CECCHandlingonHOSTblocks
            self.HandlerObj = CECCHandlingonHOSTblocks.CECChandler()
            return self.HandlerObj.CECCHandlerSLC(BlockState, **kwargs)

        elif(errorPhase == 'HostTLC'):
            import Host_blocks.CECCHandlingonHOSTblocks as CECCHandlingonHOSTblocks
            self.HandlerObj = CECCHandlingonHOSTblocks.CECChandler()
            return self.HandlerObj.CECCHandlerTLC(BlockState, **kwargs)        
        
        
    def HandleUECC(self, errorPhase, BlockState, **kwargs):
        global g_errorType
        if(errorPhase == 'DuringWriteToMIPBlock'):
            import Control_blocks.UECCHandlingonCONTROLblocks as UECCHandlingonCONTROLblocks
            self.HandlerObj = UECCHandlingonCONTROLblocks.UECChandler()
            return self.HandlerObj.UECCHandlerMIP(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToGATBlock'):
            import Control_blocks.UECCHandlingonCONTROLblocks as UECCHandlingonCONTROLblocks
            self.HandlerObj = UECCHandlingonCONTROLblocks.UECChandler()
            return self.HandlerObj.UECCHandlerGAT(BlockState, **kwargs)      

        elif(errorPhase == 'HostSLC'):
            import Host_blocks.UECCHandlingonHOSTblocks as UECCHandlingonHOSTblocks
            self.HandlerObj = UECCHandlingonHOSTblocks.UECChandler()
            return self.HandlerObj.UECCHandlerSLC(BlockState, **kwargs)

        elif(errorPhase == 'HostTLC'):
            import Host_blocks.UECCHandlingonHOSTblocks as UECCHandlingonHOSTblocks
            self.HandlerObj = UECCHandlingonHOSTblocks.UECChandler()
            return self.HandlerObj.UECCHandlerTLC(BlockState, **kwargs)        

        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import Infra_blocks.UECCHandlingonINFRAblocks as UECCHandlingonINFRAblocks
            self.HandlerObj = UECCHandlingonINFRAblocks.UECChandler()
            return self.HandlerObj.UECCHandlerBOOT(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToFSBlock'):
            import Infra_blocks.WAHandlingonINFRAblocks as WAHandlingonINFRAblocks
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
        if(errorPhase == 'DuringWriteToMIPBlock'):
            import Control_blocks.WAHandlingonCONTROLblocks as WAHandlingonCONTROLblocks
            self.HandlerObj = WAHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerMIP(BlockState, **kwargs)

        elif(errorPhase == 'DuringWriteToGATBlock'):
            import Control_blocks.WAHandlingonCONTROLblocks as WAHandlingonCONTROLblocks
            self.HandlerObj = WAHandlingonCONTROLblocks.WAhandler()
            return self.HandlerObj.WAHandlerGAT(BlockState, **kwargs)

        elif(errorPhase == 'HostSLC'):
            import Host_blocks.WAHandlingonHOSTblocks as WAHandlingonHOSTblocks
            self.HandlerObj = WAHandlingonHOSTblocks.WAhandler()
            return self.HandlerObj.WAHandlerSLC(BlockState, **kwargs)

        elif(errorPhase == 'HostTLC'):
            import Host_blocks.WAHandlingonHOSTblocks as WAHandlingonHOSTblocks
            self.HandlerObj = WAHandlingonHOSTblocks.WAhandler()
            return self.HandlerObj.WAHandlerTLC(BlockState, **kwargs)        

        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import Infra_blocks.WAHandlingonINFRAblocks as WAHandlingonINFRAblocks
            self.HandlerObj = WAHandlingonINFRAblocks.WAhandler()
            return self.HandlerObj.WAHandlerBOOT(BlockState, **kwargs)


        elif(errorPhase == 'DuringWriteToFSBlock'):
            import Infra_blocks.WAHandlingonINFRAblocks as WAHandlingonINFRAblocks
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
        if(errorPhase == 'DuringWriteToGATBlock') :
            import Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
            self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
            return self.HandlerObj.PFHandlerGAT(BlockState, **kwargs)
                        
        elif(errorPhase == 'DuringWriteToMIPBlock'):
            import Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
            self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
            return self.HandlerObj.PFHandlerMIP(BlockState, **kwargs)

        elif(errorPhase == 'HostSLC'):
            import Host_blocks.PFHandlingonHOSTblocks as PFHandlingonHOSTblocks
            self.HandlerObj = PFHandlingonHOSTblocks.PFhandler()
            return self.HandlerObj.PFHandlerSLC(BlockState, **kwargs)
            
        elif(errorPhase == 'HostTLC'):
            import Host_blocks.PFHandlingonHOSTblocks as PFHandlingonHOSTblocks
            self.HandlerObj = PFHandlingonHOSTblocks.PFhandler()
            return self.HandlerObj.PFHandlerTLC(BlockState, **kwargs)        

        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import Infra_blocks.PFHandlingonINFRAblocks as PFHandlingonINFRAblocks
            self.HandlerObj = PFHandlingonINFRAblocks.PFhandler()
            return self.HandlerObj.PFHandlerBOOT(BlockState, **kwargs)
        
        elif(errorPhase == 'DuringWriteToFSBlock'):
            import Infra_blocks.PFHandlingonINFRAblocks as PFHandlingonINFRAblocks
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

        elif (str(errorPhase).upper().strip()).startswith(str('DuringSLCtoTLCRelocationAndFailure').upper().strip()):
            import CMDP_Relocation.RelocationRouter as RelocationRouterHandler
            self.relocationRouterObj = RelocationRouterHandler.RelocationRouter()
            return self.relocationRouterObj.HandlerForCMDPRelocation(g_errorType, errorPhase, BlockState, **kwargs) # PF or WA or UECC will be always on TLC block, not on SLC block

        elif(str(errorPhase).upper().strip()).startswith(str('DuringTLCtoTLCRelocationAndFailure').upper().strip()):
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
        
        elif(errorPhase == 'DuringWriteToGATBlock'):
            import Control_blocks.EFAndEAHandlingonCONTROLblocks as EFAndEAHandlingonCONTROLblocks
            self.HandlerObj = EFAndEAHandlingonCONTROLblocks.EFhandler()
            return self.HandlerObj.EFAndEAHandlerGAT(BlockState, **kwargs)  
        
        elif(errorPhase == 'DuringWriteToMIPBlock'):
            import Control_blocks.EFAndEAHandlingonCONTROLblocks as EFAndEAHandlingonCONTROLblocks
            self.HandlerObj = EFAndEAHandlingonCONTROLblocks.EFhandler()
            return self.HandlerObj.EFAndEAHandlerMIP(BlockState, **kwargs)  
        
        elif(errorPhase == 'DuringWriteToFSBlock'):
            import Infra_blocks.EFAndEAHandlingonINFRAblocks as EFAndEAHandlingonINFRAblocks
            self.HandlerObj = EFAndEAHandlingonINFRAblocks.EFhandler()
            return self.HandlerObj.EFAndEAHandlerIFS(BlockState, **kwargs)
        
        elif(errorPhase == 'DuringWriteToBOOTBlock'):
            import Infra_blocks.EFAndEAHandlingonINFRAblocks as EFAndEAHandlingonINFRAblocks
            self.HandlerObj = EFAndEAHandlingonINFRAblocks.EFhandler()
            return self.HandlerObj.EFAndEAHandlerBOOT(BlockState, **kwargs)        
        
        else:
            raise ValidationError.ParameterDoesNotExist(module='CMDP Router Library', baseErrorDescription='In HandlePF(), Error Phase: %s does not exist/supported')%(errorPhase)

    def __del__(self): 
        print('Destructor called, Instance deleted.')             
