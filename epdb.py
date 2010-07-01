import pdb
import sys
import linecache
import cmd
import bdb
from reprlib import Repr
import os
import os.path
import re
import pprint
import traceback
import snapshotting
import builtins
import types
import _thread
import configparser
import shareddict
from debug import debug

dbgpath = None

def readconfig():
    global dbgpath
    sys.path = origpath
    try:
        config = configparser.ConfigParser()
        config.read(os.path.expanduser("~/.config/epdb.conf"))
        dbgmods = config.get('Main', 'dbgmods')
    except:
        dbgmods = '/home/patrick/myprogs/epdb/dbgmods'
    dbgpath = dbgmods
    sys.path.append(dbgmods)

origpath = sys.path[:]
readconfig()

#debug("PATH: ", sys.path)

import dbg

__pythonimport__ = builtins.__import__

__all__ = ["run", "pm", "Epdb", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

mode = 'normal'

def __import__(*args):
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename) in ['epdb.py', 'snaphotting.py', 'dbg.py', 'shareddict.py', 'debug.py', 'bdb.py', "cmd.py", "fnmatch.py"]:
        return __pythonimport__(*args)
    else:
        pass
    new = True
    if args[0] in dbg.modules:
        new = False
    mod = __pythonimport__(*args)
    
    if new:
        dbg.modules.append(args[0])
        if args[0][:2] != '__':
            try:
                module = __pythonimport__('__'+args[0], globals(), locals(), [])
                #debug("success")
            except ImportError:
                pass
                #debug("nosuccess", sys.path)
            else:
                #debug('Importing a module with patching', args[0])
                for key in module.__dict__.keys():
                    if key == args[0]:
                        continue
                    if key in ['__builtins__', '__file__', '__package__', '__name__', '__doc__', 'dbg']:
                        continue
                    
                    # if the name doesn't exist in the original file -> ignore it
                    try:
                        setattr(mod, '__orig__'+key, getattr(mod,key))
                        setattr(mod, key, getattr(module, key))
                    except AttributeError:
                        pass
    return mod

class EpdbExit(Exception):
    """Causes a debugger to be exited for the debugged python process."""
    pass

class EpdbPostMortem(Exception):
    """Raised when the program finishes and enters a interactive shell"""
    pass

class SnapshotData:
    def __init__(self, id, ic):
        self.id = id
        self.ic = ic
        self.references = 0

