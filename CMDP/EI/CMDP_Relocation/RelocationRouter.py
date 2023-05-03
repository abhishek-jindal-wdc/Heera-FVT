##
#"""
#********************************************************************************
#@file        : RelocationRouter.py
#@brief       : This file contains Router to call the respective relocation APIs
#@author      : Ganesh Pathirakani
#@date(ORG)   : 20 APR 2020
#@copyright   : copyright (C) 2020 SanDisk a Western Digital brand
#********************************************************************************
#"""

import Protocol.NVMe.Basic.TestCase as TestCase
import RelocationBase as RelocationBase
import Core.ValidationError as ValidationError
import os
import ConfigParser
import Constants

startLba = 0
endLba = 0
status = False

STR_PROGRAM_FAILURE = 'PROGRAMFAILURE'
STR_WRITE_ABORT = 'WRITEABORT'
STR_UECC = 'UNCORRECTABLEECC_DECODEFAIL'
STR_WRITEABORTSWITCH = 'WRITEABORTSWITCH'

class RelocationRouter(TestCase.TestCase, RelocationBase.RelocationBase):
    def __init__(self):
        global startLba, endLba, status
        RelocationBase.RelocationBase.__init__(self)
        self.startLbaAndtlcLastWrittenVbaDict = {}
    
    def DeregisterAllWaypoint(self):
        self.WaypointRegObj.UnRegisterWP(self.wayPointDict)    
    
    def HandlerForCMDPRelocation(self, errorType, errorPhase, BlockState, **kwargs):
        self.logger.Info(self.globalVarsObj.TAG, '***************** ENTERING RELOCATION HANDLER *******************')
        global startLba, endLba, status
        self.initRlcWP()
        disableTheDiagnosticFlag = False
        readTheValueTemp = None
        readTheValue = None
        configDict = {}
        status = False
        self.relocationCallBackObj.destinationWriteJbVbaFlag = False
        #errorType = errorType
        errorType = str(errorType).upper().strip()
        errorPhase = str(errorPhase).upper().strip()
        BlockState = BlockState
        configDict = self.FillDictionaryConfigValues()

        getActiveProtocolValue = None
        getActiveProtocolValue = str(self.globalVarsObj.vtfContainer.getActiveProtocol()).upper().strip()        
        if getActiveProtocolValue == Constants.String_Constants.STR_NVMe_OF_SDPCIE:
            self.sctpUtilsObj.resetModeRoutingrules()
            self.ccmObj.DoFlushCache()

        if len(self.HistoryObj.HistoryObj.GlobalWriteData) <= 0:
            startLba = 0
        else:
            startLba = self.HistoryObj.HistoryObj.GlobalWriteData[-1][0]
        endLba = self.globalVarsObj.maxLba

        for key, value in configDict.iteritems():
            if configDict[key] == configDict['DiagFlag']:
                readTheValueTemp = configDict.get('DiagFlag', None)
                readTheValue = readTheValueTemp.get('GcSetMvpDiagDisable', None)
                if str(readTheValue).upper().strip() == Constants.String_Constants.STR_TRUE:
                    disableTheDiagnosticFlag = True

        self.relocationStatisticsDictBeforeRelocation(disableTheDiagnosticFlag=disableTheDiagnosticFlag)
        getActiveProtocol = None
        getActiveProtocol = str(self.globalVarsObj.vtfContainer.getActiveProtocol()).upper().strip()

        if getActiveProtocol == Constants.String_Constants.STR_SD_OF_SDPCIE:
            if(errorPhase == str('DuringSLCtoTLCRelocation').upper().strip()):
                status, startLba, endLba = self.triggerGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || SD mode -> failed at triggerGc() function execution" % str(errorPhase)

            elif(errorPhase == str('DuringTLCtoTLCRelocation').upper().strip()):
                status, startLba, endLba = self.triggerTlcGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || SD mode -> failed at triggerTlcGc() function execution" % str(errorPhase)

            elif errorPhase.startswith(str('DuringSLCtoTLCRelocationAndFailure').upper().strip()):
                status, startLba, endLba = self.triggerGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || SD mode -> failed at triggerGc() function execution" % str(errorPhase)

            elif errorPhase.startswith(str('DuringTLCtoTLCRelocationAndFailure').upper().strip()):
                status, startLba, endLba = self.triggerTlcGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || SD mode -> failed at triggerTlcGc() function execution" % str(errorPhase)

            else:
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), Given errorPhase - %s || does not exists in the Relocation Handler" % str(errorPhase)
                self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(),  Given errorPhase - %s || does not exists in the Relocation Handler" % str(errorPhase))

        #TODO: NVME mode TLC PF handling behavior to be verified and TODO: need to verify TLC part without routing diagnostics
        elif getActiveProtocol == Constants.String_Constants.STR_NVMe_OF_SDPCIE:
            if(errorPhase == str('DuringSLCtoTLCRelocation').upper().strip()):
                self.sctpUtilsObj.changeModeToSLC() # for seq SLC GC
                #status, startLba, endLba = self.performDifferentPercentageOfValidSectorsInHostSlcBlock(numberOfValidSectorsInOneSlcBlock=8)
                status, startLba, endLba = self.triggerNvmeGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || NVME mode -> failed at triggerNvmeGc() function execution" % str(errorPhase)

            elif(errorPhase == str('DuringTLCtoTLCRelocation').upper().strip()):
                self.sctpUtilsObj.changeModeToTLC() # for TLC GC
                #status, startLba, endLba = self.triggerTlcGc()
                status, startLba, endLba = self.triggerTlcNvmeGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || NVME mode -> failed at triggerTlcNvmeGc() function execution" % str(errorPhase)

            elif errorPhase.startswith(str('DuringSLCtoTLCRelocationAndFailure').upper().strip()):
                self.sctpUtilsObj.changeModeToSLC() # for seq SLC GC
                #status, startLba, endLba = self.performDifferentPercentageOfValidSectorsInHostSlcBlock(numberOfValidSectorsInOneSlcBlock=8)
                status, startLba, endLba = self.triggerNvmeGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || NVME mode -> failed at triggerNvmeGc() function execution" % str(errorPhase)

            elif errorPhase.startswith(str('DuringTLCtoTLCRelocationAndFailure').upper().strip()):
                self.sctpUtilsObj.changeModeToTLC() # for TLC GC
                #status, startLba, endLba = self.triggerTlcGc()
                status, startLba, endLba = self.triggerTlcNvmeGc(startLba, endLba)
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorPhase: %s || NVME mode -> failed at triggerTlcNvmeGc() function execution" % str(errorPhase)

            else:
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), Given errorPhase - %s || does not exists in the Relocation Handler" % str(errorPhase)
                self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Given errorPhase - %s || does not exists in the Relocation Handler" % str(errorPhase))
        else:
            if status is False:
                status = "FAIL: In HandlerForCMDPRelocation(), Invalid protocol mode type received from CVF API -> %s || the Relocation Handler" % str(getActiveProtocol)
            self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Invalid protocol mode type received from CVF API -> %s || the Relocation Handler" % str(getActiveProtocol))

  
        if self.relocationCallBackObj.relocationStartFlag is True and status is True:
            self.startLbaAndtlcLastWrittenVbaDict = kwargs.copy()
            self.startLbaAndtlcLastWrittenVbaDict['startLba'] = startLba
            self.startLbaAndtlcLastWrittenVbaDict['ErrorVBA'] = self.relocationCallBackObj.currentRelocationDestinationBlockVba
        else:          
            self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Relocation did not triggered for errorphase -> %s || errortype -> %s" % (str(errorPhase), str(errorType)))

        getActiveProtocolValue = None
        getActiveProtocolValue = str(self.globalVarsObj.vtfContainer.getActiveProtocol()).upper().strip()
        if getActiveProtocolValue == Constants.String_Constants.STR_NVMe_OF_SDPCIE:
            self.sctpUtilsObj.resetModeRoutingrules()
            self.ccmObj.DoFlushCache() 

        if status is True: # During relocation, always PF or WA or UECC handling to be performed on TLC block
            if errorType == STR_PROGRAM_FAILURE:
                if(errorPhase == str('DuringSLCtoTLCRelocationAndFailureOnMTMBlock').upper().strip()) or\
                  (errorPhase == str('DuringTLCtoTLCRelocationAndFailureOnMTMBlock').upper().strip()):
                    self.relocationStatisticsDictAfterRelocation()
                    import CMDP.Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
                    self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
                    status = self.HandlerObj.PFHandlerMTM(BlockState, **kwargs)
                    if status is not True:
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType)))
                        status = str(status) + "FAIL MSG FROM CMDP RLC: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType))
                    else:
                        status = self.performExtraWrite(self.HistoryObj.HistoryObj.GlobalWriteData[-1][0])
                        if status is not True:
                            status = 'FAIL: In performExtraWrite() - Failed during write operation'
                        status = self.readVerificationListData(self.HistoryObj.HistoryObj.GlobalWriteData)
                        if status is not True:
                            status = 'FAIL: In readVerificationListData(), Read verification failed'

                elif(errorPhase == str('DuringSLCtoTLCRelocationAndFailureOnLogBlock').upper().strip()) or\
                    (errorPhase == str('DuringTLCtoTLCRelocationAndFailureOnLogBlock').upper().strip()):
                    self.relocationStatisticsDictAfterRelocation()
                    import CMDP.Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
                    self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
                    status = self.HandlerObj.PFHandlerLOG(BlockState, **kwargs)
                    if status is not True:
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType)))
                        status = str(status) + "FAIL MSG FROM CMDP RLC: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType))
                    else:
                        status = self.performExtraWrite(self.HistoryObj.HistoryObj.GlobalWriteData[-1][0])
                        if status is not True:
                            status = 'FAIL: In performExtraWrite() - Failed during write operation'
                        status = self.readVerificationListData(self.HistoryObj.HistoryObj.GlobalWriteData)
                        if status is not True:
                            status = 'FAIL: In readVerificationListData(), Read verification failed'

                elif(errorPhase == str('DuringSLCtoTLCRelocationAndFailureOnXORBlock').upper().strip()) or\
                    (errorPhase == str('DuringTLCtoTLCRelocationAndFailureOnXORBlock').upper().strip()):
                    self.relocationStatisticsDictAfterRelocation()
                    import CMDP.Control_blocks.PFHandlingonCONTROLblocks as PFHandlingonCONTROLblocks
                    self.HandlerObj = PFHandlingonCONTROLblocks.PFhandler()
                    status = self.HandlerObj.PFHandlerXOR(BlockState, **kwargs)
                    if status is not True:
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType)))
                        status = str(status) + "FAIL MSG FROM CMDP RLC: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType))
                    else:
                        status = self.performExtraWrite(self.HistoryObj.HistoryObj.GlobalWriteData[-1][0])
                        if status is not True:
                            status = 'FAIL: In performExtraWrite() - Failed during write operation'
                        status = self.readVerificationListData(self.HistoryObj.HistoryObj.GlobalWriteData)
                        if status is not True:
                            status = 'FAIL: In readVerificationListData(), Read verification failed'

                elif(errorPhase == str('DuringSLCtoTLCRelocationAndFailureOnFSBlock').upper().strip()) or\
                    (errorPhase == str('DuringTLCtoTLCRelocationAndFailureOnFSBlock').upper().strip()):
                    self.relocationStatisticsDictAfterRelocation()
                    import CMDP.Infra_blocks.PFHandlingonINFRAblocks as PFHandlingonINFRAblocks
                    self.HandlerObj = PFHandlingonINFRAblocks.PFhandler()
                    status = self.HandlerObj.PFHandlerIFS(BlockState, **kwargs)
                    if status is not True:
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType)))
                        status = str(status) + "FAIL MSG FROM CMDP RLC: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType))
                    else:
                        status = self.performExtraWrite(self.HistoryObj.HistoryObj.GlobalWriteData[-1][0])
                        if status is not True:
                            status = 'FAIL: In performExtraWrite() - Failed during write operation'
                        status = self.readVerificationListData(self.HistoryObj.HistoryObj.GlobalWriteData)
                        if status is not True:
                            status = 'FAIL: In readVerificationListData(), Read verification failed'

                elif(errorPhase == str('DuringSLCtoTLCRelocationAndFailureOnBootBlock').upper().strip()) or\
                    (errorPhase == str('DuringTLCtoTLCRelocationAndFailureOnBootBlock').upper().strip()):
                    self.relocationStatisticsDictAfterRelocation()
                    import CMDP.Infra_blocks.PFHandlingonINFRAblocks as PFHandlingonINFRAblocks
                    self.HandlerObj = PFHandlingonINFRAblocks.PFhandler()
                    status = self.HandlerObj.PFHandlerBOOT(BlockState, **kwargs)
                    if status is not True:
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType)))
                        status = str(status) + "FAIL MSG FROM CMDP RLC: In HandlerForCMDPRelocation(), Failed at errorPhase: %s || errorType: %s || on CMDP Relocation Router during Program Failure" % (str(errorPhase), str(errorType))
                    else:
                        status = self.performExtraWrite(self.HistoryObj.HistoryObj.GlobalWriteData[-1][0])
                        if status is not True:
                            status = 'FAIL: In performExtraWrite() - Failed during write operation'
                        status = self.readVerificationListData(self.HistoryObj.HistoryObj.GlobalWriteData)
                        if status is not True:
                            status = 'FAIL: In readVerificationListData(), Read verification failed'

                else:
                    import CMDP.Host_blocks.PFHandlingonHOSTblocks as PFHandlingonHOSTblocks
                    self.HandlerObj = PFHandlingonHOSTblocks.PFhandler()
                    status = self.HandlerObj.PFHandlerTLC(BlockState, **self.startLbaAndtlcLastWrittenVbaDict)
                    self.relocationStatisticsDictAfterRelocation()

            elif errorType == STR_WRITE_ABORT:
                import CMDP.Host_blocks.WAHandlingonHOSTblocks as WAHandlingonHOSTblocks
                self.HandlerObj = WAHandlingonHOSTblocks.WAhandler()
                status = self.HandlerObj.WAHandlerTLC(BlockState, **self.startLbaAndtlcLastWrittenVbaDict)
                self.relocationStatisticsDictAfterRelocation()

            elif errorType == STR_UECC:
                import CMDP.Host_blocks.UECCHandlingonHOSTblocks as UECCHandlingonHOSTblocks
                self.HandlerObj = UECCHandlingonHOSTblocks.UECChandler()
                status = self.HandlerObj.UECCHandlerTLC(BlockState, **self.startLbaAndtlcLastWrittenVbaDict)
                self.relocationStatisticsDictAfterRelocation()

            elif errorType == STR_WRITEABORTSWITCH:
                import CMDP.Host_blocks.WASwitchHandlingonHOSTblocks as WASwitchHandlingonHOSTblocks
                self.HandlerObj = WASwitchHandlingonHOSTblocks.WAhandler()
                status = self.HandlerObj.WAHandlerTLC(BlockState, **self.startLbaAndtlcLastWrittenVbaDict)
                self.relocationStatisticsDictAfterRelocation()
            else:
                #status = False
                if status is False:
                    status = "FAIL: In HandlerForCMDPRelocation(), errorType: %s || Invalid error type passed to RelocationRouter" % str(errorType)
                self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), errorType: %s || Invalid error type passed to RelocationRouter" % str(errorType))
        #else:
            #self.logger.Info(self.globalVarsObj.TAG, "FAIL: In HandlerForCMDPRelocation(), %s did not triggered successfully" % str(errorPhase))

        getActiveProtocolValue = None
        getActiveProtocolValue = str(self.globalVarsObj.vtfContainer.getActiveProtocol()).upper().strip()
        if getActiveProtocolValue == Constants.String_Constants.STR_NVMe_OF_SDPCIE:
            self.sctpUtilsObj.resetModeRoutingrules()
            self.ccmObj.DoFlushCache()            
        self.DeregisterAllWaypoint()
        return status

