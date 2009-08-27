# -*- coding: utf-8 -*-

# HDTV - A ROOT-based spectrum analysis software
#  Copyright (C) 2006-2009  The HDTV development team (see file AUTHORS)
#
# This file is part of HDTV.
#
# HDTV is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# HDTV is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with HDTV; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

import ROOT
import os
import glob

import hdtv.cmdline
import hdtv.cmdhelper
import hdtv.color
import hdtv.cal
import hdtv.util
import hdtv.ui
 
from hdtv.spectrum import Spectrum, FileSpectrum, SpectrumCompound
from hdtv.specreader import SpecReaderError
from copy import copy

# Don't add created spectra to the ROOT directory
ROOT.TH1.AddDirectory(ROOT.kFALSE)

class SpecInterface:
    """
    User interface to work with 1-d spectra
    """
    def __init__(self, window, spectra):
        print "Loaded user interface for working with 1-d spectra"
    
        self.window = window
        self.spectra= spectra
        self.caldict = dict()
        
        # tv commands
        self.tv = TvSpecInterface(self)
        
        # good to have as well...
        self.window.AddHotkey(ROOT.kKey_PageUp, self._HotkeyShowPrev)
        self.window.AddHotkey(ROOT.kKey_PageDown, self._HotkeyShowNext)
        
        # register common tv hotkeys
        self.window.AddHotkey([ROOT.kKey_N, ROOT.kKey_p], self._HotkeyShowPrev)
        self.window.AddHotkey([ROOT.kKey_N, ROOT.kKey_n], self._HotkeyShowNext)
        self.window.AddHotkey(ROOT.kKey_Equal, self.spectra.RefreshAll)
        self.window.AddHotkey(ROOT.kKey_t, self.spectra.RefreshVisible)
        self.window.AddHotkey(ROOT.kKey_n,
                lambda: self.window.EnterEditMode(prompt="Show spectrum: ",
                                           handler=self._HotkeyShow))
        self.window.AddHotkey(ROOT.kKey_a,
                lambda: self.window.EnterEditMode(prompt="Activate spectrum: ",
                                           handler=self._HotkeyActivate))
    
    def _HotkeyShow(self, arg):
        """ 
        ShowObjects wrapper for use with Hotkey
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(arg, self.spectra)
            if len(ids) == 0:
                self.spectra.HideAll()
            else:
                self.spectra.ShowObjects(ids)
                activateID = min(ids)
                self.spectra.ActivateObject(activateID)
        except ValueError:
            self.window.viewport.SetStatusText("Invalid spectrum identifier: %s" % arg)

        
    def _HotkeyActivate(self, arg):
        """
        ActivateObject wrapper for use with Hotkey
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(arg, self.spectra)
            if len(ids) > 1:
                self.window.viewport.SetStatusText("Cannot activate more than one spectrum")
            elif len(ids) == 0: # Deactivate
                oldactive = self.spectra.activeID
                self.spectra.ActivateObject(None)
                self.window.viewport.SetStatusText("Deactivated spectrum %d" % oldactive)
            else:
                ID = ids[0]
                self.spectra.ActivateObject(ID)
                self.window.viewport.SetStatusText("Activated spectrum %d" % self.spectra.activeID)
        except ValueError:
            self.window.viewport.SetStatusText("Invalid id: %s" % arg)
        except KeyError:
            self.window.viewport.SetStatusText("No such id: %d" % ID)

    def _HotkeyShowNext(self):
        """
        Show next spectrum and activate it automatically
        """
        nextID = self.spectra.nextID
        self.spectra.ShowObjects(nextID)
        self.spectra.ActivateObject(nextID)

    def _HotkeyShowPrev(self):
        """
        Show previous spectrum and activate it automatically
        """
        prevID = self.spectra.prevID
        self.spectra.ShowObjects(prevID)
        self.spectra.ActivateObject(prevID)


    def LoadSpectra(self, patterns, ID=None):
        """
        Load spectra from files matching patterns.
        
        If ID is specified, the spectrum is stored with id ID, possibly
        replacing a spectrum that was there before.
        """
        # Avoid multiple updates
        self.window.viewport.LockUpdate()
        # only one filename is given
        if type(patterns) == str or type(patterns) == unicode:
            patterns = [patterns]

        if ID != None and len(patterns) > 1:
            print "Error: if you specify an ID, you can only give one pattern"
            self.window.viewport.UnlockUpdate()
            return
        
        loaded = [] 
        for p in patterns:
            # put fmt if available
            p = p.rsplit("'", 1)
            if len(p) == 1 or not p[1]:
                (fpat, fmt) = (p[0], None)
            else:
                (fpat, fmt) = p

            files = glob.glob(os.path.expanduser(fpat))
            
            if len(files) == 0:
                print "Warning: %s: no such file" % fpat
            elif ID != None and len(files) > 1:
                print "Error: pattern %s is ambiguous and you specified an ID" % fpat
                break
                
            files.sort()
            
            for fname in files:
                try:
                    fspec = FileSpectrum(fname, fmt)
                    # Create spectrum compund
                    spec = SpectrumCompound(self.spectra.viewport, fspec)
                except (OSError, SpecReaderError):
                    print "Warning: could not load %s'%s" % (fname, fmt)
                else:
                    if ID == None:
                        sid = self.spectra.Add(spec)
                    else:
                        sid = self.spectra.Insert(spec, ID)
                    
                    spec.SetColor(hdtv.color.ColorForID(sid))
                    loaded.append(sid)
                    
                    if fmt == None:
                        print "Loaded %s into %d" % (fname, sid)
                    else:
                        print "Loaded %s'%s into %d" % (fname, fmt, sid)
        
        if len(loaded)>0:
            self.spectra.ActivateObject(loaded[-1])
        # Update viewport if required
        if len(self.spectra.objects) == 1: # Expand window if it is the only spectrum
            self.window.Expand()
        self.window.viewport.UnlockUpdate()
        return loaded


    def FindSpectrumByName(self, name):
        """
        Find the spectrum object whose ROOT histogram has the given name.
        If there are several such objects, one of them (in undefined ordering)
        is returned. If there is none, None is returned.
        """
        for obj in self.spectra.objects.itervalues():
            if obj.name == name:
                return obj
        return None
            
    def CopySpectrum(self, ID, copyTo=None):
        """
        Copy spectrum
        
        Return ID of new spectrum
        """
        
        if copyTo is None:              
            copyTo = self.spectra.GetFreeID()

        hdtv.ui.debug("Copy spec " + str(ID) + " to " + str(copyTo), level=2)
        hist = copy(self.spectra[ID].fHist)

        spec = Spectrum(hist, cal=self.spectra[ID].cal)
        spec = SpectrumCompound(self.spectra[ID].viewport, spec)        
        sid = self.spectra.Insert(spec, copyTo)
        spec.SetColor(hdtv.color.ColorForID(sid))
        print "Copied spectrum", ID, "to", sid
            
    
    def GetCalsFromList(self, fname):
        """
        Reads calibrations from a calibration list file. The file has the format
        <specname>: <cal0> <cal1> ...
        The calibrations are written into the calibration dictionary.
        """
        fname = os.path.expanduser(fname)
        try:
            f = open(fname, "r")
        except IOError, msg:
            print "Error opening file: %s" % msg
            return False
        linenum = 0
        for l in f:
            linenum += 1
            # Remove comments and whitespace; ignore empty lines
            l = l.split('#', 1)[0].strip()
            if l == "":
                continue
            try:
                (k, v) = l.split(':', 1)
                name = k.strip()
                coeff = [ float(s) for s in v.split() ]
                self.caldict[name] = coeff
            except ValueError:
                print "Warning: could not parse line %d of file %s: ignored." % (linenum, fname)
            else:
                spec = self.FindSpectrumByName(name)
                if not spec is None:
                    spec.SetCal(self.caldict[name])
        f.close()
        return True
    
    def ApplyCalibration(self, cal, ids):
        """
        Apply calibration cal to spectra with ids
        """
        for ID in ids:
            try:
                self.spectra[ID].SetCal(cal)
                print "calibrated spectrum with id %d" %ID
            except KeyError:
                print "Warning: there is no spectrum with id: %s" %ID
