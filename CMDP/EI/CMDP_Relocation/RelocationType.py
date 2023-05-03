##
#"""
#********************************************************************************
#@file       : RelocationType.py
#@brief      : This file contains relocation type enum values from firmware
#@author     : Ganesh Pathirakani
#@date(ORG)  : 20 APR 2020
#@copyright  : copyright (C) 2020 SanDisk a Western Digital brand
#********************************************************************************
#"""

#Relocation Type Enum
RLC_TYPE_SLC_DYNAMIC       = 0
RLC_TYPE_TLC_DYNAMIC       = 1
RLC_TYPE_SLC_FORMAT        = 2
RLC_TYPE_TLC_FORMAT        = 3
RLC_TYPE_TLC_STATIC        = 4
RLC_TYPE_RS                = 5
RLC_TYPE_SLC_STATIC        = 6
RLC_TYPE_MAX               = 7           
RLC_TYPE_TERMINATE = RLC_TYPE_MAX     #7
RLC_TYPE_TERMINATE_NO_COPY = 8
RLC_TYPE_NONE              = 9
RLC_TYPE_NUM               = 10

RLC_EXPECTED_ORDER = [5, 0, 1, 4]


OBM_BLOCK_TYPE_DATA_BLK_BASE = 0
OBM_BLOCK_TYPE_TLC_BASE = OBM_BLOCK_TYPE_DATA_BLK_BASE         # TLC blocks;  Data_blks=OBM types that are host & relocation(not-control blocks)
OBM_BLOCK_TYPE_DYN_RLC = OBM_BLOCK_TYPE_TLC_BASE               # 0
OBM_BLOCK_TYPE_STC_RLC = 1                                     # 1  
OBM_BLOCK_TYPE_HOST_SHARED_TLC = 2                             # 2    = OBM_BLOCK_TYPE_HOST_SEQ_TLC
OBM_BLOCK_TYPE_HOST_SEQ_TLC = OBM_BLOCK_TYPE_HOST_SHARED_TLC
OBM_BLOCK_TYPE_SLC_BASE = 3                                    # 3
OBM_BLOCK_TYPE_HOST_SEQ_SLC = OBM_BLOCK_TYPE_SLC_BASE          # SLC blocks - 3
OBM_BLOCK_TYPE_HOST_RND_SLC = 4                                # 4
OBM_BLOCK_TYPE_CTL_BLK_BASE = 5                                # 5
OBM_BLOCK_TYPE_CTL_BLK = OBM_BLOCK_TYPE_CTL_BLK_BASE           # 5
OBM_BLOCK_TYPE_XOR = 6                                         # 6
OBM_BLOCK_TYPE_LOG = 7                                         # 7
OBM_BLOCK_TYPE_BRLC = 8                                        # 8
OBM_BLOCK_TYPE_MAX = 9                                         # 9   #Open blocks number
OBM_FIRST_XOR_PROTECTED_TYPE = OBM_BLOCK_TYPE_TLC_BASE         # 0
OBM_LAST_XOR_PROTECTED_TYPE = OBM_BLOCK_TYPE_CTL_BLK           # 5
OBM_NUM_XOR_PROTECTED_TYPES = OBM_LAST_XOR_PROTECTED_TYPE + 1  #6

# // DIAG Read Only Reasons used in Readonly_Payload_t
#typedef enum SCTP_Readonly_Reasons_e
#{
   #RO_REASON_SCTP_NONE,
   #RO_REASON_SCTP_FE,
   #RO_REASON_SCTP_FTL,
   #RO_REASON_SCTP_INVALID = MAX_UINT16,
#} VIEWEREXPORTAS(SCTP_READONLY_REASONS_XML)SCTP_Readonly_Reasons_t;

RO_REASON = {
 0 : 'RO_REASON_SCTP_NONE', 
 1 : 'RO_REASON_SCTP_FE', 
 2 : 'RO_REASON_SCTP_FTL', 
65535 : 'RO_REASON_SCTP_INVALID'
}

#// Read Only Modules used in Readonly_Payload_t
#typedef enum Readonly_Modules_e
#{
   #RO_MODULE_NONE,
   #RO_MODULE_FTL_MTM,
   #RO_MODULE_FTL_JBM,
   #RO_MODULE_FTL_MBM,
   #RO_MODULE_IFS,
   #RO_MODULE_SCTP,
   #RO_MODULE_STAT,
   #RO_MODULE_INVALID = MAX_UINT8,
#} VIEWEREXPORTAS(READONLY_MODULES_XML)Readonly_Modules_t;

RO_MODULE = {
 0 : 'RO_MODULE_NONE',
 1 : 'RO_MODULE_FTL_MTM',
 2 : 'RO_MODULE_FTL_JBM',
 3 : 'RO_MODULE_FTL_MBM',
 4 : 'RO_MODULE_IFS',
 5 : 'RO_MODULE_SCTP',
 6 : 'RO_MODULE_STAT',
 255 : 'RO_MODULE_INVALID',
}

#WAYPOINT(WP_FTL_SD_THROTTLING_START, 2, ThrottlingComponenet,  ThrottleReason)

#Where, ThorttlingComponenet and Throttle reason are as follows,

#typedef enum

#{ MVP_THROTTLE_COMP_FTL = 0,
  #MVP_THROTTLE_COMP_PS,
  #MVP_THROTTLE_COMP_INFRA,
  #MVP_THROTTLE_COMP_MAX,
#}
#MVP_ThrottleComponent_t;

MVP_THROTTLE_COMPONENT = {
    0 : 'MVP_THROTTLE_COMP_FTL',
    1 : 'MVP_THROTTLE_COMP_PS',
    2 : 'MVP_THROTTLE_COMP_INFRA',
    3 : 'MVP_THROTTLE_COMP_MAX',    
}

#typedef enum

#{
  #MVP_FTL_THROTTLE_NONE = 0,
  #MVP_FTL_THROTTLE_TRAM_LESS,
  #MVP_FTL_THROTTLE_MTM_GC,
  #MVP_FTL_THROTTLE_SAT_CONSOLIDATION,
  #MVP_FTL_THROTTLE_CUQ_FULL,
  #MVP_FTL_THROTTLE_DC_BUFFER_FULL,
  #MVP_FTL_THROTTLE_PARTIAL_BLOCK_GC,
  #MVP_FTL_THROTTLE_HOST_URGENT_GC,
  #MVP_FTL_THROTTLE_MAX,
  #}
#MVP_ThrottleReason_t;

MVP_THROTTLE_REASON = {
    0 : 'MVP_FTL_THROTTLE_NONE',
    1 : 'MVP_FTL_THROTTLE_TRAM_LESS',
    2 : 'MVP_FTL_THROTTLE_MTM_GC',
    3 : 'MVP_FTL_THROTTLE_SAT_CONSOLIDATION',
    4 : 'MVP_FTL_THROTTLE_CUQ_FULL',
    5 : 'MVP_FTL_THROTTLE_DC_BUFFER_FULL',
    6 : 'MVP_FTL_THROTTLE_PARTIAL_BLOCK_GC',
    7 : 'MVP_FTL_THROTTLE_HOST_URGENT_GC',
    8 : 'MVP_FTL_THROTTLE_MAX',    
}
#Throttling Stop WP is as follows without any params.
#WAYPOINT(WP_FTL_SD_THROTTLING_STOP, 0, 0)