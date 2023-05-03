##
#*******************************************************************************************************
# @file            : CMDP01_MultiDataPath_ErrorInjectionTest.py
# @brief           : This test reads the Test Vectors and Config file and carries out execution of tests 
# @author          : Adarsh Sreedhar
# @date(ORG)       : 18 Jan 19
# @copyright       : Copyright (C) 2018 SanDisk Corporation
#*******************************************************************************************************

##
# @detail Internal Generic Validation libraries here
import SCSIGlobalVars
import Protocol.NVMe.Basic.TestCase as TestCase
import Core.ValidationError as ValidationError
# @detail Internal Module Specific libraries here 
import EINCTD_Library
import CMDP_Router
import WaypointReg
import EIMediator
#import CMDP_HWRouter
# @detail External libraries here 
import os
import ConfigParser
import csv
import Extensions.CVFImports as pyWrap

##
# @brief the test class
class CMDP01_MultiDataPath_ErrorInjectionTest(TestCase.TestCase):
    ##
    # @brief     A method to instantiate and define variables used by the test
    # @details   Here we instantiate objects of GlobalVars and Common Code Manager modules. 
    #            Also read the input parameters from the XML Config file and assign it to local variables
    # @Params    This method takes no parameters
    # @return    None
    # @exception None    
    def setUp(self):
        # Call the base class setUp function
        TestCase.TestCase.setUp(self)
        # for finding the folder 
        self.sandiskValidationPathValue = os.getenv("SANDISK_FVT_INSTALL_DIR")
        self.subfolderName = "Tests\\CMDP\\EI"
        self.subfolderPath = os.path.join(self.sandiskValidationPathValue, self.subfolderName)        
        # Utils & Global Vars
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)    
        self.ccmObj = self.globalVarsObj.ccmObj
        self.randomObj = self.globalVarsObj.randomObj
	self.eiObj = EIMediator.ErrorInjectionClass(self.globalVarsObj)
	self.globalVarsObj.eiObj = self.eiObj
        # other objects
        self.vtfContainer = self.globalVarsObj.vtfContainer
        self.livetObj = self.vtfContainer._livet 
        self.logger = self.globalVarsObj.logger
        self.__livetFlash = self.livetObj.GetFlash()
        self.__livetFlash.TraceOn("data_write")
        self.__livetFlash.TraceOn("data_read")
        self.__livetFlash.TraceOn('error_injected')
        self.__livetFlash.TraceOn('error_occurred')        
     
        # the main ei library where all methods are present
        self.einLibObj = EINCTD_Library.EINCTD_Library(self.vtfContainer)
       
        # We store the pass/fail value of each test vector here
        self.epwrBlocks = list()
        self.vtfContainer.cmd_line_args.IgnoreError = False
        self.ccmObj.SetLbaTracker()
        return

    ##
    # @brief      A punit style method that defines the actual logic(main algorithm) of the test
    # @details    This reads the sheet and then executes each, as required
    #             This test validates the basic access pattern tests i.e. reads and writes 
    # @return     None
    # @exception: Raise exception if there is any unexpected behavior    
    def testCMDP01_MultiDataPath_ErrorInjectionTest(self): 
        self.dictOfTestVectorPassFailStates = dict()
        # this dictionary will store the configurations set by user applied to the test vector  
        userConfigurations = self.FillDictionaryConfigValues()
        # Fetch the relevant .csv file to read vectors
        csvReaderList = self.ReadCsvFile(userConfigurations)
        num_of_rows = len(csvReaderList)
        # this dictionary will store the particulars of the current test vector for execution   
        combinationForCurrentTest = dict((key, None) for key in csvReaderList[0])
        # if the user has a specified list to do
        if userConfigurations['TestsToRun']['Tests']=='All':
            num_of_rows = len(csvReaderList)
            listOfTests = range(1, num_of_rows)
            self.randomObj.shuffle(listOfTests)
        else:
            if self.vtfContainer.cmd_line_args.testList:
                # extract the list of tests from cmd line args
                listOfTests = self.vtfContainer.cmd_line_args.testList
            else:
                # extract the string from the ini file
                listOfTests = userConfigurations['TestsToRun']['Tests']
            # since we need to convert the string to a list of tests, we extract the numbers between the brackets
            testNumbers = listOfTests[listOfTests.find('[')+1:listOfTests.find(']')]
            # assuming that the tests are seperated by commas, we use , as a delimiter
            listOfTests = testNumbers.split(',')
            # since the numbers are still in string we convert them to int
            listOfTests = [int(x) for x in listOfTests]
            # we now have a list of test numbers to be executed!
            self.randomObj.shuffle(listOfTests)
            self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'Test Vector List: %s'%(listOfTests))

        for testNumber in listOfTests:
            #del self.einLibObj.epwrBlocks[:]
	    self.logger.Info(self.globalVarsObj.TAG, "Clearing All errors")
	    ErrorManager = self.vtfContainer.device_session.GetErrorManager()
	    ErrorManager.ClearAllErrors()              
            if testNumber == 4:
                pass
            self.logger.Info(self.globalVarsObj.TAG, "Executing Test %d from the File"%(testNumber))
            row = csvReaderList[testNumber]
            self.logger.Info(self.globalVarsObj.TAG, "Executing Test %d from the File"%(testNumber)) 
            # set the dictionary particulars 
            for i in range(len(csvReaderList[0])): 
                combinationForCurrentTest[csvReaderList[0][i]] = csvReaderList[testNumber][i]
            # log once 
            self.logger.Info(self.globalVarsObj.TAG, "Test Details:\n%s"%(combinationForCurrentTest))
            
            # Perform some amount of Pre-conditioning with Write/Read/Powercycle before calling the ErrorInjector Libs
            self.einLibObj.ExecuteTest(combinationForCurrentTest, userConfigurations)
            # Call EI now
            #------------------------Heera doesnt support----------------------------------
            #self.einLibObj.InitInMode(combinationForCurrentTest['ModeBeforeSwitch'])
            #------------------------------------------------------------------------------


            assert combinationForCurrentTest['ErrorPhase'], "ErrorPhase key should be present"
            assert combinationForCurrentTest['ErrorType'], "ErrorType key should be present"	

            if(not self.vtfContainer.isModel):
                #HW
                self.cmdpRouterLib = CMDP_HWRouter.Router()
            else:
                #Model
                self.cmdpRouterLib = CMDP_Router.Router()

            #Set the Mode to Previous
            self.OriginalMode = self.globalVarsObj.SEND_TYPE

            #Change the mode
            self.globalVarsObj.SEND_TYPE = pyWrap.SEND_IMMEDIATE

            retVal = self.cmdpRouterLib.HandleError(combinationForCurrentTest, self.einLibObj)

            self.vtfContainer.device_session.GetErrorManager().DeRegisterCallback()


            #Reset the mode
            self.globalVarsObj.SEND_TYPE = self.OriginalMode

            # Store the pass/fail state for later introspection
            self.dictOfTestVectorPassFailStates[str(combinationForCurrentTest)] = retVal
            if self.globalVarsObj.readOnlyMode:	
                self.globalVarsObj.readOnlyMode=False
                self.vtfContainer.DoProduction() 
                self.setUp() 

            if retVal is not True:
                if self.vtfContainer.cmd_line_args.IgnoreError:
                    self.logger.Info(self.globalVarsObj.TAG, 'Test Vector: %s Failed, Continuing as IgnoreError Argument provided'%(combinationForCurrentTest))
                else:
                    raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestExecutionName(), testFailueDescription=retVal)
        # after finishing all vectors
        self.logger.Info(self.globalVarsObj.TAG, "All test vectors are executed!")
        # Print all test vectors and their values
        self.logger.Info(self.globalVarsObj.TAG, "Status Of Test Vectors")
        for vector, value in self.dictOfTestVectorPassFailStates.iteritems():
            self.logger.Info(self.globalVarsObj.TAG, "Vector: {0} Status: {1}".format(vector, value))
        # Check if any test vectors failed, accordingly raise Exception
        for value in self.dictOfTestVectorPassFailStates.values():
            if value != True:
                raise ValidationError.TestFailError('CMDP01', 'Not all vectors passed')
        return

    # @brief   Tear down function for test method
    # @details Does the garbage collection and draw a graph if --drawGraph=True
    # @return  None    
    def tearDown(self):
        # check if EI has to be used
        userConfigurations = self.FillDictionaryConfigValues()

        if not (self.globalVarsObj.vtfContainer.cmd_line_args.useCSVFile is not None and userConfigurations['WritesAndReads']['UseEI']=='Yes'):        
            self.einLibObj.PerformReads()
        self.einLibObj.ClearTestData()  
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
        # this will hold all the read sections and variables inside each section
        userConfigurations = dict()
        configFileName = 'CMDP_Configurables.ini'
        assert os.path.isfile(os.path.join(self.subfolderPath,configFileName)), 'File path %s doesnt exist'%(os.path.join(self.subfolderPath,configFileName))
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

    # @brief   Tear down function for test method
    # @details Does the garbage collection and draw a graph if --drawGraph=True
    # @return  csvReaderList
    def ReadCsvFile(self, userConfigurations):
        # this obj will store the csv reader obj over which we can iterate to retrieve and execute test details
        csvReaderList = list()     
        # preference to file given through command line
        if self.globalVarsObj.vtfContainer.cmd_line_args.useCSVFile is not None:
            csvFileName = self.globalVarsObj.vtfContainer.cmd_line_args.useCSVFile
        else:
            csvFileName = userConfigurations['CSVFile']['FileToUse']
        self.globalVarsObj.logger.Info(self.globalVarsObj.TAG, 'CSV File Name: %s'%(csvFileName))
        # get the file name first
        # make sure its a csv file 
        if csvFileName.endswith("csv"):
            assert os.path.isfile(os.path.join(self.subfolderPath,csvFileName)), 'File path %s doesnt exist'%(os.path.join(self.subfolderPath,csvFileName))                          
            try:
                fileLocation = os.path.join(self.subfolderPath, csvFileName)
                with open(fileLocation, 'r') as csv_file:
                    csvReaderList = list(csv.reader(csv_file, delimiter=','))
            except IOError:
                self.logger.Info(self.globalVarsObj.TAG, "File could not be found")
        else:
            raise ValidationError.TestFailError(self.globalVarsObj.vtfContainer.GetTestExecutionName(), 'Input parameter should be a .csv file')
        # return the values to the caller
        return csvReaderList