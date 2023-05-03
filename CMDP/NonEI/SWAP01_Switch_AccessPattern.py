##
#***********************************************************************************************
# @file            : SWAP01_Switch_AccessPattern.py
# @brief           : This test reads the sheet and config file and carries out execution of tests 
# @author          : Adarsh 
# @date(ORG)       : 18 Jan 19
# @copyright       : Copyright (C) 2018 SanDisk Corporation
#***********************************************************************************************

##
# @detail Internal Generic Validation libraries here
import SCSIGlobalVars 
import Protocol.SCSI.Basic.TestCase as TestCase
import Core.ValidationError as ValidationError

# @detail Internal Module Specific libraries here 
import SWAPCTD_Library

# @detail External libraries here 
import os
import ConfigParser
import csv

##
# @brief the test class
class SWAP01_Switch_AccessPattern(TestCase.TestCase):
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
        self.sandiskValidationPathValue = os.getenv("FVTPATH")
        self.subfolderName = "\\Tests\\CMDP\\NonEI"
        self.subfolderPath = self.sandiskValidationPathValue + self.subfolderName     
        # Utils & Global Vars
        self.globalVarsObj = SCSIGlobalVars.SCSIGlobalVars(self.vtfContainer)   
        self.ccmObj = self.globalVarsObj.ccmObj
        self.randomObj = self.globalVarsObj.randomObj
        # other objects
        self.logger = self.globalVarsObj.logger
        # the main ei library where all methods are present
        self.swapLibObj = SWAPCTD_Library.SWAPCTD_Library(self.vtfContainer)
        # Set the default temparature to 298K
        #self.globalVarsObj.vtfContainer._livet.GetController().SetTemperature(298)
        return
    
    ##
    # @brief      A punit style method that defines the actual logic(main algorithm) of the test
    # @details    This reads the sheet and then executes each, as required
    #             This test validates the basic access pattern tests i.e. reads and writes 
    # @return     None
    # @exception: Raise exception if there is any unexpected behavior    
    def testSWAP01_Switch_AccessPattern(self): 
        userConfigurations = self.FillDictionaryConfigValues()
        csvReaderList = self.ReadCsvFile(userConfigurations)
        combinationForCurrentTest = dict((key, None) for key in csvReaderList[0])
        
        if userConfigurations['TestsToRun']['Tests']=='All':
            num_of_rows = len(csvReaderList)
            listOfTests = range(1, num_of_rows)
            self.randomObj.shuffle(listOfTests)
        elif self.vtfContainer.cmd_line_args.testList:
                # extract the list of tests from cmd line args
                listOfTests = self.vtfContainer.cmd_line_args.testList
                # since we need to convert the string to a list of tests, we extract the numbers between the brackets
                testNumbers = listOfTests[listOfTests.find('[')+1:listOfTests.find(']')]
                # assuming that the tests are seperated by commas, we use , as a delimiter
                listOfTests = testNumbers.split(',')
                # since the numbers are still in string we convert them to int
                listOfTests = [int(x) for x in listOfTests]
                # we now have a list of test numbers to be executed!
                self.randomObj.shuffle(listOfTests)
        else:
            num_of_rows = len(csvReaderList)
            RangeOfTestRows = range(1, num_of_rows)
            listOfTests = self.randomObj.sample(RangeOfTestRows, 5)            
            
        for testNumber in listOfTests:
            row = csvReaderList[testNumber]
            self.logger.Info(self.globalVarsObj.TAG, "Executing Test %d from the File"%(testNumber)) 
            # set the dictionary particulars 
            for i in range(len(csvReaderList[0])): 
                combinationForCurrentTest[csvReaderList[0][i]] = csvReaderList[testNumber][i] 
            # log once 
            self.logger.Info(self.globalVarsObj.TAG, "Test Details:\n%s"%(combinationForCurrentTest))
            # execute this row
            self.swapLibObj.ExecuteTest(combinationForCurrentTest, userConfigurations)
            self.tearDown()      
        # after finishing all vectors 
        self.logger.Info(self.globalVarsObj.TAG, "All test combinations are executed!") 
        # if we still have time left, then we can run few more test cases
        # self.CheckWhetherToRunAgain()
        return
    
    # @brief   Tear down function for test method
    # @details Does the garbage collection and draw a graph if --drawGraph=True
    # @return  None    
    def tearDown(self):
        # check if EI has to be used
        userConfigurations = self.FillDictionaryConfigValues()
        if not (self.globalVarsObj.vtfContainer.cmd_line_args.useCSVFile is not None and userConfigurations['WritesAndReads']['UseEI']=='Yes'):        
            self.swapLibObj.PerformReads()
        self.swapLibObj.ClearTestData()  
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
        try:
            configFileName = 'SWAP_CTD_Configurables.ini'
            config.read(os.path.join(self.subfolderPath,configFileName))
            sections = config.sections()
            for section in sections:
                userConfigurations[section] = {}
                options = config.options(section)
                for option in options:
                    userConfigurations[section][option]=config.get(section, option)
        except:
            raise ValidationError.TestFailError(self.vtfContainer.GetTestName, "Error parsing config file")           
        return userConfigurations
    
    # @brief   Tear down function for test method
    # @details Does the garbage collection and draw a graph if --drawGraph=True
    # @return  csvReaderList
    def ReadCsvFile(self, userConfigurations):
        # this obj will store the csv reader obj over which we can iterate to retrieve and execute test details
        csvReaderList = list()
        # this dictionary will store the particulars of the current test combination in the CTD
        combinationForCurrentTest = dict()        
        # preference to file given through command line
        if self.globalVarsObj.vtfContainer.cmd_line_args.useCSVFile is not None:
            csvFileName = self.globalVarsObj.vtfContainer.cmd_line_args.useCSVFile
        else:
            csvFileName = userConfigurations['CSVFile']['FileToUse']        
        # get the file name first
        # make sure its a csv file 
        if csvFileName.endswith("csv"):
            try:
                fileLocation = os.path.join(self.subfolderPath, csvFileName)
                with open(fileLocation, 'r') as csv_file:
                    csvReaderList = list(csv.reader(csv_file, delimiter=','))
            except IOError:
                self.logger.Info(self.globalVarsObj.TAG, "File could not be found")
        else:
            raise ValidationError.TestFailError(self.vtfContainer.GetTestName, 'should be a .csv file')
        # return the values to the caller
        return csvReaderList  
