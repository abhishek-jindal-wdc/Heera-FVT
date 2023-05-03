import Constants
import SCSIGlobalVars
import Core.ValidationError as ValidationError
import ErrorInjectorLib
import SctpUtils
import WayPointHandler
import SDUtils
import Extensions.CVFImports as pyWrap
import WayPointHandler



class EpicCallbacks(object):
    __staticECObj = None
    __staticEpicCallbacksBackObjectCreated   = False
    
    
    def __new__(cls, *args, **kwargs):

        if not EpicCallbacks.__staticECObj:
            EpicCallbacks.__staticECObj = super(EpicCallbacks,cls).__new__(cls, *args, **kwargs)

        return EpicCallbacks.__staticECObj    
    
    
    def HistoryObj(self):
        return self.HistoryObj
    
    def RegisterWaypoints(self):
        self.wayPointDict = {
            #"WP_PS_PF_DETECTED"                : [self.PFdetectedCallback],
                    }
        self.wayPointHandlerObj.RegisterWP(self.wayPointDict)    
        
    
    def __init__(self):
        if EpicCallbacks.__staticEpicCallbacksBackObjectCreated:
            return
        
        EpicCallbacks.__staticEpicCallbacksBackObjectCreated = True
        super(EpicCallbacks, self).__init__()
        
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars()    
        self.livetObj = self.globalVarsObj.vtfContainer._livet
        self.logger = self.globalVarsObj.logger        
        self.wayPointHandlerObj = WayPointHandler.WayPointHandler(self.livetObj, self.logger,  self.globalVarsObj)
        self.HistoryObj = History()
        self.Verbose = False        
        #self.RegisterWaypoints()
    

class History(object):
    
    __staticHObj = None
    __staticHObjObjectCreated   = False

    ##
    # @brief A method to create a singleton object of LOG PF HANDLER
    # @param cls : The class being created
    # @param args : positional argument
    # @param kwargs : keyword argument
    # @return Returns the class singleton instance
    def __new__(cls, *args, **kwargs):

        if not History.__staticHObj:
            History.__staticHObj = super(History,cls).__new__(cls, *args, **kwargs)

        return History.__staticHObj
    
    
    def __init__(self):
        if History.__staticHObjObjectCreated:
            return
        
        History.__staticHObjObjectCreated = True
        super(History, self).__init__()
        
        self.BadBlockList = []
        self.PartialBlockList = []
        self.RelinkedBlocks = []
        self.BadIFSblocks = []
        self.LastWrittenLBA = 0
        self.GlobalWriteData = []

    
    def __del__(self):
        pass
    
        