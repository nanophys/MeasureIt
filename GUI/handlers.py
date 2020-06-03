# -*- coding: utf-8 -*-
"""
Created on Mon May  4 15:40:07 2020

@author: Elliott Runburg
"""

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
import time

# The new Stream Object which replaces the default stream associated with sys.stdout
# This object just puts data in a queue!
class WriteStream(object):
    def __init__(self,queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text)
        
    def flush(self):
        pass
    

class OutputThread(QThread):
    mysignal = pyqtSignal(str)
    
    def __init__(self, queue):
        self.queue = queue
        self.stop = False
        QThread.__init__(self)
        
    def run(self):
        while self.stop == False:
            while not self.queue.empty():
                text = self.queue.get(block=False)
                self.mysignal.emit(text)
            time.sleep(.1)