##
#"""
#********************************************************************************
#@file       : JumboBlock.py
#@brief      : This file contains JumboBlock object attributes
#@author     : Ganesh Pathirakani
#@date(ORG)  : 20 APR 2020
#@copyright  : copyright (C) 2020 SanDisk a Western Digital brand
#********************************************************************************
#"""


class JumboBlock(object):
    def __init__(self):
        
        self.isBlockClosed = False
        self.dataType = None
        self.blockType = None
        self.blockID = None
        self.VC = None
        self.PEC = None
        self.BER = 0
        self.selected = False
        self.isActive = False