class Epdb(pdb.Pdb):
    def __init__(self):
        pdb.Pdb.__init__(self, skip=['random', 'debug', 'fnmatch', 'epdb', 'posixpath', 'shareddict', 'pickle'])
        self.init_reversible()
    
    def is_skipped_module(self, module_name):
        """Extend to skip all modules that start with double underscore"""
        base = pdb.Pdb.is_skipped_module(self, module_name)
        if base == True:
            return True
        
        if module_name == '__main__':
            return False
        return module_name.startswith('__')
    
    def findsnapshot(self, ic):
        """Looks for a snpashot to use for stepping backwards.
        Returns snapshot data"""
        #debug("findsnapshot", ic)
        bestic = -1
        bestsnapshot = None
        for k in self.snapshots.keys():
            e = self.snapshots[k]
            debug("try snapshot: ",e.id,e.ic)
            if e.ic <= ic:
                if e.ic > bestic:
                    bestic = e.ic
                    bestsnapshot = e
                    #debug("bestsnapshot found")
                else:
                    pass
                    #debug("snapshot ic smaller than best ic")
            else:
                pass
                #debug("snapshot ic bigger than current ic")
        return bestsnapshot
                
    def make_snapshot(self):
        snapshot = snapshotting.Snapshot(dbg.ic, self.snapshot_id)
        self.psnapshot = self.snapshot
        self.psnapshot_id = self.snapshot_id
        self.pss_ic = self.ss_ic
        self.snapshot = snapshot
        self.snapshot_id = snapshot.id
        # self.ss_ic = self.ic
        self.ss_ic = dbg.ic
        
        snapshotdata = SnapshotData(id=self.snapshot_id, ic=dbg.ic)
        self.snapshots[snapshotdata.id] = snapshotdata
        
        dbg.current_timeline.add(snapshotdata.id)
        if snapshot.step_forward > 0:
            dbg.mode = 'replay'
            self.stopafter = snapshot.step_forward + 1
            return 1
        else:
            return
    
    #def precmd(self, line):
    #    #debug("precommand")
    #    return line

    def preloop(self):
        debug("ic: ", dbg.ic)
    
    def _runscript(self, filename):
        # The script has to run in __main__ namespace (or imports from
        # __main__ will break).
        #
        # So we clear up the __main__ and set several special variables
        # (this gets rid of pdb's globals and cleans old variables on restarts).
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({"__name__"    : "__main__",
                                  "__file__"    : filename,
                                  "__builtins__": __builtins__,
                                })

        # When bdb sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).
        self._wait_for_mainpyfile = 1
        self.mainpyfile = self.canonic(filename)
        self._user_requested_quit = 0
        globals = __main__.__dict__
        #locals = globals
        debug("##################",dbgpath)
        sys.path.append('/home/patrick/myprogs/epdb/dbgmods')

        with open(filename, "rb") as fp:
            statement = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), self.mainpyfile)
        builtins.__import__ = __import__            
        self.run(statement)
        
    def init_reversible(self):
        self.mp = snapshotting.MainProcess()
        from breakpoint import Breakpoint
        #self.ic = 0             # Instruction Counter
        self.ron = True
        
        dbg.ic = 0
        
        self.starting_ic = None
        
        self.ss_ic = 0
        self.snapshot = None
        self.snapshot_id = None
        
        self.pss_ic = 0
        self.psnapshot = None
        self.psnapshot_id = None
        
        self.prompt = '(Epdb) '
        self.running_mode = None
        self.stopafter = -1
        
        # The call_stack contains ic for every call in a previous frame
        # This is used in user_return to find its corresponding call
        self.call_stack = []
        
        # In rnext_ic the position for the rnext command to jump to is saved
        # It is filled in user_return
        self.rnext_ic = {}
        
        # In rcontinue_ln for every execute line number a list of instruction counts
        # that have executed them is saved. This is needed for reverse continue
        self.rcontinue_ln = {}
        
        # steps from last snapshot
        self.stepsfromlastss = None
        
        self.breaks = shareddict.DictProxy('breaks')
        self.snapshots = shareddict.DictProxy('snapshots')
    
    def trace_dispatch(self, frame, event, arg):
        # debug("trace_dispatch")
        return pdb.Pdb.trace_dispatch(self, frame, event, arg)
    
    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        lineno = frame.f_lineno     # TODO extend with filename so to support different files
        filename = frame.f_code.co_filename
        filename = self.canonic(filename)
        
        try:
            self.rcontinue_ln[(filename,lineno)].append(dbg.ic+1)
        except:
            self.rcontinue_ln[(filename,lineno)] = [dbg.ic+1]
        
        if self.running_mode == 'continue':
            dbg.ic += 1
            if self.break_here(frame):
                self.interaction(frame, None)
        elif self.running_mode == 'next':
            dbg.ic += 1
            if self.nocalls <= 0:
                self.interaction(frame, None)
            if self.break_here(frame):
                self.interaction(frame, None)
        else:
            if self._wait_for_mainpyfile:
                if (self.mainpyfile != self.canonic(frame.f_code.co_filename) or frame.f_lineno<= 0):
                    return
                self.make_snapshot()
                self._wait_for_mainpyfile = 0
            else:
                dbg.ic += 1
            
            if self.starting_ic is None:
                if frame.f_code.co_filename == self.mainpyfile:
                    self.starting_ic = dbg.ic
                    debug("starting ic: ", self.starting_ic)
            
            if self.stopafter > 0:
                #debug('stopafter > 0', self.stopafter)
                self.stopafter -= 1
            
            if self.stopafter == 0:
                #debug('stopafter == 0')
                self.stopafter = -1
                #debug(dbg.mode)
                dbg.mode = 'normal'
                self.set_trace()
            
            if self.bp_commands(frame) and self.stopafter == -1:
                #debug("Interaction")
                self.interaction(frame, None)
        
    def user_call(self, frame, argument_list):
        
        self.call_stack.append(dbg.ic)
        
        if dbg.mode == 'replay':
            pass
        elif self.running_mode == 'continue':
            pass
        elif self.running_mode == 'next':
            self.nocalls += 1
        elif self.running_mode == 'step':
            pass
        else:
            if self._wait_for_mainpyfile:
                return
            debug('Calling interaction', self.running_mode)
            self.interaction(frame, None)
    
    def stop_here(self, frame):
        if pdb.Pdb.stop_here(self, frame):
            return True
        return False

    def set_continue(self):
        if not self.ron:
            return pdb.Pdb.set_continue(self)
        # Debugger overhead needed to count instructions
        self.set_step()
        self.running_mode = 'continue'

    def do_snapshot(self, arg, temporary=0):
        """snapshot - makes a snapshot"""
        r = self.make_snapshot()
        if self.stopafter > 0:
            self.stopafter -= 1
        return r
    
    def do_restore(self, arg):
        """Restore a previous Snapshot, e.g. restore 0"""
        # TODO leave current timeline and go into roff mode
        try:
            id = int(arg)
        except:
             debug('You need to supply an index, e.g. restore 0')
             return
        self.mp.activatesp(id)
        raise EpdbExit()
    
    def do_ude(self, arg):
        """Shows the current ude. Debugging only."""
        debug('ude:', dbg.ude)
    
    def do_sde(self, arg):
        """Shows the current sde. Debugging only."""
        debug('sde:', dbg.sde)
    
    def do_snapshots(self, arg):
        """Lists all snapshots"""
        debug("id        ic")
        debug("------------")
        for k in self.snapshots.keys():
            e = self.snapshots[k]
            print(e.id, e.ic)
        self.mp.list_snapshots()

    def do_ic(self, arg):
        """Shows the current instruction count"""
        debug('The instruction count is:', dbg.ic)
        
    def do_timelines(self, arg):
        """List all timelines."""
        dbg.timelines.show()
    
    def do_switch_timeline(self, arg):
        """Switch to another timeline"""
        debug("Doesn't work yet")
        return
        try:
            timeline = dbg.timelines.get(arg)
        except:
            debug("Timeline '",arg,"' dosn't exist", sep='')
            return    
        dbg.current_timeline.deactivate(dbg.ic)
        dbg.ic = timeline.get_ic()
        dbg.sde = timeline.get_sde()
        dbg.timelines.set_current_timeline(timeline.get_name())
        dbg.current_timeline = timeline
        snapshot = self.findsnapshot(dbg.ic)
        
    def do_current_timeline(self, arg):
        """View the name of the current timeline"""
        dbg.current_timeline.show()
        
    def do_newtimeline(self, arg):
        """Create a new timeline. This allows changing the program flow from the last run"""
        if arg.strip() == '':
            debug("You need to supply a name for the new timeline")
            return
        newtimeline = dbg.current_timeline.copy(arg.strip(), dbg.ic)
        dbg.current_timeline.deactivate(dbg.ic)
        #dbg.ic = newtimeline.get_ic() # not necessary here because it is the same as in the previous one
        dbg.sde = newtimeline.get_sde()
        dbg.timelines.set_current_timeline(newtimeline.get_name())
        dbg.current_timeline = newtimeline
        
    def do_quit(self, arg):
        self._user_requested_quit = 1
        self.mp.quit()
        self.set_quit()
        return 1
    
    def do_replay(self, arg):
        """Debugging only. TODO remove if not needed anymore"""
        dbg.mode = 'replay'
    
    def do_mode(self, arg):
        """Shows the current mode."""
        debug("mode: ", dbg.mode)
        
    def do_ron(self, arg):
        """Enables reverse debugging"""
        # TODO create or activate a new timeline
        self.ron = True
    
    def do_roff(self, arg):
        """Disables reverse debugging"""
        if self.ron:
            self.ron = False
            dbg.current_timeline.deactivate(dbg.ic)
    
    def do_rstep(self, arg):
        """Steps one step backwards"""
        
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return
        
        if dbg.ic == 0:
            debug("At the beginning of the program. Can't step back")
            return
        
        actual_ic = dbg.ic
        
        s = self.findsnapshot(dbg.ic-1)
        if s == None:
            debug("No snapshot made. Can't step back")
            return
        
        # Undo last step
        try:
            dbg.ude[dbg.ic - 1]()
            del dbg.ude[dbg.ic - 1]
        except KeyError:
            pass
        
        if s == None:
            debug("No snapshot made. Can't step back")
            return
        
        steps = dbg.ic - s.ic - 1
        debug('snapshot activation', s.id, steps)
        self.mp.activatesp(s.id, steps)
        raise EpdbExit()
        
    def do_rnext(self, arg):
        """Reverse a next command."""
        
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return
        
        if dbg.ic == 0:
            debug("At the beginning of the program. Can't step back")
            return
        
        nextic = self.rnext_ic.get(dbg.ic, dbg.ic-1)
        
        s = self.findsnapshot(nextic)
        if s == None:
            debug("No snapshot made. Can't step back")
            return
        
        # Undo last steps
        for i in range(dbg.ic, nextic,-1):
            debug("undo ic: ", i)
            try:
                dbg.ude[dbg.ic - i - 1]()
                del dbg.ude[dbg.ic - i -1]
            except KeyError:
                pass
        
        steps = nextic - s.ic
        debug('snapshot activation', s.id, steps)
        self.mp.activatesp(s.id, steps)
        raise EpdbExit()
        
    def do_rcontinue(self, arg):
        """Continues in backward direction"""
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return
            
        if dbg.ic == 0:
            debug("At the beginning of the program. Can't step back")
            return

        # Find the breakpoint with the highest ic
        from breakpoint import Breakpoint
        highestic = 0
        for bp in Breakpoint.bplist:
            debug("Checking Bp: ", bp)
            try:
                newmax = max(self.rcontinue_ln[bp][-1], highestic)
                if newmax < dbg.ic:
                    highestic = newmax
            except KeyError:
                pass
            
        debug("Highest ic found: ", highestic)

        s = self.findsnapshot(highestic)
        if s == None:
            debug("No snapshot made. Can't step back")
            return

        # Undo last steps
        for i in range(dbg.ic, highestic,-1):
            debug("undo ic: ", i)
            try:
                dbg.ude[dbg.ic - i - 1]()
                del dbg.ude[dbg.ic - i -1]
            except KeyError:
                pass
            
        steps = highestic - s.ic
        debug('snapshot activation', s.id, steps)
        self.mp.activatesp(s.id, steps)
        raise EpdbExit()
        
    def set_next(self, frame):
        """Stop on the next line in or below the given frame."""
        if not self.ron:
            return pdb.Pdb.set_next(self, frame)
        self.set_step()
        self.running_mode = 'next'
        self.nocalls = 0 # Increased on call - decreased on return
        
    def do_step(self, arg):
        if not self.ron:
            return pdb.Pdb.do_step(self, arg)
        self.set_step()
        self.running_mode = 'step'
        return 1
    do_s = do_step # otherwise the pdb impl is called
        
    def set_quit(self):
        pdb.Pdb.set_quit(self)
    
    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        try:
            callic = self.call_stack.pop()
        except:
            #TODO this usually happens
            debug("the program has finished")
        self.rnext_ic[dbg.ic + 1] = callic
        
        if  self.running_mode == 'continue':
            pass
        elif  self.running_mode == 'next':
            self.nocalls -= 1
        elif  self.running_mode == 'step':
            pass
        else:
            frame.f_locals['__return__'] = return_value
            debug('--Return--')
            self.interaction(frame, None)
    
    # The following functions are the same as in bdp except for
    # The usage of the epdb Breakpoint implementation
    
    def break_here(self, frame):
        filename = self.canonic(frame.f_code.co_filename)
        if not filename in self.breaks:
            return False
        lineno = frame.f_lineno
        if not lineno in self.breaks[filename]:
            # The line itself has no breakpoint, but maybe the line is the
            # first line of a function with breakpoint set by function name.
            lineno = frame.f_code.co_firstlineno
            if not lineno in self.breaks[filename]:
                return False

        # flag says ok to delete temp. bp
        (bp, flag) = effective(filename, lineno, frame)
        if bp:
            self.currentbp = bp.number
            if (flag and bp.temporary):
                self.do_clear(str(bp.number))
            return True
        else:
            return False
        
    def set_break(self, filename, lineno, temporary=0, cond = None,
                  funcname=None):
        from breakpoint import Breakpoint
        filename = self.canonic(filename)
        import linecache # Import as late as possible
        line = linecache.getline(filename, lineno)
        if not line:
            return 'Line %s:%d does not exist' % (filename,
                                   lineno)
        if not filename in self.breaks:
            self.breaks[filename] = []
        list = self.breaks[filename]
        if not lineno in list:
            list.append(lineno)
            self.breaks[filename] = list  # This is necessary for the distributed application
        bp = Breakpoint(filename, lineno, temporary, cond, funcname)

    def clear_break(self, filename, lineno):
        from breakpoint import Breakpoint
        filename = self.canonic(filename)
        if not filename in self.breaks:
            return 'There are no breakpoints in %s' % filename
        if lineno not in self.breaks[filename]:
            return 'There is no breakpoint at %s:%d' % (filename,
                                    lineno)
        # If there's only one bp in the list for that file,line
        # pair, then remove the breaks entry
        for bp in Breakpoint.bplist[filename, lineno][:]:
            bp.deleteMe()
        if (filename, lineno) not in Breakpoint.bplist:
            self.breaks[filename].remove(lineno)
        if not self.breaks[filename]:
            del self.breaks[filename]

    def clear_bpbynumber(self, arg):
        from breakpoint import Breakpoint
        try:
            number = int(arg)
        except:
            return 'Non-numeric breakpoint number (%s)' % arg
        try:
            bp = Breakpoint.bpbynumber[number]
        except IndexError:
            return 'Breakpoint number (%d) out of range' % number
        if not bp:
            return 'Breakpoint (%d) already deleted' % number
        self.clear_break(bp.file, bp.line)

    def clear_all_file_breaks(self, filename):
        from breakpoint import Breakpoint
        filename = self.canonic(filename)
        if not filename in self.breaks:
            return 'There are no breakpoints in %s' % filename
        for line in self.breaks[filename]:
            blist = Breakpoint.bplist[filename, line]
            for bp in blist:
                bp.deleteMe()
        del self.breaks[filename]

    def clear_all_breaks(self):
        from breakpoint import Breakpoint
        if not self.breaks:
            return 'There are no breakpoints'
        for bp in Breakpoint.bpbynumber:
            if bp:
                bp.deleteMe()
        #self.breaks = {}
        self.breaks.clear()   # As this is a shared dictionary it is important to use clear
    
    def get_break(self, filename, lineno):
        filename = self.canonic(filename)
        return filename in self.breaks and \
            lineno in self.breaks[filename]

    def get_breaks(self, filename, lineno):
        from breakpoint import Breakpoint
        filename = self.canonic(filename)
        if filename in self.breaks:
            debug("Get_breaks: Filename", filename)
        return filename in self.breaks and \
            lineno in self.breaks[filename] and \
            Breakpoint.bplist[filename, lineno] or []

    def get_file_breaks(self, filename):
        filename = self.canonic(filename)
        if filename in self.breaks:
            return self.breaks[filename]
        else:
            return []

    def get_all_breaks(self):
        return self.breaks
    
    def do_break(self, arg, temporary = 0):
        from breakpoint import Breakpoint
        # break [ ([filename:]lineno | function) [, "condition"] ]
        if not arg:
            if self.breaks:  # There's at least one
                print("Num Type         Disp Enb   Where", file=self.stdout)
                for bp in Breakpoint.bpbynumber:
                    if bp:
                        bp.bpprint(self.stdout)
            return
        # parse arguments; comma has lowest precedence
        # and cannot occur in filename
        filename = None
        lineno = None
        cond = None
        comma = arg.find(',')
        if comma > 0:
            # parse stuff after comma: "condition"
            cond = arg[comma+1:].lstrip()
            arg = arg[:comma].rstrip()
        # parse stuff before comma: [filename:]lineno | function
        colon = arg.rfind(':')
        funcname = None
        if colon >= 0:
            filename = arg[:colon].rstrip()
            f = self.lookupmodule(filename)
            if not f:
                print('*** ', repr(filename), end=' ', file=self.stdout)
                print('not found from sys.path', file=self.stdout)
                return
            else:
                filename = f
            arg = arg[colon+1:].lstrip()
            try:
                lineno = int(arg)
            except ValueError as msg:
                print('*** Bad lineno:', arg, file=self.stdout)
                return
        else:
            # no colon; can be lineno or function
            try:
                lineno = int(arg)
            except ValueError:
                try:
                    func = eval(arg,
                                self.curframe.f_globals,
                                self.curframe_locals)
                except:
                    func = arg
                try:
                    if hasattr(func, '__func__'):
                        func = func.__func__
                    code = func.__code__
                    #use co_name to identify the bkpt (function names
                    #could be aliased, but co_name is invariant)
                    funcname = code.co_name
                    lineno = code.co_firstlineno
                    filename = code.co_filename
                except:
                    # last thing to try
                    (ok, filename, ln) = self.lineinfo(arg)
                    if not ok:
                        print('*** The specified object', end=' ', file=self.stdout)
                        print(repr(arg), end=' ', file=self.stdout)
                        print('is not a function', file=self.stdout)
                        print('or was not found along sys.path.', file=self.stdout)
                        return
                    funcname = ok # ok contains a function name
                    lineno = int(ln)
        if not filename:
            filename = self.defaultFile()
        # Check for reasonable breakpoint
        line = self.checkline(filename, lineno)
        if line:
            # now set the break point
            err = self.set_break(filename, line, temporary, cond, funcname)
            if err: print('***', err, file=self.stdout)
            else:
                bp = self.get_breaks(filename, line)[-1]
                print("Breakpoint %d at %s:%d" % (bp.number,
                                                                 bp.file,
                                                                 bp.line), file=self.stdout)

