#!/usr/bin/env python

import random
import dbg
import debug as log

#def randint(a, b):
#    def replay(a, b):
#        log.debug('Replaying randint', dbg.ic)
#        return dbg.nde[dbg.ic]
#    def undo(a, b):
#        log.debug('undoing randint')
#    def debug(a, b):
#        value = random.__orig__randint(a, b)
#        dbg.nde[dbg.ic] = value
#        log.debug('debugging randint')
#        return value
#    def redo(a, b):
#        log.debug("redoing randint")
#        return dbg.nde[dbg.ic]
#    log.debug('This is the modified randint', a, b)
#    if dbg.mode == 'replay':
#        return replay(a, b)
#    elif dbg.mode == 'normal':
#        return debug(a, b)
#    elif dbg.mode == 'redo':
#        return redo(a, b)
#    elif dbg.mode == 'undo':
#        return
   
def seed(a=None):
    if dbg.mode == 'normal':
        random.__orig__seed(a)
        dbg.snapshottingcontrol.set_make_snapshot()
        return