#        self.window.Expand()

class TvSpecInterface:
    """
    TV style commands for the spectrum interface.
    """
    def __init__(self, specInterface):
        self.specIf = specInterface
        self.spectra = self.specIf.spectra
        
        # register tv commands
        hdtv.cmdline.command_tree.SetDefaultLevel(1)
        
        
        # spectrum commands
        parser = hdtv.cmdline.HDTVOptionParser(prog="spectrum get",
                     usage="%prog [OPTIONS] <pattern> [<pattern> ...]")
        parser.add_option("-i", "--id", action="store",
                          default=None, help="id for loaded spectrum")
        hdtv.cmdline.AddCommand("spectrum get", self.SpectrumGet, level=0, minargs=1,
                                fileargs=True, parser=parser)
        
        parser = hdtv.cmdline.HDTVOptionParser(prog="spectrum list", usage="%prog [OPTIONS]")
        parser.add_option("-v", "--visible", action="store_true",
                          default=False, help="list only visible (and active) spectra")
        hdtv.cmdline.AddCommand("spectrum list", self.SpectrumList, nargs=0, parser=parser)
        
        hdtv.cmdline.AddCommand("spectrum delete", self.SpectrumDelete, minargs=0,
                                usage="%prog <ids>", level = 0)
        hdtv.cmdline.AddCommand("spectrum activate", self.SpectrumActivate, nargs=1,
                                usage="%prog <id>", level = 0)
        hdtv.cmdline.AddCommand("spectrum show", self.SpectrumShow, minargs=0,
                                usage="%prog <ids>|all|none|...", level = 0)
        hdtv.cmdline.AddCommand("spectrum hide", self.SpectrumHide, minargs=0,
                                usage="%prog <ids>|all|none|...", level = 2)
        hdtv.cmdline.AddCommand("spectrum info", self.SpectrumInfo, minargs=0,
                                usage="%prog [ids]", level=0)
        hdtv.cmdline.AddCommand("spectrum update", self.SpectrumUpdate, minargs=0,
                                usage="%prog <ids>|all|shown", level = 0)
        hdtv.cmdline.AddCommand("spectrum write", self.SpectrumWrite, minargs=1, maxargs=2,
                                usage="%prog <filename>'<format> [id]", level = 0)
        hdtv.cmdline.AddCommand("spectrum normalization", self.SpectrumNormalization,
                                minargs=1, level = 0,
                                usage="%prog [ids] <norm>")


        prog = "spectrum add"
        parser = hdtv.cmdline.HDTVOptionParser(prog=prog,
                                               usage="%prog [OPTIONS] <target-id> <ids>|all")
        parser.add_option("-n", "--normalize", action="store_true", 
                          help="normalize <target-id> by dividing through number of added spectra afterwards")
        hdtv.cmdline.AddCommand(prog, self.SpectrumAdd, level = 2, minargs=1, fileargs=False, parser=parser)

        prog = "spectrum substract"
        parser = hdtv.cmdline.HDTVOptionParser(prog=prog,
                                               usage="%prog [OPTIONS] <target-id> <ids>|all")
        hdtv.cmdline.AddCommand(prog, self.SpectrumSub, level = 2, minargs=1, fileargs=False, parser=parser)
        
        prog = "spectrum multiply"
        parser = hdtv.cmdline.HDTVOptionParser(prog=prog,
                                               usage="%prog [OPTIONS]  [ids]|all|... <factor>")
        hdtv.cmdline.AddCommand(prog, self.SpectrumMultiply, level = 2, minargs=1, fileargs=False, parser=parser)
        
        
        prog = "spectrum copy"
        parser = hdtv.cmdline.HDTVOptionParser(prog=prog,
                                               usage="%prog <ids>")
        parser.add_option("-i", "--id", action="store", default=None, help="Copy to <ids>")
        hdtv.cmdline.AddCommand(prog, self.SpectrumCopy, level = 2, fileargs=False, parser=parser)
        

        prog = "spectrum name"
        parser = hdtv.cmdline.HDTVOptionParser(prog=prog, usage="%prog <name>")
        hdtv.cmdline.AddCommand(prog, self.SpectrumName, level = 2, fileargs = False, parser=parser)

        # calibration commands
        parser = hdtv.cmdline.HDTVOptionParser(prog="calibration position read",
                                               usage="%prog [OPTIONS] <filename>")
        parser.add_option("-s", "--spec", action="store",
                          default="all", help="spectrum ids to apply calibration to")
        hdtv.cmdline.AddCommand("calibration position read", self.CalPosRead, level = 0, nargs=1,
                                fileargs=True, parser=parser)
        
        
        parser = hdtv.cmdline.HDTVOptionParser(prog="calibration position enter",
                     description=
"""Fit a calibration polynomial to the energy/channel pairs given.
Hint: specifying degree=0 will fix the linear term at 1. Specify spec=None
to only fit the calibration.""",
                     usage="%prog [OPTIONS] <ch0> <E0> [<ch1> <E1> ...]")
        parser.add_option("-s", "--spec", action="store",
                          default="all", help="spectrum ids to apply calibration to")
        parser.add_option("-d", "--degree", action="store",
                          default="1", help="degree of calibration polynomial fitted [default: %default]")
        parser.add_option("-D", "--draw-fit", action="store_true",
                          default=False, help="draw fit used to obtain calibration")
        parser.add_option("-r", "--draw-residual", action="store_true",
                          default=False, help="show residual of calibration fit")
        parser.add_option("-t", "--show-table", action="store_true",
                          default=False, help="print table of energies given and energies obtained from fit")
        parser.add_option("-f", "--file", action="store", 
                          default = None, help="get channel<->energy pairs from file")
        hdtv.cmdline.AddCommand("calibration position enter", self.CalPosEnter, level = 0,
                                minargs=0, parser=parser, fileargs=True)
        
        parser = hdtv.cmdline.HDTVOptionParser(prog="calibration position set",
                                               usage="%prog [OPTIONS] <p0> <p1> [<p2> ...]")
        parser.add_option("-s", "--spec", action="store",
                          default="all", help="spectrum ids to apply calibration to")
        hdtv.cmdline.AddCommand("calibration position set", self.CalPosSet, level = 0,
                                minargs=2, parser=parser)
        
        
        hdtv.cmdline.AddCommand("calibration position getlist", self.CalPosGetlist, nargs=1,
                                fileargs=True,
                                usage="%prog <filename>", level=0)

    
    def SpectrumList(self, args, options):
        """
        Print a list of all spectra 
        """
        self.spectra.ListObjects(options.visible)
    

    def SpectrumGet(self, args, options):
        """
        Load Spectra from files
        """
        if options.id != None:
            ID = int(options.id)
        else:
            ID = None
        
        self.specIf.LoadSpectra(patterns = args, ID = ID)


    def SpectrumDelete(self, args):
        """ 
        Deletes spectra 
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(args, self.spectra)
        except ValueError:
            return "USAGE"
                    
        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return
        self.spectra.RemoveObjects(ids)

        

    def SpectrumActivate(self, args):
        """
        Activate one spectra
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(args, self.spectra)
        except ValueError:
            return "USAGE"

        if len(ids) > 1:
            hdtv.ui.error("Can only activate one spectrum")
        elif len(ids) == 0:
            self.spectra.ActivateObject(None)
        else:
            self.spectra.ActivateObject(min(ids))


    def SpectrumCopy(self, args, options):
        """
        Copy spectra
        """
        hdtv.ui.debug("SpectrumCopy: args= " + str(args) + " options= " + str(options), level=6)
        try:
            ids = hdtv.cmdhelper.ParseIds(args, self.spectra)
            
            if len(ids) == 0:
                hdtv.ui.warn("Nothing to do")
                return
        except ValueError:
            return "USAGE"
            
        targetids = list()
        if options.id is not None:
            targetids = hdtv.cmdhelper.ParseIds(options.id, self.spectra, only_existent=False)
        if len(targetids) == 0:
            targetids = [None for i in range(0,len(ids))]
        elif len(targetids) == 1: # Only start ID is given
            startID = targetids[0]
            targetids = [i for i in range(startID, startID+len(ids))]
        elif len(targetids) != len(ids):
            hdtv.ui.error("Number of target ids does not match number of ids to copy")
            return
        
        # TODO: unfortunately ParseRange() in ParseIDs() uses unsorted sets
        ids.sort()
        targetids.sort()
        for i in range(0, len(ids)):
            try:                
                self.specIf.CopySpectrum(ids[i], copyTo=targetids[i])
            except KeyError:
                hdtv.ui.error("No such spectrum: " + str(ids[i]))
                
    
    def SpectrumAdd(self, args, options):
        """
        Add spectra (spec1 + spec2, ...)
        """
        try:
            addTo = int(args[0])
            try:
                ids = hdtv.cmdhelper.ParseIds(args[1:], self.spectra)
            except KeyError:
                hdtv.ui.msg("Adding active spectrum %d" % self.spectra.activeID)
                ids = [self.spectra.activeID]
        except ValueError:
            return "USAGE"
            
        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return

        norm_fac = len(ids)

        if not addTo in self.spectra.keys():
            sid = self.specIf.CopySpectrum(ids.pop(), addTo)
        
        for i in ids:
            try:
                hdtv.ui.msg("Adding " + str(i) + " to " + str(addTo))
                self.spectra[addTo].Plus(self.spectra[i])
            except KeyError:
                hdtv.ui.error("Could not add " + str(i))
                
        if options.normalize:
            hdtv.ui.msg("Normalizing spectrum %d by 1/%d" % (addTo, norm_fac))
            self.spectra[addTo].Multiply(1./norm_fac)


    def SpectrumSub(self, args, options):
        """
        Substract spectra (spec1 - spec2, ...)
        """   
        subFrom = int(args[0])
        try:
            ids = hdtv.cmdhelper.ParseIds(args[1:], self.spectra)
        except KeyError:
            ids = [self.spectra.activeID]
            hdtv.ui.msg("Substracting active spectrum %d" % self.spectra.activeID)
        except ValueError:
            return "USAGE"
            
        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return

        if not subFrom in self.spectra.keys():
            sid = self.specIf.CopySpectrum(ids.pop(), subFrom)
        
        for i in ids:
            try:
                hdtv.ui.msg("Substracting " + str(i) + " from " + str(subFrom))
                self.spectra[subFrom].Minus(self.spectra[i])
            except KeyError:
                hdtv.ui.error("Could not substract " + str(i))

    
    def SpectrumMultiply(self, args, options):
        """
        Multiply spectrum
        """
        try:
            factor = float(eval(args[-1]))
            
            if len(args) == 1:
                hdtv.ui.msg("Using active spectrum %d for multiplication" % self.spectra.activeID)
                ids = [self.spectra.activeID]
            else:
                ids = hdtv.cmdhelper.ParseIds(args[:-1], self.spectra)

        except (IndexError, ValueError):
            return "USAGE"
            
        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return

        for i in ids:
            if i in self.spectra.keys():
                hdtv.ui.msg("Multiplying " + str(i) + " with " + str(factor))
                self.spectra[i].Multiply(factor)
            else:
                hdtv.ui.error("Cannot multiply spectrum " + str(i) + " (Does not exist)")  
    
    def SpectrumHide(self, args):
        """
        Hides spectra
        """
        return self.SpectrumShow(args, inverse=True)
    
    def SpectrumShow(self, args, inverse=False):
        """
        Shows spectra
        
        When inverse == True SpectrumShow behaves like SpectrumHide
        """

        if len(args) == 0:
            ids = self.spectra.keys()
        else:
            try:
                ids = hdtv.cmdhelper.ParseIds(args, self.spectra)
            except ValueError:
                return "USAGE"

        if inverse:
            self.spectra.HideObjects(ids)
        else:
            self.spectra.ShowObjects(ids)

        try:
            ID = min(self.spectra.visible)
        except ValueError:
            ID = None
            
        self.spectra.ActivateObject(ID)
            
            
    def SpectrumInfo(self, args):
        """
        Print info on spectrum objects
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(args, self.spectra)
        except ValueError:
            return "USAGE"
        
        s = ""
        for ID in ids:
            try:
                spec = self.spectra[ID]
            except KeyError:
                s += "Spectrum %d: ID not found\n" % ID
                continue
            s += "Spectrum %d:\n" % ID
            s += hdtv.cmdhelper.Indent(spec.GetInfo(), "  ")
            s += hdtv.ui.linesep

        hdtv.ui.msg(s, newline=False)
	
            
    def SpectrumUpdate(self, args):
        """
        Refresh spectra
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(args, self.spectra)
        except ValueError:
            return "USAGE"

        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return
        self.spectra.Refresh(ids)

            
    def SpectrumWrite(self, args):
        """
        Write Spectrum to File
        """
        # TODO: should accept somthing like "spec write all" -> Utilize: hdtv.cmdhelper.ParseSpecIds
        try:
            (fname, fmt) = args[0].rsplit("'", 1)
            if len(args) == 1:
                ID = self.spectra.activeID
            elif len(args)==2:
                ID = int(args[1])
            else:
                print "There is just one index possible here."
                raise ValueError
            try:
                self.spectra[ID].WriteSpectrum(fname, fmt)
                print "wrote spectrum with id %d to file %s" %(ID, fname)
            except KeyError:
                 print "Warning: there is no spectrum with id: %s" %ID
        except ValueError:
            return "USAGE"
            
    def SpectrumName(self, args, options):
        """
        Give spectrum a name
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(args[0], self.spectra)
        except ValueError:
            return "USAGE"
        
        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return
        elif len(ids) > 1:
            hdtv.ui.warn("Can only rename one spectrum at a time")
            return
        
        ID = ids[0]
                    
        name = args[1]
        self.spectra[ID].spec.name = name
        hdtv.ui.msg("Renamed spectrum %d to \'%s\'" % (ID, name))
    
    def SpectrumNormalization(self, args):
        "Set normalization for spectrum"
        try:
            if len(args) == 1:
                ids = [ self.spectra.activeID ]
            else:
                ids = hdtv.cmdhelper.ParseIds(args[:-1], self.spectra)
                if len(ids) == 0:
                    hdtv.ui.warn("Nothing to do")
                    return

            norm = float(args[-1])
        except ValueError:
            return "USAGE"
            
        for ID in ids:
            try:
                self.spectra[ID].SetNorm(norm)
            except KeyError:
                hdtv.ui.error("There is no spectrum with id: %s" % ID)

    def CalPosRead(self, args, options):
        """
        Read calibration from file
        """
        try:
            ids = hdtv.cmdhelper.ParseIds(options.spec, self.spectra)
            fname = args[0]
        except (ValueError, IndexError):
            return "USAGE"
            
        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return
        
        # Load calibration
        cal = hdtv.cal.CalFromFile(fname)
        self.specIf.ApplyCalibration(cal, ids)        
        return True
            
        
    def CalPosEnter(self, args, options):
        """
        Create calibration from pairs of channel and energy
        """
        try:
            pairs = hdtv.util.Pairs(hdtv.util.ErrValue)
            if not options.file is None: # Read from file     
                pairs.fromFile(options.file)
            else:
                if len(args) % 2 != 0: # Read from command line
                    print "Error: number of parameters must be even"
                    return "USAGE"
                for p in range(0,len(args),2):
                    pairs.add(args[p], args[p+1])
            ids = hdtv.cmdhelper.ParseIds(options.spec, self.spectra)
            if len(ids) == 0:
                hdtv.ui.warn("Nothing to do")
                return
            degree = int(options.degree)
        except ValueError:
            return "USAGE"
        try:
            cal = hdtv.cal.CalFromPairs(pairs, degree, options.show_table, 
                                        options.draw_fit, options.draw_residual)
        except (ValueError, RuntimeError), msg:
            hdtv.ui.error(str(msg))
            return False
        else:
            self.specIf.ApplyCalibration(cal, ids)            
            return True


    def CalPosSet(self, args, options):
        """
        Create calibration from the coefficients p of a polynomial
        n is the degree of the polynomial
        """
        try:
            cal = [float(i) for i in args]
            ids = hdtv.cmdhelper.ParseIds(options.spec, self.spectra)
        except ValueError:
            return "USAGE"
        
        if len(ids) == 0:
            hdtv.ui.warn("Nothing to do")
            return
        
        self.specIf.ApplyCalibration(cal, ids)
        return True

        
    def CalPosGetlist(self, args):
        """
        Read calibrations for several spectra from file
        """
        self.specIf.GetCalsFromList(args[0])


# plugin initialisation
import __main__
if not hasattr(__main__,"window"):
    import hdtv.window
    __main__.window = hdtv.window.Window()
if not hasattr(__main__, "spectra"):
    import hdtv.drawable
    __main__.spectra = hdtv.drawable.DrawableCompound(__main__.window.viewport)
__main__.s = SpecInterface(__main__.window, __main__.spectra)