# copied from pdb to make use of epdb's breakpoint implementation
def effective(file, line, frame):
    from breakpoint import Breakpoint
    """Determine which breakpoint for this file:line is to be acted upon.

    Called only if we know there is a bpt at this
    location.  Returns breakpoint that was triggered and a flag
    that indicates if it is ok to delete a temporary bp.

    """
    possibles = Breakpoint.bplist[file,line]
    for i in range(0, len(possibles)):
        b = possibles[i]
        if b.enabled == 0:
            continue
        if not bdb.checkfuncname(b, frame):
            continue
        # Count every hit when bp is enabled
        b.hits = b.hits + 1
        if not b.cond:
            # If unconditional, and ignoring,
            # go on to next, else break
            if b.ignore > 0:
                b.ignore = b.ignore -1
                continue
            else:
                # breakpoint and marker that's ok
                # to delete if temporary
                return (b,1)
        else:
            # Conditional bp.
            # Ignore count applies only to those bpt hits where the
            # condition evaluates to true.
            try:
                val = eval(b.cond, frame.f_globals,
                       frame.f_locals)
                if val:
                    if b.ignore > 0:
                        b.ignore = b.ignore -1
                        # continue
                    else:
                        return (b,1)
                # else:
                #   continue
            except:
                # if eval fails, most conservative
                # thing is to stop on breakpoint
                # regardless of ignore count.
                # Don't delete temporary,
                # as another hint to user.
                return (b,0)
    return (None, None)

