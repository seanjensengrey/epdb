epdb allows you to debug backwards, meaning that you can step back.

# Screenshot #
![http://wiki.epdb.googlecode.com/hg/gepdb.png](http://wiki.epdb.googlecode.com/hg/gepdb.png)

# Requirements #
I used an Ubuntu 11.04 to develop epdb. Linux or Unix-like OS is mandatory for epdb, because it uses the system call fork(), which is not available on windows. You need a python3.1 or later for epdb and a python2.x for gepdb. For gepdb you also need pygtk, twisted and argparse.

I haven't tried it on many platforms yet. So let me know if you get it run on a different platform on the mailing list.

# Mailing List #

The project is in an early state and therefore we are (I am) happy for every kind of feedback, even if it is as simple as I got it run or it doesn't work for me. So don't hesitate to write a message to the mailing list.

http://groups.google.at/group/epdb

# Roadmap #

There is no release yet. The release of epdb is almost finished.
I will provide a roadmap here for version 0.1, 0.2 and
what could be expected from the first stable release (1.0).

## 0.1 ##

The first releas candidate for epdb and gepdb is out. You can download the egg files
in the download section. Use easy\_install and easy\_install3 to install it.

  * ~~Tracing should trace with better performance.~~
  * debian package for epdb and gepdb
  * ~~reversible debugging support for random, time and a basic one for files~~
  * ~~all 6 demos should be tested and should work~~
  * ~~breakpoints should work reliable~~
  * ~~create an egg file to easily install epdb and gepdb~~

## 0.2 ##

  * Reversible debugging support for couchdb-python
  * Debugging multiple programs at the same time with the gui

## 1.0 ##

  * fully pdb compatibile
  * watchpoints
  * support for reversible debugging for most modules of Python Standard library
  * support for reversible debugging for some external libraries
  * coverage analysis
  * injecting of instructions into a timeline
  * turn on/off revervisble mode
  * debugging multiple programs in the user interface.
  * The user interface should support basic editing of files.
  * A user interface for the browser to debug web applications
  * User documentation
  * incremental resource management
  * Extension documentation
  * Interruption of a running program
  * unittest integration

# Download the source #
Use mercurial to get the trunk. There are two project you here and you might want to install both.

hg clone https://epdb.googlecode.com/hg/ epdb

hg clone https://gui.epdb.googlecode.com/hg/ epdb-gui

# Installation from source #
Go into the epdb directory. Run

sudo python3 setup.py install

Then, in the epdb-gui directory run

sudo python setup.py install