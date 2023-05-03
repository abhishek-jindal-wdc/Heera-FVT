##
#"""
#********************************************************************************
#@file        : RelocationBase.py
#@brief       : This file contains Common APIs and parameters that are being used by all test cases which inherite from this class.
#@author      : Ganesh Pathirakani
#@date(ORG)   : 20 APR 2020
#@copyright   : copyright (C) 2020 SanDisk a Western Digital brand
#********************************************************************************
#"""

import AccessPatternLib
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import Constants
import Utils
import RelocationCallBack as RelocationCallBack
import RelocationThresholds as RelocationThresholds
import WaypointReg
import SctpUtils
import SDUtils
#import ErrorInjectorLib as ErrorInjectorLib
#import ErrorInjectionUtils as ErrorInjectionUtils
from collections import OrderedDict
import ConfigParser
import os
import CMDP.CMDP_History as History

g_string_print_length = 45

startLba = None
endLba = None

##
# @brief A class to init common parameters and run common APIs
# @details Class contains different writes and read algorithms
class RelocationBase(object):
    ##
    # @brief A method to instantiate and define variables used by test cases
    # @details Here we instantiate objects of GlobalVars and Common Code Manager modules. 
    # Also read the input parameters from the XML Config file and assign it to local variables
    # Register WP dictionary in case test is running on Model platform
    def __init__(self):
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
        self.livetObj = self.globalVarsObj.vtfContainer._livet
        self.logger = self.globalVarsObj.logger 
        self.ccmObj = self.globalVarsObj.ccmObj   
        self.accessPatternObj = AccessPatternLib.AccessPatternLib()
        self.utilsObj = Utils.Utils()
        self.sctpUtilsObj = SctpUtils.SctpUtils()            
        self.sdUtilsObj = SDUtils.SDUtils()
        self.randomObj = self.globalVarsObj.randomObj
        self.HistoryObj = History.EpicCallbacks()        
        #self.errInjectorLibObj = ErrorInjectorLib.ErrorInjectorLib(self.globalVarsObj.vtfContainer, self.logger)
        #self.errInjectorUtilsObj = ErrorInjectionUtils.ErrorInjectionUtils()        

        configDict = self.FillDictionaryConfigValues()
        for key, value in configDict.iteritems():
            if configDict[key] == configDict['DiagFlag']:
                readTheValueTemp = configDict.get('DiagFlag', None)
                readSlcTheValue = readTheValueTemp.get('slcThresholdValue', None)
                readTlcTheValue = readTheValueTemp.get('tlcThresholdValue', None)
                self.slcThrsCfgValue = int(readSlcTheValue)
                self.tlcThrsCfgValue = int(readTlcTheValue)        
        
        if self.slcThrsCfgValue is None or self.tlcThrsCfgValue is None:
            self.slcThrsCfgValue = -25
            self.tlcThrsCfgValue = -45

        self.numOfFIMs = Constants.PS_CONSTANTS.NUM_OF_FIMS
        self.numOfDiesPerFim = self.sdUtilsObj.getDieConfigurationNumber()
        self.numOfPlanesPerDie = Constants.PS_CONSTANTS.PLANES_PER_PHY_BLK
        self.numOfSectorsPerPhyPage = Constants.PS_CONSTANTS.BYTES_PER_PHY_PAGE / Constants.PS_CONSTANTS.NUM_SECTORS_PER_LWL #Ans: 32 -> 16KB per physical page, 32sectors (32 * 512bytes = 16384bytes)
        self.numOfString = Constants.PS_CONSTANTS.NUM_OF_LOGICAL_WL_PER_PHY_WL
        self.pagesInSlcWL = Constants.PS_CONSTANTS.PAGES_IN_SLC_LWL
        self.pagesInTlcWL = Constants.PS_CONSTANTS.PAGES_IN_TLC_LWL
        self.slcBlockOneJWLSizeInSectors = self.numOfFIMs * self.numOfDiesPerFim * self.numOfPlanesPerDie * self.numOfSectorsPerPhyPage * self.numOfString * self.pagesInSlcWL # 2 * 2 * 2* 32 * 4 = 1024 sectors (512KB)
        self.oneSlcJwlFmus = self.slcBlockOneJWLSizeInSectors / Constants.SectorsInKB.SECTORS_IN_4KB
        
        #Relocation: Number of times WP_FTL_RLC_WRITE_JB_VBA required to hit value (self.numOfTimesToWriteOneTlcJwl) to write on TLC JWL
        self.oneTlcJwlInFmus = self.oneSlcJwlFmus * self.pagesInTlcWL
        self.numOfTimesToWriteOneTlcJwl = self.oneTlcJwlInFmus / RelocationThresholds.NUM_OF_FMUS_COPIED_IN_RLC_WRITE_JB_VBA_WP

        self.totalWL = self.sdUtilsObj.getTotalWlNumber()
        self.oneSlcBlockSizeInSectors = self.totalWL * self.slcBlockOneJWLSizeInSectors #65536 sectors and one SLC block size in MB is 32MB for above configurations (2D_2P with 2FIM)

        #Variable initialization
        global startLba, endLba
        self.startLba = None
        self.endLba = None
        self.transferLen = 0
        self.vbaInjectedWithPfSofar = []
        self.vbaInjectedWithPfSofarDictMapping = OrderedDict()
        self.onceFlag = False
        self.onceFlag = True
        self.firstInjectedPfPlaneDict = {}
        self.firstPfInjectdOnSamePlaneFlag = False
                        
        self.relocationStatisticsDictBeforeGcValue = OrderedDict()
        self.relocationStatisticsDictAfterGcValue = OrderedDict()
        self.deviceCurrentModeValue = None
        self.lbaWrittenDict = OrderedDict() #lba:transferLenght
        
        self.slcBalancedGcFblValue = None
        self.slcUrgentGcFblValue = None
        self.tlcBalancedGcFblValue = None
        self.tlcUrgentGcFblValue = None
        
        self.disableTheDiagnosticFlag = None
        self.slcThresholdBalancedValueWithoutRelocationThresholdDiag = None
        self.slcThresholdUrgentValueWithoutRelocationThresholdDiag = None
        self.tlcThresholdBalancedValueWithoutRelocationThresholdDiag = None
        self.tlcThresholdUrgentValueWithoutRelocationThresholdDiag = None 

        self.slcBlockId = list()
        self.tlcBlockId = list()
        self.slcBlockIdDictionary = dict()
        self.tlcBlockIdDictionary = dict()
        self.outputDictionary = dict()
        self.tempDataTuple = tuple()
        self.tempKeyValue = list()
        self.physicalAddressBeforeInjectPf = dict()
        self.pfInjectedFlag = False
        self.efInjectedFlag = False
        self.writeAbortInjectedFlag = False
        self.wayPointDict = {}

        ##Way point registration
        #if self.globalVarsObj.vtfContainer.isModel is True:
            ##Way point object and Attribute initialization
            #self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj,
                                                                      #self.logger,
                                                                      #self.globalVarsObj)
            #self.WaypointRegObj.printArguments = True
            #self.relocationCallBackObj = RelocationCallBack.RelocationCallBack()
            #self.wayPointDict = {
                #'WP_HOST_READ_COMPLETE'            : [self.relocationCallBackObj.CB_WP_HOST_READ_COMPLETE],
                #'WP_HOST_WRITE_COMPLETE'           : [self.relocationCallBackObj.CB_WP_HOST_WRITE_COMPLETE],
                #'WP_FTL_HWD_WRITE_JB_VBA'          : [self.relocationCallBackObj.CB_WP_FTL_HWD_WRITE_JB_VBA],
                #'WP_FTL_BML_JUMBOBLOCK_ALLOCATED'  : [self.relocationCallBackObj.CB_WP_FTL_BML_JUMBOBLOCK_ALLOCATED],
                ##"WP_FTL_RLC_RLC_START"             : [self.relocationCallBackObj.CB_WP_FTL_RLC_RLC_START],
                #"WP_FTL_RLC_RLC_COMPLETE"          : [self.relocationCallBackObj.CB_WP_FTL_RLC_RLC_COMPLETE],
                #"WP_FTL_OBM_JUMBO_BLOCK_ALLOC"     : [self.relocationCallBackObj.CB_WP_FTL_OBM_JUMBO_BLOCK_ALLOC],
                #"WP_FTL_RLC_SOURCE_BLOCK_SELECTED" : [self.relocationCallBackObj.CB_WP_FTL_RLC_SOURCE_BLOCK_SELECTED],
                #"WP_FTL_OBM_JUMBO_BLOCK_CLOSED"    : [self.relocationCallBackObj.CB_WP_FTL_OBM_JUMBO_BLOCK_CLOSED],
                #"WP_FTL_RLC_TARGET_BLOCK_FULL"     : [self.relocationCallBackObj.CB_WP_FTL_RLC_TARGET_BLOCK_FULL],
                #"WP_FTL_RLC_SOURCE_BLOCK_RELEASED" : [self.relocationCallBackObj.CB_WP_FTL_RLC_SOURCE_BLOCK_RELEASED],
                #"WP_FTL_RLC_COPY_FMUS"             : [self.relocationCallBackObj.CB_WP_FTL_RLC_COPY_FMUS],
                #"WP_FTL_RLC_CYCLE_TERMINATE"       : [self.relocationCallBackObj.CB_WP_FTL_RLC_CYCLE_TERMINATE],
                #"WP_FTL_RLC_WRITE_JB_VBA"          : [self.relocationCallBackObj.CB_WP_FTL_RLC_WRITE_JB_VBA],
                #"WP_PS_EPWR_ACTIVATE"              : [self.relocationCallBackObj.CB_WP_PS_EPWR_ACTIVATE],
                #"WP_FTL_RLC_GC_TYPE"               : [self.relocationCallBackObj.CB_WP_FTL_RLC_GC_TYPE]
            #}
        
        #self.WaypointRegObj.RegisterWP(self.wayPointDict)
        
        #one sector is equal to 512bytes, so 64 sectors equal to 32KB
        startLba = self.startLba = Constants.START_LBA
        endLba = self.endLba = self.globalVarsObj.maxLba
        self.transferLen = self.globalVarsObj.randomObj.choice(RelocationThresholds.RLC_RANDOM_TRANSFER_LENGTH_LIST)

        #GC Threhold diag initialization variables
        self.slcBalanceGc = None
        self.slcUrgentGc = None
        self.tlcBalanceGc = None
        self.tlcUrgentGc = None
        self.tlcJbIdAndVfcCountDict = OrderedDict()
    
        self.originalValueOfSlcFreeBlockCountWithDiag = None
        self.originalValueOfSlcFreeBlockCountWithDiag = None
        self.originalValueOfSlcFreeBlockCountWithDiag = None
        self.originalValueOfSlcFreeBlockCountWithDiag = None
    
        self.originalValueOfSlcFreeBlockCountWithoutDiag = None
        self.originalValueOfTlcFreeBlockCountWithoutDiag = None
        self.originalValueOfSlcFreeBlockCountWithDiag = None
        self.originalValueOfTlcFreeBlockCountWithDiag = None
    
        self.originalValueOfSlcBalanceGcTriggerBlockCountWithDiag = None
        self.originalValueOfSlcUrgentGcTriggerBlockCountWithDiag = None
        self.originalValueOfTlcBalanceGcTriggerBlockCountWithDiag = None
        self.originalValueOfTlcUrgentGcTriggerBlockCountWithDiag = None
        self.onceOriginalDiagCallFlag = False
        
        self.efInjectedMetablockAndVbaMappingDict = OrderedDict()
        self.efInjectedCount = None
        self.hostEfInjectedCount = 0


    def initRlcWP(self):
        try:
            #Way point registration
            if self.globalVarsObj.vtfContainer.isModel is True:
                #Way point object and Attribute initialization
                self.WaypointRegObj = WaypointReg.WaypointReg(self.livetObj,
                                                                              self.logger,
                                                                              self.globalVarsObj)
                self.WaypointRegObj.printArguments = True
                self.relocationCallBackObj = RelocationCallBack.RelocationCallBack()
                self.wayPointDict = {
                        'WP_HOST_READ_COMPLETE'            : [self.relocationCallBackObj.CB_WP_HOST_READ_COMPLETE],
                        'WP_HOST_WRITE_COMPLETE'           : [self.relocationCallBackObj.CB_WP_HOST_WRITE_COMPLETE],
                        'WP_FTL_HWD_WRITE_JB_VBA'          : [self.relocationCallBackObj.CB_WP_FTL_HWD_WRITE_JB_VBA],
                        'WP_FTL_BML_JUMBOBLOCK_ALLOCATED'  : [self.relocationCallBackObj.CB_WP_FTL_BML_JUMBOBLOCK_ALLOCATED],
                        #"WP_FTL_RLC_RLC_START"             : [self.relocationCallBackObj.CB_WP_FTL_RLC_RLC_START],
                        "WP_FTL_RLC_RLC_COMPLETE"          : [self.relocationCallBackObj.CB_WP_FTL_RLC_RLC_COMPLETE],
                        "WP_FTL_OBM_JUMBO_BLOCK_ALLOC"     : [self.relocationCallBackObj.CB_WP_FTL_OBM_JUMBO_BLOCK_ALLOC],
                        "WP_FTL_RLC_SOURCE_BLOCK_SELECTED" : [self.relocationCallBackObj.CB_WP_FTL_RLC_SOURCE_BLOCK_SELECTED],
                        "WP_FTL_OBM_JUMBO_BLOCK_CLOSED"    : [self.relocationCallBackObj.CB_WP_FTL_OBM_JUMBO_BLOCK_CLOSED],
                        "WP_FTL_RLC_TARGET_BLOCK_FULL"     : [self.relocationCallBackObj.CB_WP_FTL_RLC_TARGET_BLOCK_FULL],
                        "WP_FTL_RLC_SOURCE_BLOCK_RELEASED" : [self.relocationCallBackObj.CB_WP_FTL_RLC_SOURCE_BLOCK_RELEASED],
                        "WP_FTL_RLC_COPY_FMUS"             : [self.relocationCallBackObj.CB_WP_FTL_RLC_COPY_FMUS],
                        "WP_FTL_RLC_CYCLE_TERMINATE"       : [self.relocationCallBackObj.CB_WP_FTL_RLC_CYCLE_TERMINATE],
                        "WP_FTL_RLC_WRITE_JB_VBA"          : [self.relocationCallBackObj.CB_WP_FTL_RLC_WRITE_JB_VBA],
                        "WP_PS_EPWR_ACTIVATE"              : [self.relocationCallBackObj.CB_WP_PS_EPWR_ACTIVATE],
                        "WP_FTL_RLC_GC_TYPE"               : [self.relocationCallBackObj.CB_WP_FTL_RLC_GC_TYPE]
                    }

            self.WaypointRegObj.RegisterWP(self.wayPointDict)
        except:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestExecutionName(), "In initRlcWP(), Error Registering RLC WP")
        return

    # @brief   Tear down function for test method
    # @details Does the garbage collection and draw a graph if --drawGraph=True
    # @return  None    
    def FillDictionaryConfigValues(self):
        # we should also set the configurations as desired from the user
        # refer to the .ini file to check what levels can be set by the user
        config = ConfigParser.ConfigParser()
        # All option names are passed through the optionxform() method. Its default implementation converts option names to lower case.
        # str passes through the options unchanged.
        config.optionxform = str
        self.sandiskValidationPathValue = os.getenv("SANDISK_FVT_INSTALL_DIR")
        self.subfolderName = "Tests\\CMDP"
        self.subfolderPath = os.path.join(self.sandiskValidationPathValue, self.subfolderName)
        # this will hold all the read sections and variables inside each section
        userConfigurations = dict()
        configFileName = 'CMDP_Configurables.ini'
        assert os.path.isfile(os.path.join(self.subfolderPath,configFileName)), 'File path %d doesnt exist'%(os.path.join(self.subfolderPath,configFileName))
        try:
            config.read(os.path.join(self.subfolderPath,configFileName))
            sections = config.sections()
            for section in sections:
                userConfigurations[section] = {}
                options = config.options(section)
                for option in options:
                    userConfigurations[section][option]=config.get(section, option)
        except:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestExecutionName(), "Error parsing config file")
        return userConfigurations


    def gcThresholdValueWithoutDiag(self):
        self.logger.Info(self.globalVarsObj.TAG, 'GC Threshold value calculation for SLC and TLC Partiton for both Balanced and Urgent GC before calling MVP threshold diagnostics')

        MvpThresholdresultsDicList = self.sctpUtilsObj.GetFTLThresholds(1)
        #MvpThresholdresultsDicList = [MvpThresholdSlcresultsDic, MvpThresholdTlcresultsDic]
        self.originalValueOfSlcFreeBlockCountWithoutDiag = MvpThresholdresultsDicList[0].get('SlcfreeBlocks')
        self.originalValueOfTlcFreeBlockCountWithoutDiag = MvpThresholdresultsDicList[1].get('TlcfreeBlocks')

        self.originalValueOfSlcBalanceGcTriggerBlockCountWithoutDiag = MvpThresholdresultsDicList[0].get('SlcfreeBlocksToStartBalanceGc')       
        self.originalValueOfSlcUrgentGcTriggerBlockCountWithoutDiag = MvpThresholdresultsDicList[0].get('SlcfreeBlocksToStartUrgentGc')        

        self.originalValueOfTlcBalanceGcTriggerBlockCountWithoutDiag = MvpThresholdresultsDicList[1].get('TlcfreeBlocksToStartBalanceGc')        
        self.originalValueOfTlcUrgentGcTriggerBlockCountWithoutDiag = MvpThresholdresultsDicList[1].get('TlcfreeBlocksToStartUrgentGc')

        self.slcBalanceGc = self.originalValueOfSlcFreeBlockCountWithoutDiag - self.originalValueOfSlcBalanceGcTriggerBlockCountWithoutDiag
        self.slcUrgentGc = self.originalValueOfSlcFreeBlockCountWithoutDiag - self.originalValueOfSlcUrgentGcTriggerBlockCountWithoutDiag
        self.tlcBalanceGc = self.originalValueOfTlcFreeBlockCountWithoutDiag - self.originalValueOfTlcBalanceGcTriggerBlockCountWithoutDiag
        self.tlcUrgentGc = self.originalValueOfTlcFreeBlockCountWithoutDiag - self.originalValueOfTlcUrgentGcTriggerBlockCountWithoutDiag

        self.logger.Info(self.globalVarsObj.TAG, 'SLC Balanced GC triggers if the number of allocated SLC blocks count reached to %s SLC blocks' % str(abs(self.slcBalanceGc)))
        self.logger.Info(self.globalVarsObj.TAG, 'SLC Urgent GC triggers if the number of allocated SLC blocks count reached to %s SLC blocks' % str(abs(self.slcUrgentGc)))
        self.logger.Info(self.globalVarsObj.TAG, 'TLC Balanced GC triggers if the number of allocated TLC blocks count reached to %s TLC blocks' % str(abs(self.tlcBalanceGc)))
        self.logger.Info(self.globalVarsObj.TAG, 'TLC Urgent GC triggers if the number of allocated TLC blocks count reached to %s TLC blocks' % str(abs(self.tlcUrgentGc)))       
        return
    
    
    def gcThresholdValueWithDiag(self):
        self.logger.Info(self.globalVarsObj.TAG, 'GC Threshold value calculation for SLC and TLC Partiton for both Balanced and Urgent GC After calling MVP threshold diagnostics')
    
        MvpThresholdresultsDicList = self.sctpUtilsObj.GetFTLThresholds(1)
        #MvpThresholdresultsDicList = [MvpThresholdSlcresultsDic, MvpThresholdTlcresultsDic]
    
        self.originalValueOfSlcFreeBlockCountWithDiag = MvpThresholdresultsDicList[0].get('SlcfreeBlocks')
        self.originalValueOfTlcFreeBlockCountWithDiag = MvpThresholdresultsDicList[1].get('TlcfreeBlocks')
    
        self.originalValueOfSlcBalanceGcTriggerBlockCountWithDiag = MvpThresholdresultsDicList[0].get('SlcfreeBlocksToStartBalanceGc')        
        self.originalValueOfSlcUrgentGcTriggerBlockCountWithDiag = MvpThresholdresultsDicList[0].get('SlcfreeBlocksToStartUrgentGc')        
        self.originalValueOfTlcBalanceGcTriggerBlockCountWithDiag = MvpThresholdresultsDicList[1].get('TlcfreeBlocksToStartBalanceGc')        
        self.originalValueOfTlcUrgentGcTriggerBlockCountWithDiag = MvpThresholdresultsDicList[1].get('TlcfreeBlocksToStartUrgentGc')
    
        self.slcBalanceGc = self.originalValueOfSlcFreeBlockCountWithDiag - self.originalValueOfSlcBalanceGcTriggerBlockCountWithDiag
        self.slcUrgentGc = self.originalValueOfSlcFreeBlockCountWithDiag - self.originalValueOfSlcUrgentGcTriggerBlockCountWithDiag
        self.tlcBalanceGc = self.originalValueOfTlcFreeBlockCountWithDiag - self.originalValueOfTlcBalanceGcTriggerBlockCountWithDiag
        self.tlcUrgentGc = self.originalValueOfTlcFreeBlockCountWithDiag - self.originalValueOfTlcUrgentGcTriggerBlockCountWithDiag
    
        self.logger.Info(self.globalVarsObj.TAG, 'Expectation: SLC Balanced GC triggers if the number of allocated SLC blocks count reaches to %s SLC blocks' % str(abs(self.slcBalanceGc)))
        self.logger.Info(self.globalVarsObj.TAG, 'Expectation: SLC Urgent GC triggers if the number of allocated SLC blocks count reaches to %s SLC blocks' % str(abs(self.slcUrgentGc)))
        self.logger.Info(self.globalVarsObj.TAG, 'Expectation: TLC Balanced GC triggers if the number of allocated TLC blocks count reaches to %s TLC blocks' % str(abs(self.tlcBalanceGc)))
        self.logger.Info(self.globalVarsObj.TAG, 'Expectation: TLC Urgent GC triggers if the number of allocated TLC blocks count reaches to %s TLC blocks' % str(abs(self.tlcUrgentGc)))
        return


    def relocationStatisticsDictBeforeRelocation(self, disableTheDiagnosticFlag=False):
        self.disableTheDiagnosticFlag = disableTheDiagnosticFlag
        if self.disableTheDiagnosticFlag is False: #diagnostic is active
            self.logger.Info(self.globalVarsObj.TAG, "relocationStatisticsDictBeforeRelocation(): Set MVP threshold Diagnotic is Enabled and used, Hence Relocation threshold setted successfully")             
            if not (self.slcThrsCfgValue == 0 or self.tlcThrsCfgValue == 0): #Handle thresholds and adjust device range when test starts
                self.utilsObj.ThresholdHandler("start", self.slcThrsCfgValue, self.tlcThrsCfgValue)
        elif self.disableTheDiagnosticFlag is True:  #diagnostic is inactive, go through normal flow of operation
            self.logger.Info(self.globalVarsObj.TAG, "relocationStatisticsDictBeforeRelocation(): Set MVP threshold Diagnotics is disabled and not used, Hence Relocation triggers only after the normal amount of SLC and TLC block exhaustion") 

        self.relocationStatisticsDictBeforeGcValue = self.sctpUtilsObj.GetRelocationStatistics()   #Get Relocation statistics
        self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)
        self.logger.Info(self.globalVarsObj.TAG, "|     Relocation Statistics Before test     |")
        self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)
        for key,val in self.relocationStatisticsDictBeforeGcValue.iteritems():
            self.logger.Info(self.globalVarsObj.TAG, "| {:<35} | {:<3} |".format(key, val))
            self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)
        if self.disableTheDiagnosticFlag is False:
            self.gcThresholdValueWithDiag()
        else:
            self.gcThresholdValueWithoutDiag()
        return
        

    def relocationStatisticsDictAfterRelocation(self, disableTheDiagnosticFlag=False):
        self.disableTheDiagnosticFlag = disableTheDiagnosticFlag
        self.relocationStatisticsDictAfterGcValue = self.sctpUtilsObj.GetRelocationStatistics()  #Get Relocation statistics
        self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)
        self.logger.Info(self.globalVarsObj.TAG, "|      Relocation Statistics after test     |")
        self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)       
        for key,val in self.relocationStatisticsDictAfterGcValue.iteritems():
            self.logger.Info(self.globalVarsObj.TAG, "| {:<35} | {:<3} |".format(key, val))
            self.logger.Info(self.globalVarsObj.TAG, "-" * g_string_print_length)  
        
        if self.disableTheDiagnosticFlag is False: #diagnostic is active
            self.logger.Info(self.globalVarsObj.TAG, "relocationStatisticsDictAfterRelocation(): Set MVP threshold Diagnotic is Enabled and used, Hence Relocation threshold resetting is required. SLC and TLC MVP threshold are resetted to 0")                 
            self.utilsObj.ThresholdHandler("end", slcThrs=None, tlcThrs=None)      #Handle thresholds and adjust device range when test ends  
        elif self.disableTheDiagnosticFlag is True: #diagnostic is inactive, go through normal flow of operation
            self.logger.Info(self.globalVarsObj.TAG, "relocationStatisticsDictAfterRelocation(): Set MVP threshold Diagnotics is disabled and not used, Hence Relocation threshold resetting is not required")     
        return
    
    
    #It triggers SLC Dynamic Relocation - It is working now
    def triggerGc(self, startLba, endLba):
        try:
            retStatus = False
            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER SLC BALANCED DYNAMIC GC LOGIC STARTED")
            #global startLba, endLba
            diasbleThediagThresholdConditionCheck = None
            self.relocationCallBackObj.destinationWriteJbVbaFlag = False
            self.relocationCallBackObj.relocationStartFlag = False

            if self.disableTheDiagnosticFlag is True:
                self.logger.Info(self.globalVarsObj.TAG, "triggerGc(): Set MVP threshold Diagnotics is disabled and not used, Hence Relocation triggers only after the normal amount of SLC and TLC block exhaustion")
                diasbleThediagThresholdConditionCheck = True #BY DEFAULT, DIAGNOSTIC RELOCATION CHECK IS DISABLED
            else:
                self.logger.Info(self.globalVarsObj.TAG, "triggerGc(): Set MVP threshold Diagnotics is Enabled and used, Hence Relocation triggers as per the set MVP threshold values for both SLC and TLC")
                diasbleThediagThresholdConditionCheck = False

            for lba in range(startLba, endLba, self.transferLen):
                if (startLba - (2 * self.transferLen)) >= (self.globalVarsObj.maxLba - self.transferLen):
                    self.logger.Info(self.globalVarsObj.TAG, "As current LBA -> %s | reached maxLba -> %s | restarting the startLba to 0" % (str(startLba), str(self.globalVarsObj.maxLba)))
                    startLba = 0
                    self.logger.Info(self.globalVarsObj.TAG, "Restarting the startLba is {}".format(startLba))
                self.ccmObj.Write(startLba, self.transferLen)
                self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))
                self.lbaWrittenDict[startLba] = self.transferLen
                startLba = startLba + self.transferLen

                if self.relocationCallBackObj.slcDynamicRelocationType is True and \
                   self.relocationCallBackObj.relocationStartFlag is True and self.relocationCallBackObj.destinationWriteJbVbaFlag is True:                    
                    # if number of jumbo blocks allocated met threshold; break the loop to check RLC status
                    if (self.relocationCallBackObj.Number_of_SLC_JB_allocated) >= int(self.slcBalanceGc):
                        self.logger.Info(self.globalVarsObj.TAG, "PASS: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                        self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                        self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed)) 
                        self.sctpUtilsObj.GetFTLThresholds(1)
                        retStatus = True
                        break                        
                        #if self.relocationCallBackObj.slcDynamicRelocationType is True:
                            #self.sctpUtilsObj.GetFTLThresholds(1)
                            #retStatus = True
                            ##return True, startLba, endLba
                            #break
                    else:
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                        self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed))                                 
                        break
                        #raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'SLC Balanced GC did not trigger, even after reaching the threshold')


                #if self.relocationCallBackObj.relocationStartFlag is True and self.relocationCallBackObj.destinationWriteJbVbaFlag is True:
                    #if diasbleThediagThresholdConditionCheck is True:                    
                        #if (self.relocationCallBackObj.Number_of_SLC_JB_allocated) >= int(self.slcBalanceGc): 
                            #self.logger.Info(self.globalVarsObj.TAG, "PASS: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                            #self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                            #self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed)) 
                            #if self.relocationCallBackObj.slcDynamicRelocationType is True:
                                ##return True, startLba, endLba
                                #retStatus = True
                                #break
                        #else:
                            #self.logger.Info(self.globalVarsObj.TAG, "FAIL: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                            #self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                            #self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed))                                 
                            #break
                                ##raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'Relocation did not trigger, even after reaching the threshold')
                    #else:                        
                        ## if number of jumbo blocks allocated met threshold; break the loop to check RLC status
                        #if (self.relocationCallBackObj.Number_of_SLC_JB_allocated) >= int(self.slcBalanceGc):
                            #self.logger.Info(self.globalVarsObj.TAG, "PASS: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                            #self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                            #self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed)) 
                            #if self.relocationCallBackObj.slcDynamicRelocationType is True:
                                #self.sctpUtilsObj.GetFTLThresholds(1)
                                #retStatus = True
                                ##return True, startLba, endLba
                                #break
                        #else:
                            #self.logger.Info(self.globalVarsObj.TAG, "FAIL: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                            #self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                            #self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed))                                 
                            #break
                            ##raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'SLC Balanced GC did not trigger, even after reaching the threshold')

            if retStatus is True:
                while self.relocationCallBackObj.destinationWriteJbVbaFlag is False:
                    self.ccmObj.Write(startLba, self.transferLen)
                    self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))                    
                    self.lbaWrittenDict[startLba] = self.transferLen
                    startLba = startLba + self.transferLen
            else:
                self.logger.Info(self.globalVarsObj.TAG, "FAIL: TRIGGER SLC BALANCED DYNAMIC GC LOGIC FAILED, In triggerGc(), the retStatus -> %s" % str(retStatus))

            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER SLC BALANCED DYNAMIC GC LOGIC COMPLETED") 

        except Exception as e_obj:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'EXCEPTION: In triggerGc() - %s' % str(e_obj))
        return retStatus, startLba, endLba


    #It triggers TLC Dynamic Relocation (TLC to TLC relocation takes longer time) - (without threshold relaxation)
    def triggerTlcGc(self, startLba, endLba):
        try:
            tlcBalancedGcRelaxedValue = None
            retStatus = False
            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER TLC BALANCED DYNAMIC GC LOGIC STARTED")
            #global startLba, endLba
            tlcVfcSrcSelectionCheck = False
            onceFlag = False
            tlcBalancedGcRelaxedValue = 3 # as per the FW discussion
            self.relocationCallBackObj.destinationWriteJbVbaFlag = False
            self.relocationCallBackObj.relocationStartFlag = False
            
            self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            self.logger.Info(self.globalVarsObj.TAG, "TLC BALANCED GC THRESHOLD BEFORE RELAXING BY THREE BLOCKS - %s" % str(self.tlcBalanceGc))
            self.tlcBalanceGc = self.tlcBalanceGc + tlcBalancedGcRelaxedValue
            self.logger.Info(self.globalVarsObj.TAG, "TLC BALANCED GC THRESHOLD AFTER RELAXING BY THREE BLOCKS - %s" % str(self.tlcBalanceGc))
            self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")

            for lba in range(startLba, endLba, self.transferLen):
                if tlcVfcSrcSelectionCheck is True:
                    break
                if (startLba - (2 * self.transferLen)) >= (self.globalVarsObj.maxLba - self.transferLen):
                    self.logger.Info(self.globalVarsObj.TAG, "As current LBA -> %s | reached maxLba -> %s | restarting the startLba to 0" % (str(startLba), str(self.globalVarsObj.maxLba)))
                    startLba = 0
                    self.logger.Info(self.globalVarsObj.TAG, "Restarting the startLba is {}".format(startLba))
                self.ccmObj.Write(startLba, self.transferLen)
                self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))
                self.lbaWrittenDict[startLba] = self.transferLen
                startLba = startLba + self.transferLen
        
                if self.relocationCallBackObj.relocationStartFlag is True:
                    # add one more condition self.relocationCallBackObj.Number_of_TLC_JB_allocated) >= int(self.tlcBalanceGc) + 1 if below is not working
                    #if (self.relocationCallBackObj.Number_of_TLC_JB_allocated) >= int(self.tlcBalanceGc):
                    if (self.relocationCallBackObj.Number_of_TLC_JB_closed) >= int(self.tlcBalanceGc) + 1 or self.relocationCallBackObj.tlcDynamicRelocationType is True:
                        if onceFlag is False:
                            onceFlag = True
                            self.sctpUtilsObj.GetFTLThresholds(1)
                        # if number of jumbo blocks allocated met threshold; break the loop to check RLC status
                        self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#%")
                        self.logger.Info(self.globalVarsObj.TAG, "TLC BALANCED GC THRESHOLD CHECK TRIGGERS WITH RELAXING BY THREE BLOCKS AND AFTER CLOSURE OF BLOCK -%s" % str(self.tlcBalanceGc))
                        self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#%")                        
                        self.logger.Info(self.globalVarsObj.TAG,"TLC MVP threshold to trigger Relocation is {}".format(int(self.tlcBalanceGc)))
                        self.logger.Info(self.globalVarsObj.TAG,"{} TLC blocks are allocated relocation is supposed to start".format(self.relocationCallBackObj.Number_of_TLC_JB_allocated))
                        self.logger.Info(self.globalVarsObj.TAG,"{} TLC blocks are closed relocation is supposed to start".format(self.relocationCallBackObj.Number_of_TLC_JB_closed))                       
                        if self.relocationCallBackObj.tlcDynamicRelocationType is True:
                            self.sctpUtilsObj.GetFTLThresholds(1)
                            while tlcVfcSrcSelectionCheck is False:
                                self.ccmObj.Write(startLba, self.transferLen)
                                self.lbaWrittenDict[startLba] = self.transferLen
                                startLba = startLba + self.transferLen                            
                                if self.relocationCallBackObj.relocationSourceSelectedPartitionTypeFromWp == 1: # for TLC to TLC GC
                                    #self.tlcVfcSourceSelectionCheck()
                                    tlcVfcSrcSelectionCheck = True
                                    # TODO: need to check this threshold part of TLC to TLC balanced GC threshold relaxation
                                    self.logger.Info(self.globalVarsObj.TAG, "PASS: TLC Balanced GC trigger point is relaxed from set trigger TLC balanced GC value %s" % str(abs(self.tlcThrsCfgValue)))  
                                    self.logger.Info(self.globalVarsObj.TAG, "PASS: Number of TLC blocks closed %s" % str(len(self.relocationCallBackObj.tlcClosedBlockList)))
                                    self.logger.Info(self.globalVarsObj.TAG, "PASS: TLC blocks GC threshold %s" % str(int(self.tlcBalanceGc)))
                                    self.sctpUtilsObj.GetFTLThresholds(1)
                                    retStatus = True
                                    break
                                #if len(self.relocationCallBackObj.tlcClosedBlockList) > int(self.tlcBalanceGc) + 1: # observed it triggers after writing 17 blocks sequentially in NVme mode and SD after closure of 15b blocks
                                    #self.logger.Info(self.globalVarsObj.TAG, "FAIL: Number of TLC blocks closed %s" % str(len(self.relocationCallBackObj.tlcClosedBlockList)))
                                    #self.logger.Info(self.globalVarsObj.TAG, "FAIL: TLC blocks GC threshold %s" % str(int(self.tlcBalanceGc)))
                                    #self.sctpUtilsObj.GetFTLThresholds(1)
                                    #break
                        #else:
                            #raise ValidationError.TestFailError("triggerTlcGc()", "FAIL: TLC BALANCED GC TRIGGERED is not triggered on the desired threshold value")

            if retStatus is True:
                self.relocationCallBackObj.destinationWriteJbVbaFlag = False
                while self.relocationCallBackObj.destinationWriteJbVbaFlag is False:
                    self.ccmObj.Write(startLba, self.transferLen) 
                    self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))                    
                    self.lbaWrittenDict[startLba] = self.transferLen
                    startLba = startLba + self.transferLen

            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER TLC BALANCED DYNAMIC GC LOGIC COMPLETED") 
        
        except Exception as e_obj:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'EXCEPTION: In triggerTlcGc() - ' + str(e_obj))
        return retStatus, startLba, endLba


    #It triggers SLC Dynamic Relocation - It is working now
    def triggerNvmeGc(self, startLba, endLba):
        try:
            retStatus = False
            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER NVME SLC BALANCED DYNAMIC GC LOGIC STARTED")
            #global startLba, endLba
            diasbleThediagThresholdConditionCheck = None
            self.relocationCallBackObj.destinationWriteJbVbaFlag = False
            self.relocationCallBackObj.relocationStartFlag = False

            if self.disableTheDiagnosticFlag is True:
                self.logger.Info(self.globalVarsObj.TAG, "triggerGc(): Set MVP threshold Diagnotics is disabled and not used, Hence Relocation triggers only after the normal amount of SLC and TLC block exhaustion")
                diasbleThediagThresholdConditionCheck = True #BY DEFAULT, DIAGNOSTIC RELOCATION CHECK IS DISABLED
            else:
                self.logger.Info(self.globalVarsObj.TAG, "triggerGc(): Set MVP threshold Diagnotics is Enabled and used, Hence Relocation triggers as per the set MVP threshold values for both SLC and TLC")
                diasbleThediagThresholdConditionCheck = False

            for lba in range(startLba, endLba, self.transferLen):
                self.ccmObj.Write(startLba, self.transferLen) 
                self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))                
                self.lbaWrittenDict[startLba] = self.transferLen
                startLba = startLba + self.transferLen
                #self.ccmObj.DoFlushCache()
                #self.globalVarsObj.vtfContainer.cmd_mgr.GetThreadPoolMgr().WaitForThreadCompletion() #ZRPG-2762

                if self.relocationCallBackObj.relocationStartFlag is True:
                    if diasbleThediagThresholdConditionCheck is True:                    
                        if (self.relocationCallBackObj.Number_of_SLC_JB_allocated) >= int(self.slcBalanceGc) \
                           and self.relocationCallBackObj.destinationWriteJbVbaFlag is True: 
                            self.logger.Info(self.globalVarsObj.TAG, "PASS: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                            self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                            self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed)) 
                            if self.relocationCallBackObj.slcDynamicRelocationType is True:
                                #return True, startLba, endLba
                                retStatus = True
                                break
                            else:
                                self.logger.Info(self.globalVarsObj.TAG, "FAIL: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                                self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                                self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed))                                 
                                break
                                #raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'Relocation did not trigger, even after reaching the threshold')
                    else:                        
                        # if number of jumbo blocks allocated met threshold; break the loop to check RLC status
                        if (self.relocationCallBackObj.Number_of_SLC_JB_allocated) >= int(self.slcBalanceGc) and\
                           self.relocationCallBackObj.destinationWriteJbVbaFlag is True:
                            self.logger.Info(self.globalVarsObj.TAG, "PASS: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                            self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                            self.logger.Info(self.globalVarsObj.TAG, "PASS: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed)) 
                            if self.relocationCallBackObj.slcDynamicRelocationType is True:
                                self.sctpUtilsObj.GetFTLThresholds(1)
                                retStatus = True
                                #return True, startLba, endLba
                                break
                            else:
                                self.logger.Info(self.globalVarsObj.TAG, "FAIL: triggerNvmeGc(), Did not trigger SLC to TLC NVME mode GC")
                                self.logger.Info(self.globalVarsObj.TAG, "FAIL: SLC MVP threshold to trigger Relocation is {}".format(self.slcBalanceGc))
                                self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated)) 
                                self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed))                                 
                                break
                                #raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'SLC Balanced GC did not trigger, even after reaching the threshold')

            if retStatus is True:
                while self.relocationCallBackObj.destinationWriteJbVbaFlag is False:
                    self.ccmObj.Write(startLba, self.transferLen) 
                    self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))                    
                    self.lbaWrittenDict[startLba] = self.transferLen
                    startLba = startLba + self.transferLen 

            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER NVME SLC BALANCED DYNAMIC GC LOGIC COMPLETED") 

        except Exception as e_obj:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'EXCEPTION: In triggerNvmeGc() - %s' % str(e_obj))
        return retStatus, startLba, endLba



    #It triggers TLC Dynamic Relocation (TLC to TLC relocation takes longer time) - (without threshold relaxation)
    def triggerTlcNvmeGc(self, startLba, endLba):
        try:
            tlcBalancedGcRelaxedValue = None
            retStatus = False
            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER NVME TLC BALANCED DYNAMIC GC LOGIC STARTED")
            #global startLba, endLba
            tlcVfcSrcSelectionCheck = False
            onceFlag = False
            tlcBalancedGcRelaxedValue = 3 # as per the FW discussion
            self.relocationCallBackObj.destinationWriteJbVbaFlag = False
            self.relocationCallBackObj.relocationStartFlag = False

            while not ((startLba % self.oneTlcJwlInFmus) == 0):
                startLba = startLba + (startLba % self.oneTlcJwlInFmus)
                if startLba >= self.globalVarsObj.maxLba:
                    startLba = 0

            self.transferLen = self.oneTlcJwlInFmus

            self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            self.logger.Info(self.globalVarsObj.TAG, "TLC BALANCED GC THRESHOLD BEFORE RELAXING BY THREE BLOCKS - %s" % str(self.tlcBalanceGc))
            self.tlcBalanceGc = self.tlcBalanceGc + tlcBalancedGcRelaxedValue
            self.logger.Info(self.globalVarsObj.TAG, "TLC BALANCED GC THRESHOLD AFTER RELAXING BY THREE BLOCKS - %s" % str(self.tlcBalanceGc))
            self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")

            for lba in range(startLba, endLba, self.transferLen):
                if tlcVfcSrcSelectionCheck is True:
                    break

                self.ccmObj.Write(startLba, self.transferLen) 
                self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))                
                self.lbaWrittenDict[startLba] = self.transferLen
                startLba = startLba + self.transferLen
        
                if self.relocationCallBackObj.relocationStartFlag is True:
                    # add one more condition self.relocationCallBackObj.Number_of_TLC_JB_allocated) >= int(self.tlcBalanceGc) + 1 if below is not working
                    #if (self.relocationCallBackObj.Number_of_TLC_JB_allocated) >= int(self.tlcBalanceGc):
                    if (self.relocationCallBackObj.Number_of_TLC_JB_closed) >= int(self.tlcBalanceGc) + 1 or self.relocationCallBackObj.tlcDynamicRelocationType is True:
                        if onceFlag is False:
                            onceFlag = True
                            self.sctpUtilsObj.GetFTLThresholds(1)
                        # if number of jumbo blocks allocated met threshold; break the loop to check RLC status
                        self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#%")
                        self.logger.Info(self.globalVarsObj.TAG, "TLC BALANCED GC THRESHOLD CHECK TRIGGERS WITH RELAXING BY THREE BLOCKS AND AFTER CLOSURE OF BLOCK -%s" % str(self.tlcBalanceGc))
                        self.logger.Info(self.globalVarsObj.TAG, "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#%")                        
                        self.logger.Info(self.globalVarsObj.TAG,"TLC MVP threshold to trigger Relocation is {}".format(int(self.tlcBalanceGc)))
                        self.logger.Info(self.globalVarsObj.TAG,"{} TLC blocks are allocated relocation is supposed to start".format(self.relocationCallBackObj.Number_of_TLC_JB_allocated))
                        self.logger.Info(self.globalVarsObj.TAG,"{} TLC blocks are closed relocation is supposed to start".format(self.relocationCallBackObj.Number_of_TLC_JB_closed))                       
                        if self.relocationCallBackObj.tlcDynamicRelocationType is True:
                            self.sctpUtilsObj.GetFTLThresholds(1)
                            while tlcVfcSrcSelectionCheck is False:
                                self.ccmObj.Write(startLba, self.transferLen)
                                self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))                                
                                self.lbaWrittenDict[startLba] = self.transferLen
                                startLba = startLba + self.transferLen                            
                                if self.relocationCallBackObj.relocationSourceSelectedPartitionTypeFromWp == 1: # for TLC to TLC GC
                                    #self.tlcVfcSourceSelectionCheck()
                                    tlcVfcSrcSelectionCheck = True
                                    # TODO: need to check this threshold part of TLC to TLC balanced GC threshold relaxation
                                    self.logger.Info(self.globalVarsObj.TAG, "PASS: TLC Balanced GC trigger point is relaxed from set trigger TLC balanced GC value %s" % str(abs(self.tlcThrsCfgValue)))  
                                    self.logger.Info(self.globalVarsObj.TAG, "PASS: Number of TLC blocks closed %s" % str(len(self.relocationCallBackObj.tlcClosedBlockList)))
                                    self.logger.Info(self.globalVarsObj.TAG, "PASS: TLC blocks GC threshold %s" % str(int(self.tlcBalanceGc)))
                                    self.sctpUtilsObj.GetFTLThresholds(1)
                                    retStatus = True
                                    break
                                if len(self.relocationCallBackObj.tlcClosedBlockList) > 20: # observed it triggers after writing 17 blocks sequentially in NVme mode and SD after closure of 15b blocks
                                    self.logger.Info(self.globalVarsObj.TAG, "FAIL: Number of TLC blocks closed %s" % str(len(self.relocationCallBackObj.tlcClosedBlockList)))
                                    self.logger.Info(self.globalVarsObj.TAG, "FAIL: TLC blocks GC threshold %s" % str(int(self.tlcBalanceGc)))                             
                                    self.sctpUtilsObj.GetFTLThresholds(1)
                                    break
                        #else:
                            #raise ValidationError.TestFailError("triggerTlcNvmeGc()", "FAIL: TLC BALANCED GC TRIGGERED is not triggered on the desired threshold value")

            if retStatus is True:
                while self.relocationCallBackObj.destinationWriteJbVbaFlag is False:
                    self.ccmObj.Write(startLba, self.transferLen)
                    self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, self.transferLen))                    
                    self.lbaWrittenDict[startLba] = self.transferLen
                    startLba = startLba + self.transferLen

            self.logger.Info(self.globalVarsObj.TAG, "TRIGGER NVME TLC BALANCED DYNAMIC GC LOGIC COMPLETED") 
        
        except Exception as e_obj:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'EXCEPTION: In triggerTlcNvmeGc() - ' + str(e_obj))
        return retStatus, startLba, endLba
    
    
    def performDifferentPercentageOfValidSectorsInHostSlcBlock(self, numberOfValidSectorsInOneSlcBlock):
        try:
            retStatus = False
            global startLba, endLba
            count = 0
            #self.percentageOfValidSectorsRequiredInOneSlcBlockValue = numberOfValidSectorsInOneSlcBlock
            noOfValidSectorRequiredInSlcBlock = numberOfValidSectorsInOneSlcBlock #number of sector valid in one SLC block
            self.logger.Info(self.globalVarsObj.TAG, "noOfValidSectorRequiredInSlcBlock valid number of sectors in one SLC block - {}".format(int(noOfValidSectorRequiredInSlcBlock)))

            self.transferLen = 1024
            self.logger.Info(self.globalVarsObj.TAG, "Transfer Length {}".format(int(self.transferLen)))


            # Write host data on the same LBA till gc triggers and it keep track of the LBA written     
            while self.relocationCallBackObj.relocationStartFlag is False:
                sectorsWritten = 0
                txlen = 512
                
                if len(self.relocationCallBackObj.slcClosedBlockJbIdList) > self.slcBalanceGc + 2:
                    self.logger.Info(self.globalVarsObj.TAG, "FAIL: SLC MVP threshold to trigger Relocation is {}".format(abs(self.slcBalanceGc)))
                    self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are allocated relocation so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated))                    
                    self.logger.Info(self.globalVarsObj.TAG, "FAIL: {} SLC blocks are Closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed))                    
                    #raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'FAIL: In performDifferentPercentageOfValidSectorsInHostSlcBlock() - SLC to TLC Dynamic relocation did not triggered in SD mode')
                    break

                while sectorsWritten < self.oneSlcBlockSizeInSectors:
                    if sectorsWritten < (self.oneSlcBlockSizeInSectors - txlen):
                        self.ccmObj.Write(startLba, txlen)
                    if sectorsWritten >= (self.oneSlcBlockSizeInSectors - txlen):
                        txlen = noOfValidSectorRequiredInSlcBlock
                        self.ccmObj.Write(startLba, txlen)
                        self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, txlen))                        
                        if sectorsWritten >= (self.oneSlcBlockSizeInSectors - noOfValidSectorRequiredInSlcBlock):
                            self.ccmObj.Write(startLba, txlen)
                            self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, txlen))                            
                            self.lbaWrittenDict[startLba]=txlen #it keeps track on the same written LBA
                            startLba = startLba + txlen
                    sectorsWritten = sectorsWritten + txlen

                    if self.relocationCallBackObj.relocationStartFlag is True:
                        self.logger.Info(self.globalVarsObj.TAG, "SLC MVP threshold to trigger Relocation is {}".format(abs(self.slcThrsCfgValue)))
                        self.logger.Info(self.globalVarsObj.TAG, "{} SLC blocks are allocated so far".format(self.relocationCallBackObj.Number_of_SLC_JB_allocated))                     
                        self.logger.Info(self.globalVarsObj.TAG, "{} SLC blocks are closed so far".format(self.relocationCallBackObj.Number_of_SLC_JB_closed))                     
                        if self.relocationCallBackObj.slcDynamicRelocationType is True:
                            self.logger.Info(self.globalVarsObj.TAG, "Trigger SLC to TLC Relocation by keeping only certain number of valid sectors in each SLC block COMPLETED") 
                            break

            if self.relocationCallBackObj.destinationWriteJbVbaFlag is True:
                #Get the JB ID and VFC for source jumbo block picked for SLC to TLC Dynamic relocation            
                self.currentPickedSourceBlockForRelocationJbIdFromWP = self.relocationCallBackObj.relocationSourceSelectedJbIdFromWp
                self.currentPickedSourceBlockForRelocationJbVfcFromWP = self.relocationCallBackObj.relocationSourceSelectedSourceVcFromWp

                slcJumboBlockIdAndVfcOutputDict = dict()
                tempSlcJumboBlockInfoResultantDict = dict()
                slcListOfJbId = self.relocationCallBackObj.slcClosedBlockJbIdList #block picked for relocation must be a closed SLC block
                self.logger.Info(self.globalVarsObj.TAG, "Apply GetJumboBlockInfo diag for list of SLC closed Jumbo Block ID - %s" % str(slcListOfJbId))
                if len(slcListOfJbId) > 0:
                    for jbId in slcListOfJbId:
                        #PartitionId = 0 for SLC, 1 for TLC
                        self.logger.Info(self.globalVarsObj.TAG, "Applying GetJumboBlockInfo diag for Jumbo Block ID - %s" % str(jbId))
                        databufffer, tempSlcJumboBlockInfoResultantDict = self.sctpUtilsObj.GetJumboBlockInfo(PartitionId=0, JumboBlockId=jbId)
                        #Get the VFC of a closed SLC JB {blockId : VFC} 
                        slcJumboBlockIdAndVfcOutputDict[jbId] = tempSlcJumboBlockInfoResultantDict['vfc']
                    
                    self.currentPickedSourceBlockJbIdForRelocationVfcCount = slcJumboBlockIdAndVfcOutputDict.get(self.currentPickedSourceBlockForRelocationJbIdFromWP,
                                                                                                                 None)
                    if self.currentPickedSourceBlockJbIdForRelocationVfcCount is None:
                        raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'FAIL: In performDifferentPercentageOfValidSectorsInHostSlcBlock() - Invalid SLC Jumbo block had been picked as source for SLC to TLC Dynamic relocation in SD mode')
                    else:                 
                        self.logger.Info(self.globalVarsObj.TAG, "Source Jumbo Block ID - %s picked for SLC to TLC Dynamic relocation has VFC - %s" 
                                         % (str(self.currentPickedSourceBlockForRelocationJbIdFromWP), 
                                            str(self.currentPickedSourceBlockJbIdForRelocationVfcCount)))
                        retStatus = True

                    ## LRU check for SLC blocks
                    #if self.currentPickedSourceBlockForRelocationJbIdFromWP in self.relocationCallBackObj.slcClosedBlockJbIdList[0]:
                        #self.logger.Info(self.globalVarsObj.TAG, "Source JB ID is picked - %s, JB ID to pick - %s for SLC to TLC Dynamic relocation is LRU of SLC closed block JB list %s" 
                                         #% (str(self.currentPickedSourceBlockForRelocationJbIdFromWP), str(self.relocationCallBackObj.slcClosedBlockJbIdList[0]), str(self.relocationCallBackObj.slcClosedBlockJbIdList)))
                        #retStatus = True
                    #else:
                        #self.logger.Info(self.globalVarsObj.TAG, "Source JB ID is picked - %s, JB ID to pick - %s for SLC to TLC Dynamic relocation are not LRU of SLC closed block JB list %s" 
                                         #% (str(self.currentPickedSourceBlockForRelocationJbIdFromWP), str(self.relocationCallBackObj.slcClosedBlockJbIdList[0]), str(self.relocationCallBackObj.slcClosedBlockJbIdList)))
                        #raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(),
                                                            #'FAIL: In sourceSelectionCheck() - SLC Jumbo block picked for relocation is not the one LRU used block from SLC Closed block list')
                    
        except Exception as e_obj:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'EXCEPTION: In performDifferentPercentageOfValidSectorsInHostSlcBlock() - ' + str(e_obj))
        return retStatus, startLba, endLba


    def tlcVfcSourceSelectionCheck(self):
        try:
            currentPickedSourceBlockForRelocationJbIdFromWP = self.relocationCallBackObj.relocationSourceSelectedJbIdFromWp
            currentPickedSourceBlockForRelocationJbVfcFromWP = self.relocationCallBackObj.relocationSourceSelectedSourceVcFromWp
            tlcListOfJbId = []
            tlcJumboBlockIdAndVfcOutputDict = dict()
            tempTlcJumboBlockInfoResultantDict = dict()
            tlcListOfJbId = self.relocationCallBackObj.tlcClosedBlockJbIdList #block picked for relocation must be a closed SLC block
            self.logger.Info(self.globalVarsObj.TAG, "Apply GetJumboBlockInfo diag for list of TLC closed Jumbo Block ID - %s" % str(tlcListOfJbId))
            if len(tlcListOfJbId) > 0:
                for jbId in tlcListOfJbId:
                    #PartitionId = 0 for SLC, 1 for TLC
                    self.logger.Info(self.globalVarsObj.TAG, "Applying GetJumboBlockInfo diag for Jumbo Block ID - %s" % str(jbId))
                    databufffer, tempTlcJumboBlockInfoResultantDict = self.sctpUtilsObj.GetJumboBlockInfo(PartitionId=1,
                                                                                                          JumboBlockId=jbId)
                    #Get the VFC of a closed SLC JB {blockId : VFC} 
                    tlcJumboBlockIdAndVfcOutputDict[jbId] = tempTlcJumboBlockInfoResultantDict['vfc']
                    self.tlcJbIdAndVfcCountDict[jbId] = tempTlcJumboBlockInfoResultantDict['vfc']
                
                currentPickedSourceBlockJbIdForRelocationVfcCount = tlcJumboBlockIdAndVfcOutputDict.get(currentPickedSourceBlockForRelocationJbIdFromWP, None)

                if currentPickedSourceBlockJbIdForRelocationVfcCount is None:
                    self.logger.Info(self.globalVarsObj.TAG, "TLC Source Jumbo Block ID - %s picked for TLC to TLC Dynamic relocation has VFC - %s" 
                                     % (str(currentPickedSourceBlockForRelocationJbIdFromWP), str(currentPickedSourceBlockJbIdForRelocationVfcCount)))
                else:
                    raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'FAIL: In tlcVfcSourceSelectionCheck() - Invalid TLC Jumbo block had been picked as source for TLC to TLC Dynamic relocation in SD mode')

                if currentPickedSourceBlockJbIdForRelocationVfcCount == currentPickedSourceBlockForRelocationJbVfcFromWP:
                    raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'FAIL: In tlcVfcSourceSelectionCheck() - TLC Jumbo block had been picked as source for TLC to TLC Dynamic relocation in SD mode VFC from WP and Diagnostics is different')
                else:                 
                    self.logger.Info(self.globalVarsObj.TAG, "TLC Source Jumbo Block ID - %s picked for TLC to TLC Dynamic relocation has VFC from diagnostics - %s and VFC from WP %s" 
                                     % (str(currentPickedSourceBlockForRelocationJbIdFromWP), str(currentPickedSourceBlockJbIdForRelocationVfcCount), str(currentPickedSourceBlockForRelocationJbVfcFromWP)))
                

                for dictKey, dictVfcCount in self.tlcJbIdAndVfcCountDict.iteritems():
                    self.logger.Info(self.globalVarsObj.TAG, "TLC Closed Jumbo Block ID - %s and its VFC - %s" % (str(dictKey), str(dictVfcCount)))


                # this is to compare against other Jumbo block to confirm the picked source block has less vfc count
                # If vfc count is same for more than JB block, how the souce block is picked for TLC to TLC Dynamic relocation               
                for key, value in tlcJumboBlockIdAndVfcOutputDict.iteritems():
                    # compare slc closed JB and its vfc with the JB picked for relocation and also compare against all other closed slc JB
                    if int(key) != int(currentPickedSourceBlockForRelocationJbIdFromWP):
                        if value >= currentPickedSourceBlockJbIdForRelocationVfcCount:
                            pass
                        else:
                            self.logger.Info(self.globalVarsObj.TAG, "Invalid TLC Source JB ID is picked - %s, JB ID to pick - %s for TLC to TLC Dynamic relocation and its VFC - %s , closed TLC block Dict - %s" 
                                             % (str(currentPickedSourceBlockForRelocationJbIdFromWP), str(key), str(value), str(tlcJumboBlockIdAndVfcOutputDict)))
                            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'FAIL: In tlcVfcSourceSelectionCheck() - TLC Jumbo block picked for relocation is not the one which has VFC count is less')
                self.logger.Info(self.globalVarsObj.TAG, "TLC Source Jumbo Block ID - %s picked for TLC to TLC Dynamic relocation has VFC - %s is verified successfully against all closed TLC blocks - %s" 
                                     % (str(currentPickedSourceBlockForRelocationJbIdFromWP), str(currentPickedSourceBlockJbIdForRelocationVfcCount), str(tlcJumboBlockIdAndVfcOutputDict)))
            else:
                raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), 'FAIL: In tlcVfcSourceSelectionCheck() - TLC Closed Jumbo Block ID list is empty - %s' % str(self.relocationCallBackObj.tlcClosedBlockJbIdList))
        except:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), "FAIL: In tlcVfcSourceSelectionCheck() - TLC Source selected block is not the one which VFC is less")
        return


    def injectPF(self, lba, vba=None):
        # first convert lba to vba 
        # then convert to Physical address
        # this would contain all information like block, string, wordline etc     
        #then inject PF at desired location using 
        try:
            if vba is None:
                vba = self.sctpUtilsObj.LBA2VBA(lba, 1)
            else:
                vba = vba
            physical_address = self.sctpUtilsObj.TranslateVbaToDeVbaAndPba(vba, 1)
            self.physicalAddressBeforeInjectPf = physical_address.copy()
            phyAddress=[physical_address['die'],
                        physical_address['plane'],
                        physical_address['physicalblock'],
                        physical_address['wordline'],
                        physical_address['stringnumber'], 0, 0]
            errorPersistence = 1 
            paerrorDescription = (self.globalVarsObj.vtfContainer._livet.etProgramError ,errorPersistence, 0, 1, 0, 0)
            package = physical_address['channel'] 
            self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
            self.pfInjectedFlag = True
        except:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(),
                                                "FAIL: In injectPF() - To Inject PF on desired VBA -%s for the given LBA - %s, if LBA is None, then input for the function is VBA" % (str(vba), str(lba)))
        return


    def injectEraeFailure(self, lba, vba=None):
        # first convert lba to vba 
        # then convert to Physical address
        # this would contain all information like block, string, wordline etc     
        #then inject PF at desired location using 
        try:
            if vba is None:
                vba = self.sctpUtilsObj.LBA2VBA(lba, 1)
            else:
                vba = vba
            physical_address = self.sctpUtilsObj.TranslateVbaToDeVbaAndPba(vba, 1)
            self.physicalAddressBeforeInjectPf = physical_address.copy()
            phyAddress=[physical_address['die'],
                        physical_address['plane'],
                        physical_address['physicalblock'],
                        physical_address['wordline'],
                        physical_address['stringnumber'], 0, 0]
            errorPersistence = 1 
            paerrorDescription = (self.globalVarsObj.vtfContainer._livet.etEraseError, errorPersistence, 0, 1, 0, 0)
            package = 0 # physical_address['channel']
            self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
            package = 1 # physical_address['channel']
            self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)                
            self.efInjectedFlag = True
            self.logger.Info(self.globalVarsObj.TAG, "EF injected VBA %s and its pba dict %s" % (str(vba), str(physical_address)))
        except:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), "FAIL: In injectEF() - To Inject EF on desired VBA -%s, then input for the function is VBA" % str(vba))
        return


    def injectWriteAbort(self, lba, vba=None):
        # first convert lba to vba 
        # then convert to Physical address
        # this would contain all information like block, string, wordline etc     
        #then inject PF at desired location using 
        try:
            if vba is None:
                vba = self.sctpUtilsObj.LBA2VBA(lba, 1)
            else:
                vba = vba
            physical_address = self.sctpUtilsObj.TranslateVbaToDeVbaAndPba(vba, 1)
            self.physicalAddressBeforeInjectPf = physical_address.copy()
            phyAddress=[physical_address['die'],
                        physical_address['plane'],
                        physical_address['physicalblock'],
                        physical_address['wordline'],
                        physical_address['stringnumber'], 0, 0]
            errorPersistence = 1 
            paerrorDescription = (self.globalVarsObj.vtfContainer._livet.etProgramAbort ,errorPersistence, 0, 1, 0, 0)
            package = physical_address['channel']
            self.livetObj.GetFlash().InjectError(package, phyAddress, paerrorDescription)
            self.writeAbortInjectedFlag = True
        except:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestName(), "FAIL: In injectWriteAbort() - To Inject WA on desired VBA -%s for the given LBA - %s, if LBA is None, then input for the function is VBA" % (str(vba), str(lba)))
        return


    def readVerificationListData(self, lbaWrittenList):
        status = True
        #perform read operation, once the card in read only mode, all read should pass
        for lba, txlen in lbaWrittenList:
            try:
                self.logger.Info(self.globalVarsObj.TAG, 'READ ON LBA %d of transfer length %d' % (lba, txlen))                
                self.ccmObj.Read(lba, txlen)
            except:
                status = False
                #Fail the case if read failed
                self.logger.Info(self.globalVarsObj.TAG, "FAIL: In readVerificationListData(), Read verification failed at LBA %d of transfer length %d"%(lba, txlen))
                #raise ValidationError.TestFailError("In readVerification()", "FAIL: Read verification operation failed")
        return status

    def readVerificationDictData(self, lbaWrittenDict):
        status = True
        #perform read operation, once the card in read only mode, all read should pass
        for lba, txlen in lbaWrittenDict.iteritems():
            try:
                self.logger.Info(self.globalVarsObj.TAG, 'READ ON LBA %d of transfer length %d' % (lba, txlen))                
                self.ccmObj.Read(lba, txlen)
            except:
                #Fail the case if read failed
                self.logger.Info(self.globalVarsObj.TAG, "FAIL: In readVerificationDictData(), Read verification failed at LBA %d of transfer length %d"%(lba, txlen))
                status = False
        return status


    def performExtraWrite(self, startLba):
        try:
            status = True
            sectorsWritten = 0
            txlen = 1024
            while sectorsWritten < self.oneSlcBlockSizeInSectors:
                self.ccmObj.Write(startLba, txlen)
                self.HistoryObj.HistoryObj.GlobalWriteData.append((startLba, txlen))                            
                self.lbaWrittenDict[startLba]=txlen #it keeps track on the same written LBA
                startLba = startLba + txlen
                sectorsWritten = sectorsWritten + txlen
        except:
            status = False
            self.logger.Info(self.globalVarsObj.TAG, "FAIL: In performExtraWrite() - Failed during write operation")
            #raise ValidationError.TestFailError(self.globalVarsObj.TAG, "FAIL: In performExtraWrite() - Failed during write operation")
        return status      