def run(statement, globals=None, locals=None):
    Epdb().run(statement, globals, locals)

def runeval(expression, globals=None, locals=None):
    return Epdb().runeval(expression, globals, locals)

def runctx(statement, globals, locals):
    # B/W compatibility
    run(statement, globals, locals)

def runcall(*args, **kwds):
    return Epdb().runcall(*args, **kwds)

def set_trace():
    Epdb().set_trace(sys._getframe().f_back)

# Post-Mortem interface

def post_mortem(t=None):
    # handling the default
    if t is None:
        # sys.exc_info() returns (type, value, traceback) if an exception is
        # being handled, otherwise it returns None
        t = sys.exc_info()[2]
        if t is None:
            raise ValueError("A valid traceback must be passed if no "
                                               "exception is being handled")

    p = Epdb()
    p.reset()
    p.interaction(None, t)

def pm():
    post_mortem(sys.last_traceback)
    
    # Main program for testing

TESTCMD = 'import x; x.main()'

def test():
    run(TESTCMD)

# print help
def help():
    for dirname in sys.path:
        fullname = os.path.join(dirname, 'epdb.doc')
        if os.path.exists(fullname):
            sts = os.system('${PAGER-more} '+fullname)
            if sts: print('*** Pager exit status:', sts)
            break
    else:
        pass
        #print('Sorry, can\'t find the help file "epdb.doc"', end=' ')
        #print('along the Python search path')

