#!/usr/bin/env python
from multiprocessing.managers import BaseManager
from multiprocessing.managers import BaseProxy
import os
import multiprocessing.util

multiprocessing.util.log_to_stderr()

timelines = None

current_timeline = None

# mode can be of 'normal', 'replay', 'redo', 'undo'
mode = 'normal'

# sde ... side effects dictionary ic:effect effect is a function
# Will be overwritten by an proxy to the manager
sde = {}

# ude ... undo effects dictionary ic:effect effect is a function
ude = {}

manager = None
server = None

modules = []

ic = 0

server_sde = {}
#server_ude = {}

dict = None

class DictManager(BaseManager):
    pass

def get_sde():
    return server_sde


#DictManager.register('get_ude', callable=lambda:server_ude, proxytype=DictProxy)

def start_server():
    class DictProxy(BaseProxy):
        _exposed_ = ['__getitem__', '__setitem__','__str__','__repr__']
        def __getitem__(self, value):
            ret = self._callmethod('__getitem__',(value,))
            return ret
        def __setitem__(self, idx, value):
            self._callmethod('__setitem__',(value,))
        def __repr__(self):
            return self._callmethod('__repr__')
        def __str__(self):
            return self._callmethod('__str__')
    
    d = {}
    def getdict():
        return d
    
    if os.fork():
        class DictManager(BaseManager):
            pass
        DictManager.register('dict', getdict, proxytype=DictProxy)
        m = DictManager(address=('', 50000), authkey=b'epdb')
        s = m.get_server()
        s.serve_forever()
        sys.exit(0)    
    
def connect():
    global manager
    global dict
    DictManager.register('dict')
    #dict = m.get_dict()
    #dict[123] = {}
    manager = DictManager(address=('localhost', 50000), authkey=b'epdb')
    manager.connect()
    dict = manager.dict()
    
if __name__ == '__main__':   
    import sys
    import os
    import time
    from multiprocessing.managers import BaseManager
    from multiprocessing.managers import BaseProxy
    
    start_server()
    
    #class DictProxy(BaseProxy):
    #    _exposed_ = ['__getitem__', '__setitem__','__str__','__repr__']
    #    def __getitem__(self, value):
    #        ret = self._callmethod('__getitem__',(value,))
    #        return ret
    #    def __setitem__(self, idx, value):
    #        self._callmethod('__setitem__',(value,))
    #    def __repr__(self):
    #        return self._callmethod('__repr__')
    #    def __str__(self):
    #        return self._callmethod('__str__')
    #
    #d = {}
    #def getdict():
    #    return d
    #
    #if os.fork():
    #    class DictManager(BaseManager):
    #        pass
    #    DictManager.register('dict', getdict, proxytype=DictProxy)
    #    m = DictManager(address=('', 50000), authkey=b'epdb')
    #    s = m.get_server()
    #    s.serve_forever()
    #    sys.exit(0)
    
    time.sleep(0.5)
    #
    DictManager.register('dict')
    #dict = m.get_dict()
    #dict[123] = {}
    manager = DictManager(address=('localhost', 50000), authkey=b'epdb')
    manager.connect()
    sde = manager.dict()
    #connect()
    if os.fork():
        sde[1] = 'hallo Welt'
        sde[2] = 'Number2'
        time.sleep(3)
    else:
        #connect()
        #del m
        #del sde
        time.sleep(1)
        manager = DictManager(address=('localhost', 50000), authkey=b'epdb')
        manager.connect()
        sde = manager.dict()
        time.sleep(0.5)
        sde[3] = 'Blah'
        print('done', sde, sde[1])