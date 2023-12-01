# -*- coding: utf-8 -*-
"""
Created on Mon May  4 15:40:07 2020

@author: Elliott Runburg
"""
import sys, os, time
from datetime import datetime
from queue import Queue
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from qcodes.logger import start_all_logging


class TeeOut(object):
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stdout = sys.stdout
        sys.stdout = self

    def __del__(self):
        sys.stdout = self.stdout
        self.file.close()

    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)

    def flush(self):
        self.file.flush()


class TeeErr(object):
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stderr = sys.stderr
        sys.stderr = self

    def __del__(self):
        sys.stderr = self.stderr
        self.file.close()

    def write(self, data):
        self.file.write(data)
        self.stderr.write(data)

    def flush(self):
        self.file.flush()


class NotebookLogger(QObject):
    def __init__(self):
        super().__init__()
        # Let's define where we want our logging to occur
        self.stdout_filename = os.environ['MeasureItHome'] + '\\logs\\stdout\\' + datetime.now().strftime(
            "%Y-%m-%d") + '.txt'
        self.stderr_filename = os.environ['MeasureItHome'] + '\\logs\\stderr\\' + datetime.now().strftime(
            "%Y-%m-%d") + '.txt'
        self.stdout_file = None
        self.stderr_file = None
        self.thread = None

    def start(self):
        # Create Queue and redirect sys.stdout to this queue
        out_queue = Queue()
        sys.stdout = WriteStream(out_queue)
        err_queue = Queue()
        sys.stderr = WriteStream(err_queue)

        self.stderr_file = open(self.stderr_filename, 'a')

        self.thread = AllOutputThread(out_queue, err_queue)
        self.thread.outsignal.connect(self.append_stdout)
        self.thread.errsignal.connect(self.append_stderr)
        self.thread.start()

        print('Started logging at  ' + datetime.now().strftime("%H:%M:%S"))
        self.stderr_file.write('Started logging at  ' + datetime.now().strftime("%H:%M:%S") + '\n')
        # self.stdout_file.close()
        self.stderr_file.close()

        start_all_logging()

    @pyqtSlot(str)
    def append_stdout(self, text):
        print(text)
        self.stdout_file = open(self.stdout_filename, 'a')
        t = datetime.now().strftime("%H:%M:%S")
        self.stdout_file.write(t + '\t' + text)
        self.stdout_file.close()

    @pyqtSlot(str)
    def append_stderr(self, text):
        print(text, file=sys.stderr)
        self.stderr_file = open(self.stderr_filename, 'a')
        t = datetime.now().strftime("%H:%M:%S")
        self.stderr_file.write(t + '\t' + text)
        self.stderr_file.close()

    def __del__(self):
        if self.thread is not None:
            self.thread.stop = True
            self.thread.exit()
            if not self.thread.wait(5000):
                self.thread.terminate()
                print("Forced stdout thread to terminate.", file=sys.stderr)

        self.stdout_file = open(self.stdout_filename, 'a')
        self.stdout_file.write("Program exited at " + datetime.now().strftime("%H:%M:%S") + '\n')
        self.stderr_file = open(self.stderr_filename, 'a')
        self.stderr_file.write("Program exited at " + datetime.now().strftime("%H:%M:%S") + '\n')
        self.stdout_file.close()
        self.stderr_file.close()


class AllOutputThread(QThread):
    outsignal = pyqtSignal(str)
    errsignal = pyqtSignal(str)

    def __init__(self, out_queue, err_queue):
        self.out_queue = out_queue
        self.err_queue = err_queue
        self.stop = False
        QThread.__init__(self)

    def run(self):
        while self.stop is False:
            while not self.out_queue.empty():
                text = self.out_queue.get(block=False)
                self.outsignal.emit(text)
            while not self.err_queue.empty():
                text = self.err_queue.get(block=False)
                self.errsignal.emit(text)
            time.sleep(.1)


# The new Stream Object which replaces the default stream associated with sys.stdout
# This object just puts data in a queue!
class WriteStream(object):
    def __init__(self, queue):
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
        while self.stop is False:
            while not self.queue.empty():
                text = self.queue.get(block=False)
                self.mysignal.emit(text)
            time.sleep(.1)