def main():
    if not sys.argv[1:] or sys.argv[1] in ("--help", "-h"):
        print("usage: epdb.py scriptfile [arg] ...")
        sys.exit(2)

    mainpyfile =  sys.argv[1]     # Get script filename
    if not os.path.exists(mainpyfile):
        print('Error:', mainpyfile, 'does not exist')
        sys.exit(1)

    del sys.argv[0]         # Hide "pdb.py" from argument list

    # Replace pdb's dir with script's dir in front of module search path.
    sys.path[0] = os.path.dirname(mainpyfile)

    # Note on saving/restoring sys.argv: it's a good idea when sys.argv was
    # modified by the script being debugged. It's a bad idea when it was
    # changed by the user from the command line. There is a "restart" command
    # which allows explicit specification of command line arguments.
    epdb = Epdb()
    while 1:
        try:
            #epdb.ic = 0
            dbg.ic = 0
            epdb._runscript(mainpyfile)
            if epdb._user_requested_quit:
                break
            #print("The program finished and will be restarted")
            print("The program has finished", dbg.ic)
            raise EpdbPostMortem()
            #epdb.interaction(None, None)
        except pdb.Restart:
            print("Restarting", mainpyfile, "with arguments:")
            print("\t" + " ".join(sys.argv[1:]))
            # Deactivating automatic restart temporarily TODO
            break
        except SystemExit:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = sys.exc_info()[2]
            epdb.interaction(None, t)
        except EpdbExit:
            debug('EpdbExit caught')
            break
            # sys.exit(0)
        except bdb.BdbQuit:
            debug('BdbQuit caught - Shutting servers down')
            break
        except snapshotting.ControllerExit:
            debug('ControllerExit caught')
            break
        except snapshotting.SnapshotExit:
            debug('SnapshotExit caught')
            break
        except EpdbPostMortem:
            t = sys.exc_info()[2]
            epdb.mp.quit()
            break
        except:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = sys.exc_info()[2]
            epdb.interaction(None, t)
    
            #print("Post mortem debugger finished. The " + mainpyfile +
            #      " will be restarted")

# When invoked as main program, invoke the debugger on a script
if __name__ == '__main__':
    import epdb
    epdb.main()
