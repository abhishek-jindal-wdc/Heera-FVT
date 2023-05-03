##
#"""
#********************************************************************************
#@file       : RelocationCallBack.py
#@brief      : Module contains call back functions for relocation test
#@author     : Ganesh Pathirakani
#@date(ORG)  : 20 APR 2020
#@copyright  : copyright (C) 2020 SanDisk a Western Digital brand
#********************************************************************************
#"""

import SCSIGlobalVars
import Core.ValidationError as ValidationError
import JumboBlock
import Constants
import SDUtils
import RelocationType as RelocationType
import RelocationThresholds as RelocationThresholds
from collections import defaultdict, OrderedDict


SLC_RELOCATION_VALUE = 0
TLC_RELOCATION_VALUE = 1

##
# @brief A class which contains call back functions for relocation test
class RelocationCallBack(object):
    #Create Static RelocationCallBack Object
    __staticObjRelocationCallBack           = None
    __staticRelocationCallBackObjectCreated   = False

    #TODO: Check Comments
    #Memory allocation ( This function use to create Singleton object of OrthogonalTestManager)
    def __new__(cls, *args, **kwargs):

        if not RelocationCallBack.__staticObjRelocationCallBack:
            RelocationCallBack.__staticObjRelocationCallBack = super(RelocationCallBack, cls).__new__(cls, *args, **kwargs)
        return RelocationCallBack.__staticObjRelocationCallBack

    ##
    # @brief A method to instantiate and define variables used by test cases
    # @details Here we instantiate objects of GlobalVars and logger modules.
    def __init__(self):
        #Condition to check if the variable is already created
        if RelocationCallBack.__staticRelocationCallBackObjectCreated:
            return

        #Set the static variable of class such that the object gets created ONLY once
        RelocationCallBack.__staticRelocationCallBackObjectCreated = True
        super(RelocationCallBack, self).__init__()

        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()
	self.livetObj = self.globalVarsObj.vtfContainer._livet
        self.logger = self.globalVarsObj.logger
        self.sdUtilsObj = SDUtils.SDUtils()

        self.slcDict = OrderedDict()
        self.tlcDict = OrderedDict()
        self.slcClosedBlockList = []
        self.tlcClosedBlockList = []
        self.firstSelectedJBType = None
        self.fullTargerBlockDict = {}
        self.copiedFMUsDict = {}
        self.relocationCycles = [0]
        self.accumulatedFMUsInSingleCopy = 0
        self.firstBlockSelected = True
        self.relocationOrder = []
        self.bkopsRelocations = []
        self.currentRelocationDestinationBlockJbId = []
	self.currentRelocationDestinationBlockJbIdValue = None
	self.currentRelocationDestinationBlockVba = None
        
        self.countOfVBAsRelocated = 0
        self.wlLineCount = 0
        
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

        
        #WP Flags
        self.relocationStartFlag = False
        self.relocationCompleteFlag = False
        self.isEpwrStarted = False

        self.numberOfTimesEpwrOccured = 0
        self.wlLineCount = 0
        self.countOfVBAsRelocated = 0
	self.rlcBlockReleaseFlag = False
	self.relocationSourceSelectionFlag = False
	self.relocationSourceSelectedJbIdFromWp = None
	self.relocationSourceSelectedSourceVcFromWp = None	

        self.relocationType  = None
        self.slcDynamicRelocationType = False
        self.tlcDynamicRelocationType = False
        self.slcStaticRelocationType = False
        self.tlcStaticRelocationType = False
        self.pfHandlingSuccessFlag = False
        self.tramFullFlag = False
	self.deviceIsInRoMode = False
        
        self.maxSourceSelectedBlockList = list()
        self.sourceSlcSelectedBlockList = list()
        self.sourceTlcSelectedBlockList = list()
        self.sourceSlcReleaseBlockList = list()
        self.sourceTlcReleaseBlockList = list()
        #self.slcSelectedRelocationBlockId = list()
        #self.tlcSelectedRelocationBlockId = list()
        self.currentReleasedAutoFreeSlcBlockJbId = None
        self.currentReleasedAutoFreeTlcBlockJbId = None
	self.SLC_TLC_RLCstarted = OrderedDict()
	self.TLC_TLC_RLCstarted = OrderedDict()
        self.autoFreeGcSlcBlockFlag = False
        self.autoFreeGcTlcBlockFlag = False
        self.destinationWriteJbVbaFlag = False
        self.balancedSlcGcTriggered = False
        self.balancedTlcGcTriggered = False
        self.urgentSlcGcTriggered = False
        self.urgentTlcGcTriggered = False
        self.staticRelocationTriggeredFlag = False
        self.controlSyncTriggered = False
        self.psPfDetected = False
	self.psEfDetected = False
        self.psEiUeccDetected = False
        
        self.slcStaticRelocationSourceJbId = None
        self.slcStaticRelocationDestinationJbId = None                            
        self.slcStaticRelocationSourceJbPec = None
        self.slcStaticRelocationDestinationJbPec = None 
        
        self.tlcStaticRelocationSourceJbId = None
        self.tlcStaticRelocationDestinationJbId = None                            
        self.tlcStaticRelocationSourceJbPec = None
        self.tlcStaticRelocationDestinationJbPec = None 
        
        self.Number_of_SLC_JB_allocated = 0
        self.Number_of_TLC_JB_allocated = 0
	self.Number_of_SLC_JB_closed = 0
	self.Number_of_TLC_JB_closed = 0
        self.slcObmList = list()
        self.tlcObmList = list()
        
        #Host write and Read CB  variables
        self.write_count = 0
        self.read_count = 0        
        self.currentOpenBlockId = None
        self.currentHostWriteJumboBlockId = None
        self.currentHostReadJumboBlock = None
        self.currentfTLHostWriteJumboBlockId = None
        self.currentHostWriteVbaId = None
        self.currentPickedSourceBlockJbIdForRelocationCopyFmuStep = 0
	self.tempVbaWrittenList = list() # hold two VBA one last written and current one
	self.previousHostWrittenVbaId = None
        
	self.currentPickedSourceBlockJbIdOfRelocationSourceSelectionWP = 0
        self.currentPickedSourceBlockJbVfcOfRelocationSourceSelectionWP = 0
	self.relocationSourceSelectedPartitionTypeFromWp = None
        self.slcClosedBlockJbIdList = list()
        self.tlcClosedBlockJbIdList = list()

        #PBL
        self.partialBlockJbIdGlobalDict = dict()
        self.currentlyAvailablePartialBlockJbIdDict = dict()
        self.handlingSuccessPartialBlockJbIdGlobalDict = dict()
        self.releasedPartialBlockJbId_handlingSuccessJbIdList = list()
	
	#MTM CB Variable initialization
	self.mtmVbaToWrite = None
	self.allocatedMtmBlcokJbId = list()
	self.currentAllocatedMtmBlockJbId = None
	self.mtmPfInjectedJbIdAndInjectedLbaMappingDict = dict()	

	# TARGET FULL RLC WP
	self.currentRelocationTypeOftargetBlockFullWp = 0
	self.currentRelocationTargetBlockOftargetBlockFullWp = 0
	
	# FE THROTTLE WP Flags
	self.feThrottleQueryCheckFlag = True
	self.numberOfTimesFeThrottleTriggeredCount = 0
	
	# FTL THROTTLE WP Flags
	self.throttlingFtlStartFlag = False
	self.throttlingFtlStopFlag = False
	
	# PS THROTTLE WP Flags
	self.psEhThrottleFlag = False
	
	# MTM WP Flags
	self.mtmWriteJbVbaStartFlag = False
	self.mtmPfInjected = False
	self.mtmPfInjectedJbIdAndInjectedLbaMappingDict = dict()

	# ST WP Flags	
	self.numberOfSectorsProcessedPartOfWriteSt = 0
	self.numberOfSectorsProcessedPartOfReadSt = 0
	self.stHandlingReadSuccessFlag = False
	self.stHandlingWriteSuccessFlag = False
	self.stHandlingMultiSectorReadStartFlag = False
	self.stHandlingSingleSectorReadStartFlag = False
	self.stHandlingMultiSectorWriteStartFlag = False
	self.stHandlingSingleSectorWriteStartFlag = False

	# MTM JB VBA Flag
	self.MTMVBAHistory = defaultdict(lambda:[])
	self.LatestMTMjb = None
	
	# FTL MBM Erase
	self.metaDieIdToErase = None
	self.metaBlockIdToErase = None
	self.partitionTypeToErase = None
	self.mbmFtlEraseStart = False
	self.metaBlockIdSlcEraseList = []
	self.metaBlockIdTlcEraseList = []

	# WP_FTL_SD_RLC_STRECIEVED_OR_TRAMFULL
	self.destinationRelocationTypeDuringStOrTram = None
	self.destinationRelocationPhaseDuringStOrTram = None
		
    # @brief     Waypoint callback methods
    # @return    None
    # @exception Raises an exception if there is any unexpected behavior
    def CB_WP_HOST_WRITE_COMPLETE(self, eventKeys, arg, processorID):
        #WP_HOST_WRITE_COMPLETE, 2, opbId, jba.jumboBlockId
	#self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_HOST_WRITE_COMPLETE appeared with arguments: %s" % str(arg))
        self.currentOpenBlockId = int(arg[0])
        self.currentHostWriteJumboBlockId = int(arg[1])
        #self.logger.Info(self.globalVarsObj.TAG, 'WP_HOST_WRITE_COMPLETE Open block ID - %s and Jumbo block ID - %s' % (str(arg[0]), str(arg[1])))
        self.write_count = self.write_count + 1
        return


    def CB_WP_HOST_READ_COMPLETE(self, eventKeys, arg, processorID):
        #WP_HOST_READ_COMPLETE, 1, jba.jumboBlockId
	#self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_HOST_READ_COMPLETE appeared with arguments: %s" % str(arg))
        self.currentHostReadJumboBlock = int(arg[0])
        #self.logger.Info(self.globalVarsObj.TAG, 'WP_HOST_READ_COMPLETE Jumbo block ID - %s' % str(arg[0]))
        self.read_count = self.read_count + 1
        return      
    
    
    def CB_WP_FTL_HWD_WRITE_JB_VBA(self, eventKeys, arg, processorID):
        #2, jba.jumboBlockId, vba.vba32
	#self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_HWD_WRITE_JB_VBA appeared with arguments: %s" % str(arg))
	self.previousHostWrittenVbaId = self.currentHostWriteVbaId
        self.currentfTLHostWriteJumboBlockId = int(arg[0])
        self.currentHostWriteVbaId = int(arg[1])
	self.tempVbaWrittenList = [self.previousHostWrittenVbaId, self.currentHostWriteVbaId]
	
	
        #self.logger.Info(self.globalVarsObj.TAG, 'WP_FTL_HWD_WRITE_JB_VBA Jumbo block ID - %s and Current Host Write Vba ID - %s' % (str(arg[0]), str(arg[1])))
        return    


    def CB_WP_FTL_BML_JUMBOBLOCK_ALLOCATED(self, eventKeys, arg, processorID):
        #3 - jumboblock id, partitionId (SLC/TLC), jumboblock PEC
	#self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_BML_JUMBOBLOCK_ALLOCATED appeared with arguments: %s" % str(arg))
        #self.logger.Info(self.globalVarsObj.TAG, 'WP_FTL_BML_JUMBOBLOCK_ALLOCATED Jumbo block ID - %s' % str(arg[0]))
        #self.logger.Info(self.globalVarsObj.TAG, 'WP_FTL_BML_JUMBOBLOCK_ALLOCATED Partition ID (SLC/TLC) - %s' % str(arg[1]))
        #self.logger.Info(self.globalVarsObj.TAG, 'WP_FTL_BML_JUMBOBLOCK_ALLOCATED Jumbo block PEC - %s' % str(arg[2]))
        return


    def CB_WP_FTL_RLC_RLC_START(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_RLC_START appeared with arguments: %s" % str(arg))
        #self.relocationStartFlag = True
        #self.relocationType = int(arg[0])
        #if self.relocationType == RelocationType.RLC_TYPE_SLC_DYNAMIC:
            #self.slcDynamicRelocationType = True
            #self.logger.Info(self.globalVarsObj.TAG, "SLC to TLC Dynamic Balanced Relocation triggered") 
        #elif self.relocationType == RelocationType.RLC_TYPE_TLC_DYNAMIC:
            #self.tlcDynamicRelocationType = True
            #self.logger.Info(self.globalVarsObj.TAG, "TLC to TLC Dynamic Balanced Relocation triggered")
        #elif self.relocationType == RelocationType.RLC_TYPE_SLC_STATIC:
            #self.slcStaticRelocationType = True
            #self.logger.Info(self.globalVarsObj.TAG, "SLC Static Relocation triggered") 
        #elif self.relocationType == RelocationType.RLC_TYPE_TLC_STATIC:
            #self.tlcStaticRelocationType = True
            #self.logger.Info(self.globalVarsObj.TAG, "TLC Static Relocation triggered")         
        return


    def CB_WP_FTL_RLC_RLC_COMPLETE(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_RLC_COMPLETE appeared with arguments: %s" % str(arg))
        self.relocationCompleteFlag = True
        return
    

    def CB_WP_FTL_RLC_WRITE_JB_VBA(self, eventKeys, arg, processorID):
        #2, dstJba.jumboBlockId, vba.vba32
	#self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_WRITE_JB_VBA appeared with arguments: %s" % str(arg))
        self.destinationWriteJbVbaFlag = True
	self.currentRelocationDestinationBlockJbIdValue = arg[0]
        self.currentRelocationDestinationBlockJbId.append(arg[0])
        self.currentRelocationDestinationBlockVba = arg[1]
        
        # enter this only when slc->tlc relocation has started, and this WP gets hit once for every 48FMU transfer
        self.countOfVBAsRelocated = self.countOfVBAsRelocated + 1
        # at a time, 48FMUs are copied, must calculate how many times are hit for one full wl has been relocated
        if self.countOfVBAsRelocated == self.numOfTimesToWriteOneTlcJwl:
            self.wlLineCount = self.wlLineCount + 1
            self.logger.Info(self.globalVarsObj.TAG, "%s WL has been relocated as count of VBAs hit under this waypoint" % str(self.wlLineCount))
            self.countOfVBAsRelocated = 0        
        return


    def CB_WP_PS_EPWR_ACTIVATE(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_PS_EPWR_ACTIVATE appeared with arguments: %s" % str(arg))
        self.isEpwrStarted = True
        self.numberOfTimesEpwrOccured = self.numberOfTimesEpwrOccured + 1
        return


    def CB_WP_FTL_RLC_GC_TYPE(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_GC_TYPE appeared with arguments: %s" % str(arg))
        #WP_FTL_RLC_GC_TYPE, 2, GC type (1-balanced and 0 - urgent), partition_p->partition (0-SLC, 1-TLC)
        #This flag condition enabling need to update
	#self.relocationStartFlag = True
        self.rlcType = arg[0]
        self.rlcPartitionType = arg[1]
        if self.rlcType == Constants.Numerical_Constants.CONST_NUMERICAL_ONE:
            if self.rlcPartitionType == Constants.Numerical_Constants.CONST_NUMERICAL_ZERO:
                self.logger.Info(self.globalVarsObj.TAG, "SLC Balanced Relocation triggered")
                self.balancedSlcGcTriggered = True              
            elif self.rlcPartitionType == Constants.Numerical_Constants.CONST_NUMERICAL_ONE:
                self.logger.Info(self.globalVarsObj.TAG, "TLC Balanced Relocation triggered")
                self.balancedTlcGcTriggered = True  
        elif self.rlcType == Constants.Numerical_Constants.CONST_NUMERICAL_ZERO:
            if self.rlcPartitionType == Constants.Numerical_Constants.CONST_NUMERICAL_ZERO:
                self.logger.Info(self.globalVarsObj.TAG, "SLC Urgent Relocation triggered")
                self.urgentSlcGcTriggered = True
            elif self.rlcPartitionType == Constants.Numerical_Constants.CONST_NUMERICAL_ONE:
                self.logger.Info(self.globalVarsObj.TAG, "TLC Urgent Relocation triggered")
                self.urgentTlcGcTriggered = True
        else:
            self.logger.Info(self.globalVarsObj.TAG, "Invalid Relocation type striggered")
        return


    ##
    # @brief callback function for waypoint WP_BML_JUMBO_BLOCK_ALLOCATED.
    # @details
    # @param arg - list of output parameters of waypoint:
    # arg[0] - Block ID
    # arg[1] - Block Type (SLC - 0 /TLC - 1)
    # arg[2] - Block PEC
    def CB_WP_FTL_OBM_JUMBO_BLOCK_ALLOC(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_OBM_JUMBO_BLOCK_ALLOC appeared with arguments: %s" %str(arg))
    
        blockId = int(arg[0])
        blockType = int(arg[1])
        blockPEC = int(arg[2])
        obmBlockType = int(arg[3])

        if(obmBlockType < 5):
            if(blockType == 0):
                self.Number_of_SLC_JB_allocated += 1             
                self.slcObmList.append(blockId)
                if(blockId in self.slcDict):
		    pass
                    #self.slcDict[blockId].PEC = blockPEC
                else:
                    newSLCBlock = JumboBlock.JumboBlock()
                    newSLCBlock.blockID = blockId
                    newSLCBlock.blockType = blockType
                    #newSLCBlock.PEC = blockPEC
                    self.slcDict.update({blockId : newSLCBlock})

            elif(blockType == 1):
                self.Number_of_TLC_JB_allocated += 1
                self.tlcObmList.append(blockId)
                if(blockId in self.tlcDict):
		    pass
                    #self.tlcDict[blockId].PEC = blockPEC
                else:
                    newTLCBlock = JumboBlock.JumboBlock()
                    newTLCBlock.blockID = blockId
                    newTLCBlock.blockType = blockType
                    #newTLCBlock.PEC = blockPEC
                    self.tlcDict.update({blockId : newTLCBlock})
            else:
                raise ValidationError.TestFailError("WP_FTL_OBM_JUMBO_BLOCK_ALLOC", "Wrong block type parameter return from Waypoint WP_FTL_BML_JUMBOBLOCK_ALLOCATED")
	return


    ##
    # @brief callback function for waypoint WP_FTL_RLC_SOURCE_BLOCK_SELECTED.
    # @details
    # @param arg - list of output parameters of waypoint:
    # arg[0] - Relocation Type (FW Enum)
    # arg[1] - Block ID
    # arg[2] - Source Block VC
    def CB_WP_FTL_RLC_SOURCE_BLOCK_SELECTED(self, eventKeys, arg, processorID):
	self.relocationStartFlag = True
	self.relocationType = int(arg[0])
	if self.relocationType == RelocationType.RLC_TYPE_SLC_DYNAMIC:
	    self.slcDynamicRelocationType = True
	    self.logger.Info(self.globalVarsObj.TAG, "SLC to TLC Dynamic Balanced Relocation triggered") 
	elif self.relocationType == RelocationType.RLC_TYPE_TLC_DYNAMIC:
	    self.tlcDynamicRelocationType = True
	    self.logger.Info(self.globalVarsObj.TAG, "TLC to TLC Dynamic Balanced Relocation triggered")
	elif self.relocationType == RelocationType.RLC_TYPE_SLC_STATIC:
	    self.slcStaticRelocationType = True
	    self.logger.Info(self.globalVarsObj.TAG, "SLC Static Relocation triggered") 
	elif self.relocationType == RelocationType.RLC_TYPE_TLC_STATIC:
	    self.tlcStaticRelocationType = True
	    self.logger.Info(self.globalVarsObj.TAG, "TLC Static Relocation triggered")

        #gRlcCycleParams.rlcType, gRlcCycleParams.currSourceBlockJba.jumboBlockId, gRlcCycleParams.sourceVC
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_SOURCE_BLOCK_SELECTED appeared with arguments: %s" %str(arg))
        
        relocationType = int(arg[0])
        blockId= int(arg[1])
        sourceBlockVC = int(arg[2])
	self.relocationSourceSelectionFlag = True
	self.relocationSourceSelectedPartitionTypeFromWp = relocationType
	self.relocationSourceSelectedJbIdFromWp = blockId
	self.relocationSourceSelectedSourceVcFromWp = sourceBlockVC
        if(relocationType == RelocationType.RLC_TYPE_SLC_DYNAMIC):
	    self.SLC_TLC_RLCstarted[blockId]=[RelocationType.RLC_TYPE_SLC_DYNAMIC]
	    self.logger.Info(self.globalVarsObj.TAG, "Waypoint SLC Closed Blocks JBID: %s" % str(self.slcClosedBlockJbIdList))
	    self.logger.Info(self.globalVarsObj.TAG, "Waypoint SLC CLosed blocks Dict %s" % str(self.slcDict))
            #self.slcSelectedRelocationBlockId.append(blockId)
            self.sourceSlcSelectedBlockList.append(blockId)
            #self.maxSourceSelectedBlockList.append(blockId)
            self.currentPickedSourceBlockJbIdOfRelocationSourceSelectionWP = blockId
            self.currentPickedSourceBlockJbVfcOfRelocationSourceSelectionWP = sourceBlockVC
            #if(blockId not in self.slcDict):
                #raise ValidationError.TestFailError("SLC to TLC dynamic", "Selected source block doesn't exist in allocated SLC dictionary!")

        elif(relocationType == RelocationType.RLC_TYPE_TLC_DYNAMIC):
	    self.TLC_TLC_RLCstarted[blockId] = [RelocationType.RLC_TYPE_TLC_DYNAMIC]
	    self.logger.Info(self.globalVarsObj.TAG, "Waypoint TLC CLosed blocks JBID %s" % str(self.tlcClosedBlockJbIdList))
	    self.logger.Info(self.globalVarsObj.TAG, "Waypoint TLC CLosed blocks Dict %s" % str(self.tlcDict))
            #self.tlcSelectedRelocationBlockId.append(blockId)
            self.sourceTlcSelectedBlockList.append(blockId)
            #if(blockId not in self.tlcDict):
                #raise ValidationError.TestFailError("TLC to TLC dynamic", "Selected source block doesn't exist in allocated TLC dictionary!")

        elif(relocationType == 2):
            pass
        elif(relocationType == 3):
            pass
        elif(relocationType == 4):
            pass
        elif(relocationType == 5):
            pass
        elif(relocationType == 6):
            pass
        elif(relocationType == 7):
            pass
        else:
            raise ValidationError.TestFailError("WP_FTL_RLC_SOURCE_BLOCK_SELECTED", "Unknown relocation type!")
	return


    ##
    # @brief callback function for waypoint WP_FTL_RLC_SOURCE_BLOCK_SELECTED.
    # @details
    # @param arg - list of output parameters of waypoint:
    # arg[0] - Block ID
    # arg[1] - Block Type (SLC/TLC)
    # arg[2] - Data Type (Sequential/Random)
    def CB_WP_FTL_OBM_JUMBO_BLOCK_CLOSED(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_OBM_JUMBO_BLOCK_CLOSED appeared with arguments: %s" %str(arg))

        blockId = int(arg[0])
        blockType = int(arg[1])
        dataType = int(arg[2])
        obmBlockType = int(arg[3])

        if(obmBlockType < 5):
            if(blockType == 0):
		if(blockId in self.slcDict):
		    self.Number_of_SLC_JB_closed = self.Number_of_SLC_JB_closed + 1
                    self.slcClosedBlockList.append(self.slcDict[blockId])
                    self.slcClosedBlockJbIdList.append(blockId)
                else:
		    self.Number_of_SLC_JB_closed = self.Number_of_SLC_JB_closed + 1
		    self.slcClosedBlockJbIdList.append(blockId)
		    self.slcDict[blockId] = 999999 #'Added during block closure WP, due to block closed outside the RLC handler operation'
                    self.logger.Info(self.globalVarsObj.TAG, "INFO: WP_FTL_OBM_JUMBO_BLOCK_CLOSED, Closed data block doesn't exist in SLC allocated blocks dictionary!")
                    #raise ValidationError.TestFailError("WP_FTL_OBM_JUMBO_BLOCK_CLOSED", "Closed data block doesn't exist in SLC allocated blocks dictionary!")

            elif(blockType == 1):
                if(blockId in self.tlcDict) or (blockId in self.globalVarsObj.OpenCloseBlockList['TLC']['OB']):
		    self.Number_of_TLC_JB_closed = self.Number_of_TLC_JB_closed + 1
                    self.tlcClosedBlockList.append(self.tlcDict[blockId])
                    self.tlcClosedBlockJbIdList.append(blockId)
                else:
		    self.Number_of_TLC_JB_closed = self.Number_of_TLC_JB_closed + 1
		    self.tlcClosedBlockJbIdList.append(blockId)
		    self.tlcDict[blockId] =  999999 #'Added during block closure WP, due to block closed outside the RLC handler operation'
		    self.logger.Info(self.globalVarsObj.TAG, "INFO: WP_FTL_OBM_JUMBO_BLOCK_CLOSED, Closed data block doesn't exist in SLC allocated blocks dictionary!")
                    #raise ValidationError.TestFailError("WP_OBM_JUMBO_BLOCK_CLOSED", "Closed data block doesn't exist in TLC allocated blocks dictionary!")
            else:
                raise ValidationError.TestFailError("WP_OBM_JUMBO_BLOCK_CLOSED", "Wrong block type parameter return from Waypoint WP_OBM_JUMBO_BLOCK_CLOSED")
	return


    ##
    # @brief callback function for waypoint FTL_RLC_TARGET_BLOCK_FULL.
    # @details
    # @param arg - list of output parameters of waypoint:
    # arg[0] -
    # arg[1] -
    # arg[2] -
    def CB_WP_FTL_RLC_TARGET_BLOCK_FULL(self, eventKeys, arg, processorID):
	# 2, gRlcCycleParams.rlcType, dstJBA.jumboBlockId
	self.currentRelocationTypeOftargetBlockFullWp = arg[0]
	self.currentRelocationTargetBlockOftargetBlockFullWp = arg[1]
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_TARGET_BLOCK_FULL appeared with arguments: %s" %str(arg))
	return

    ##
    # @brief callback function for waypoint WP_FTL_RLC_SOURCE_BLOCK_RELEASED.
    # @details
    # @param arg - list of output parameters of waypoint:
    # arg[0] - Block ID
    # arg[1] - Relocation Type (FW Enum)
    def CB_WP_FTL_RLC_SOURCE_BLOCK_RELEASED(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_SOURCE_BLOCK_RELEASED appeared with arguments: %s" %str(arg))

        blockId = int(arg[0])
        relocationType = int(arg[1])
	self.rlcBlockReleaseFlag = True
        if(relocationType == RelocationType.RLC_TYPE_SLC_DYNAMIC):
            #self.slcSelectedRelocationBlockId.remove(blockId)
            self.sourceSlcReleaseBlockList.append(blockId)
	    if blockId in self.slcClosedBlockJbIdList:
		#self.maxSourceSelectedBlockList.remove(blockId)
		self.slcClosedBlockJbIdList.remove(blockId) #as soon as source block is released after relocation, remove the JB ID from SLC closed block list
        elif(relocationType == RelocationType.RLC_TYPE_TLC_DYNAMIC):
            #self.tlcSelectedRelocationBlockId.remove(blockId)
	    self.sourceTlcReleaseBlockList.append(blockId)
	    if blockId in self.tlcClosedBlockJbIdList:
		self.tlcClosedBlockJbIdList.remove(blockId) #as soon as source block is released after relocation, remove the JB ID from TLC closed block list
        else:
            self.logger.Info(self.globalVarsObj.TAG, "Block type couldn't be recognized, no item was removed from the Dictionaries!")
	return

    ##
    # @brief callback function for waypoint WP_FTL_RLC_COPY_FMUS.
    # @details
    # @param arg - list of output parameters of waypoint:
    # arg[0] - Block ID
    # arg[1] - Amount Of FMUs (mostly 48)
    # arg[2] - First FFLBA
    # arg[3] - Is Last Copy boolean value
    def CB_WP_FTL_RLC_COPY_FMUS(self, eventKeys, arg, processorID):
        #5, gBuffersManager.copiedCurrJbid, fmusToWrite, gBuffersManager.pCpyBuffer[0].fflba, 1, dstJBA.jumboBlockId
	#self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_COPY_FMUS appeared with arguments: %s" %str(arg))

        blockId = arg[0]
        amountOfFMUs = arg[1]
        firstFFLBA = arg[2]
        isLastCopy = arg[3]
        
        self.currentPickedSourceBlockJbIdForRelocationCopyFmuStep = arg[0]

        #if not last copy (from the 48 FMUs), accumulate FMUs
        if (isLastCopy == 0):
            if (self.accumulatedFMUsInSingleCopy != 0):
                # adapt amountOfFMUs to delta only for this source
                amountOfFMUs -= self.accumulatedFMUsInSingleCopy

            #print 'not last copy, amountOfFMUs = %d, accumulatedFMUsInSingleCopy = %d' %(amountOfFMUs, accumulatedFMUsInSingleCopy)
            self.accumulatedFMUsInSingleCopy += amountOfFMUs           #update accumulatedFMUsInSingleCopy to current position


        else:                   #last FMUs from the 48
            amountOfFMUs -= self.accumulatedFMUsInSingleCopy
            #print 'last copy, amountOfFMUs = %d, accumulatedFMUsInSingleCopy = %d' %(amountOfFMUs, accumulatedFMUsInSingleCopy)
            self.accumulatedFMUsInSingleCopy = 0

        if ((blockId in self.slcDict) or (blockId in self.tlcDict)):
            self.copiedFMUsDict.update({blockId : (firstFFLBA, amountOfFMUs)})
	else:
	    self.copiedFMUsDict.update({blockId : (firstFFLBA, amountOfFMUs)})
            #raise ValidationError.TestFailError("WP_FTL_RLC_COPY_FMUS", "Wanted block doesn't exist in SLC or TLC allocated blocks dictionaries!")

    ##
    # @brief callback function for waypoint WP_FTL_RLC_CYCLE_TERMINATE.
    # @details
    # @param arg - list of output parameters of waypoint:
    # arg[0] -
    # arg[1] -
    def CB_WP_FTL_RLC_CYCLE_TERMINATE(self, eventKeys, arg, processorID):
	self.logger.Info(self.globalVarsObj.TAG, "Waypoint WP_FTL_RLC_CYCLE_TERMINATE appeared with arguments: %s" %str(arg))
        relocationCompleted = arg[0]
        self.relocationCycles[Constants.START_INDEX] += 1
	return
