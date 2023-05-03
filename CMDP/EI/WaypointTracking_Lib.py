import Constants
import GlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap

class WaypointTracking_Lib:
    __staticWPTrackingObj = None

    ##
    # @brief A method to create a singleton object of WP Tracking Lib
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):
        if not __staticWPTrackingObj__staticWPTrackingObj.__staticObj:
            __staticWPTrackingObj.__staticObj = super(__staticWPTrackingObj,cls).__new__(cls, *args, **kwargs)
        return __staticWPTrackingObj.__staticObj
    
    def __init__(self):
        self.InitialiseWPFlag()
        self.InitialiseWPCounters()
        self.globalVarsObj = GlobalVars.GlobalVars()
        if self.globalVarsObj.vtfContainer.isModel is True:
            self.livetObj = self.globalVarsObj.vtfContainer._livet 
            self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.globalVarsObj.logger)
            self.wayPointDict = {
                #"WP_FTL_OBM_JUMBO_BLOCK_ALLOC":['PrintArguments', self.WP_FTL_OBM_JUMBO_BLOCK_ALLOC_Callback],#new wp
                #"WP_FTL_OBM_JUMBO_BLOCK_WL":['PrintArguments'],
                #"WP_LOG_JUMBO_BLOCK_WL":['PrintArguments'],
                #"WP_FTL_MTM_JB_VBA":['PrintArguments'],
                #"WP_FTL_HWD_WRITE_JB_VBA":['PrintArguments', self.WP_FTL_HWD_WRITE_JB_VBA_Callback],
                #"D_MODEL_FTL_HWD_PADDING":['PrintArguments'],
                #"D_MODEL_FTL_HWD_STREAM_STATUS":['PrintArguments'],
                #"WP_FTL_MBM_METABLOCK_ERASED":['PrintArguments'], #new wp
                #"D_MODEL_FTL_HWD_START_WRITE":['PrintArguments'],
                #"WP_FTL_HWD_WRITE_JB_VBA":['PrintArguments'],
                #"WP_HOST_WRITE_COMPLETE":['PrintArguments'],
                #"D_MODEL_FTL_HWD_ROUTING_RULES":['PrintArguments',self.D_MODEL_FTL_HWD_ROUTING_RULES_Callback],
                #"WP_FWR_INFRA_FFU_WRITE_PARAMETERS":['PrintArguments'],
                #"WP_FTL_READONLY_TRIGGER":[self.WP_FTL_READONLY_TRIGGER_Callback],
                #"WP_MTM_GC_COMPLETE":['PrintArguments'],
                #"WP_FTL_XOR_JB_VBA":['PrintArguments'],
                #"WP_INFRA_IFS_IN_BOOTPAGE_UPDATE":['PrintArguments'],
                #"WP_FTL_RLC_RLC_START ":['PrintArguments', self.WP_FTL_RLC_RLC_START_Callback],
                #"WP_FTL_RLC_ALLOC_BRLC_BLOCK":['PrintArguments'],
                #"WP_FTL_RLC_AUTO_FREE_JB_RELEASED":['PrintArguments'],
                #"WP_FTL_RLC_SOURCE_BLOCK_RELEASED":['PrintArguments'],
                #"WP_FTL_RLC_SOURCE_BLOCK_SELECTED":['PrintArguments'],
                #"WP_FTL_RLC_TARGET_BLOCK_FULL":['PrintArguments'],
                #"WP_FTL_RLC_WRITE_JB_VBA":['PrintArguments'],
                #"WP_DST_VC_CHECK_FINISHED":['PrintArguments']
            }
            self.wayPointHandlerObj.RegisterWP(self.wayPointDict)    
            
    def InitialiseWPFlag(self):
        
        return
    
    def InitialiseWPCounters(self):
        self.dictOfVBAWritten = dict()
        self.isSLCToTLCRelocationStart = False
        self.isTLCToSLCRelocationStart = False
        self.isSlcSeqBlockWriteTriggered = False
        self.isSlcRanBlockWriteTriggered = False
        self.isXorBlockWriteTriggered = False
        self.isLogBlockWriteTriggered = False
        self.isBRLCTriggered = False
        return
    
    def WP_FTL_HWD_WRITE_JB_VBA_Callback(self,eventKeys, args, processorID):
        # args:  2, jba.jumboBlockId, vba.vba32
        self.dictOfVBAWritten[args[0]] = args[1]
        return
    
    def D_MODEL_FTL_HWD_ROUTING_RULES_Callback(self,eventKeys, args, processorID):
        # 3, phwdCtxt->groupID, HWD_CB.HhwWfm.accumType, HWD_CB.HhwWfm.opbId'
        '''
        typedef enum OBM_BlockType_e
        {
            OBM_BLOCK_TYPE_DATA_BLK_BASE = 0,
            OBM_BLOCK_TYPE_TLC_BASE = OBM_BLOCK_TYPE_DATA_BLK_BASE,  //TLC blocks;  Data_blks=OBM types that are host & relocation(not-control blocks)
            OBM_BLOCK_TYPE_DYN_RLC = OBM_BLOCK_TYPE_TLC_BASE,        // 0
            OBM_BLOCK_TYPE_STC_RLC,                                  // 1  
            OBM_BLOCK_TYPE_HOST_SHARED_TLC ,                         // 2    = OBM_BLOCK_TYPE_HOST_SEQ_TLC                    
            OBM_BLOCK_TYPE_SLC_BASE,                                 // 3
            OBM_BLOCK_TYPE_HOST_SEQ_SLC = OBM_BLOCK_TYPE_SLC_BASE,   //SLC blocks - 3
            OBM_BLOCK_TYPE_HOST_RND_SLC,                             // 4
            OBM_BLOCK_TYPE_CTL_BLK_BASE,                             // 5
            OBM_BLOCK_TYPE_CTL_BLK = OBM_BLOCK_TYPE_CTL_BLK_BASE,    // 5
            OBM_BLOCK_TYPE_XOR,                                      // 6
            OBM_BLOCK_TYPE_LOG,                                      // 7
            OBM_BLOCK_TYPE_BRLC,                                     // 8
            OBM_BLOCK_TYPE_MAX,         //Open blocks number         // 9
            OBM_FIRST_XOR_PROTECTED_TYPE = OBM_BLOCK_TYPE_TLC_BASE,  // 0
            OBM_LAST_XOR_PROTECTED_TYPE = OBM_BLOCK_TYPE_CTL_BLK,    // 5
            OBM_NUM_XOR_PROTECTED_TYPES = OBM_LAST_XOR_PROTECTED_TYPE + 1, //6
            OBM_BLOCK_TYPE_PHYSICALLY_CLOSED = 0xff,
            OBM_BLOCK_TYPE_ILLEGAL = OBM_BLOCK_TYPE_PHYSICALLY_CLOSED,
        } VIEWEREXPORTAS(FFUSET_OBM_BlockType_t) OBM_BlockType_t;
        '''
        if args[2] == 3:
            self.isSlcSeqBlockWriteTriggered = True
        elif args[2] == 4:
            self.isSlcRanBlockWriteTriggered = True
        elif args[2] == 6:
            self.isXorBlockWriteTriggered = True
        elif args[2] == 7:
            self.isLogBlockWriteTriggered = True
        elif args[2] == 8:
            self.isBRLCTriggered = True
        return
    
    # @brief   
    # @details 
    # @param   None
    # @return  None        
    def WP_FTL_RLC_RLC_START_Callback(self,eventKeys, args, processorID):
        if args[0]==0:
            self.isSLCToTLCRelocationStart = True   
        elif args[0]==1:
            self.isTLCToSLCRelocationStart = True
        return        
    
    