import os
import pprint
path = 'C:\Program Files (x86)\SanDisk\SanDisk ValidationScripts\calypso_fvt_merge\sd_express_validation\Tests'

files = []
duplicatetestlist= []
# r=root, d=directories, f = files
def Setup():
    for r, d, f in os.walk(path):
        for file1 in f:
            if '.py' in file1 and '.pyc' not in file1:
                if any(char.isdigit() for char in file1):
                    test = returnDuplicate(files, file1)
                    if test != False:
                        duplicatetestlist.append([test, file1])
                    else:
                        files.append(file1)
    pprint.pprint(duplicatetestlist)
    
def returnDuplicate(testList, filename):
    if '__init__' not in filename and '_' in filename:
        testID = filename.split('_')[0]
        for test in testList:
            if testID == test.split('_')[0]:
                return test
    return False
    
if __name__=="__main__":
    Setup()