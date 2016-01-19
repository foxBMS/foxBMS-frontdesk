"""
:since:     Tue Jan 19 11:13:52 CET 2016
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
$Id$
"""



import wx
from wx import xrc
from wx import aui
import wx.aui
import os
import sys

import configure
import threading
import glob
import subprocess
import select
import re

class RunThread(threading.Thread):

    def __init__(self, parent, cmd, fulloutput = True):
        self.parent = parent
        threading.Thread.__init__(self)
        self.canceling = False
        self.cmd = cmd
        self.fulloutput = fulloutput

    def run(self):
        if self.fulloutput:
            self.runFull()
        else:
            self.runSilent()

    def runFull(self):
        wx.CallAfter(self.parent.enableWidgets, False)
        p = subprocess.Popen(self.cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

        while True:

            if self.canceling:
                p.stdout.close()
                p.stderr.close()
                break

            reads = [p.stdout.fileno(), p.stderr.fileno()]
            ret = select.select(reads, [], [])

            for fd in ret[0]:

                if fd == p.stdout.fileno():
                    read = p.stdout.readline()
                    wx.CallAfter(self.parent.writeLog, read)

                if fd == p.stderr.fileno():
                    read = p.stderr.readline()
                    wx.CallAfter(self.parent.writeLog, read)

            if p.poll() != None:
                break

        wx.CallAfter(self.parent.writeLog, '__all_done__')
        wx.CallAfter(self.parent.enableWidgets, True)

    def runSilent(self):
        wx.CallAfter(self.parent.enableWidgets, False)
        p = subprocess.Popen(self.cmd, stderr=subprocess.PIPE)

        while True:

            if self.canceling:
                p.stder.close()
                break

            r = p.stderr.readline()
            wx.CallAfter(self.parent.writeLog, r)

            if p.poll() != None:
                break

        wx.CallAfter(self.parent.writeLog, '__all_done__')
        wx.CallAfter(self.parent.enableWidgets, True)


def _getpath(*args):
    path = [os.path.dirname(__file__)] + list(args)
    return os.path.join(*path)

class FBFrontDeskFrame(wx.Frame):

    __COPYRIGHT = '(c) 2015, 2016 Fraunhofer IISB'
    PROGRESS_RE = re.compile('\[\s*(\d+)/(\d+)\] .*')

    def PreCreate(self, pre):
        pass

    def __init__(self, parent, path = None):
        print path
        self.parent = parent

        self.path = None

        self.dest = None
        self.archive = None
        self.existing = path

        self._tasks = 1

        self.status = {
                'initialized': False,
                'configured': False,
                'built': False,
                'flashed': False}

        self._resources = xrc.EmptyXmlResource()
        self._resources.Load(_getpath('xrc', 'foxfdd.xrc'))

        pre = wx.PreFrame()
        self._resources.LoadOnFrame(pre, parent, "frontdesk_mframe")
        self.PostCreate(pre)

        if not path is None:
            xrc.XRCCTRL(self, 'project_radio').SetSelection(1)
            xrc.XRCCTRL(self, 'existing_dp').SetPath(os.path.abspath(path))


        #self.Bind(wx.EVT_MENU, self.onProjectSelect, id=xrc.XRCID("folder_tb"))
        #self.Bind(wx.EVT_MENU, self.onOpenDocumentation, id=xrc.XRCID("help_tb"))

        xrc.XRCCTRL(self, 'project_radio').Bind(wx.EVT_RADIOBOX,
                self.onProjectRadio)
        self.nb = xrc.XRCCTRL(self, 'main_nb')
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self.onPageChanging)

        xrc.XRCCTRL(self, 'archive_fp').Bind(wx.EVT_FILEPICKER_CHANGED, self.onArchiveSelected)
        xrc.XRCCTRL(self, 'dest_dp').Bind(wx.EVT_DIRPICKER_CHANGED, self.onDestinationSelected)
        xrc.XRCCTRL(self, 'existing_dp').Bind(wx.EVT_DIRPICKER_CHANGED, self.onExistingSelected)

        xrc.XRCCTRL(self, 'clear_b').Bind(wx.EVT_BUTTON, self.onClear)
        #xrc.XRCCTRL(self, 'details_tc').SetMinSize((-1, 150))
        #xrc.XRCCTRL(self, 'commands_box').SetMinSize((200, 200))
        xrc.XRCCTRL(self, 'progress').SetSize((-1, 3))
        xrc.XRCCTRL(self, 'progress').SetMaxSize((-1, 3))

        self.pages = {}
        self.pagekeys = ['install', 'configure', 'build', 'flash']
        for k in ['install', 'build', 'flash']:
            self.pages[k] = xrc.XRCCTRL(self, k + '_page')
        self.pages['config'] = configure.FBConfigurePanel(self.nb)
        self.nb.InsertPage(1, self.pages['config'], 'Configuration')

        for k in ['config', 'build', 'flash']:
            self.pages[k].Enable(False)

        self.onProjectRadio(None)
        #self.panel = FBFrontDeskPanel(self)
        self.SetMinSize((800, 700))
        self.Fit()

        xrc.XRCCTRL(self, 'install_b').Bind(wx.EVT_BUTTON, self.onInstall)
        xrc.XRCCTRL(self, 'build_b').Bind(wx.EVT_BUTTON, self.onBuild)

        self.detect(self.path)
        #self.selectProject(self.path)

    def onInstall(self, evt):
        # FIXME bad hack
        self.nb.root = self.path
        wx.CallAfter(self.pages['config'].clear)
        wx.CallAfter(self.pages['config'].collect)
        self.status['initialized'] = True
        self.detect(self.path)
        self._tasks = 4
        self.runWaf('configure', 'doxygen', 'sphinx')

    def onBuild(self, evt):
        self._tasks = 1
        self.runWaf('build')

    def onPageChanging(self, evt):
        _old = self.nb.GetSelection() 
        _new = evt.GetSelection()
        if not self.status['initialized']:
            evt.Veto()
        elif not self.status['initialized'] and _new >= self.pagekeys.index('build'): 
            evt.Veto()
        elif not self.status['built'] and _new >= self.pagekeys.index('flash'): 
            evt.Veto()


    def onArchiveSelected(self, evt):
        self.archive = xrc.XRCCTRL(self, 'archive_dp').GetPath()
        self.onProjectRadio(None)
    
    def onDestinationSelected(self, evt):
        self.dest = xrc.XRCCTRL(self, 'dest_dp').GetPath()
        self.onProjectRadio(None)

    def onExistingSelected(self, evt):
        self.existing = xrc.XRCCTRL(self, 'existing_dp').GetPath()
        self.onProjectRadio(None)

    def onProjectRadio(self, evt):
        if xrc.XRCCTRL(self, 'project_radio').GetSelection() == 0:
            xrc.XRCCTRL(self, 'existing_dp').GetTextCtrl().Enable(False)
            xrc.XRCCTRL(self, 'existing_dp').GetPickerCtrl().Enable(False)
            xrc.XRCCTRL(self, 'existing_st').Enable(False)

            xrc.XRCCTRL(self, 'archive_fp').GetTextCtrl().Enable(True)
            xrc.XRCCTRL(self, 'archive_fp').GetPickerCtrl().Enable(True)
            xrc.XRCCTRL(self, 'archive_st').Enable(True)

            xrc.XRCCTRL(self, 'dest_dp').GetTextCtrl().Enable(True)
            xrc.XRCCTRL(self, 'dest_dp').GetPickerCtrl().Enable(True)
            xrc.XRCCTRL(self, 'dest_st').Enable(True)

            if not self.dest is None and os.path.isdir(self.dest) \
                    and not self.archive is None and os.path.isfile(self.archive):
                self.path = self.dest
                xrc.XRCCTRL(self, 'install_b').Enable(True)
            else:
                self.path = None
                xrc.XRCCTRL(self, 'install_b').Enable(False)

        else:
            xrc.XRCCTRL(self, 'existing_dp').GetTextCtrl().Enable(True)
            xrc.XRCCTRL(self, 'existing_dp').GetPickerCtrl().Enable(True)
            xrc.XRCCTRL(self, 'existing_st').Enable(True)

            xrc.XRCCTRL(self, 'archive_fp').GetTextCtrl().Enable(False)
            xrc.XRCCTRL(self, 'archive_fp').GetPickerCtrl().Enable(False)
            xrc.XRCCTRL(self, 'archive_st').Enable(False)

            xrc.XRCCTRL(self, 'dest_dp').GetTextCtrl().Enable(False)
            xrc.XRCCTRL(self, 'dest_dp').GetPickerCtrl().Enable(False)
            xrc.XRCCTRL(self, 'dest_st').Enable(False)

            if not self.existing is None and os.path.isdir(self.existing):
                self.path = self.existing
                xrc.XRCCTRL(self, 'install_b').Enable(True)
            else:
                self.path = None
                xrc.XRCCTRL(self, 'install_b').Enable(False)

    def detect(self, path):
        if path is None:
            path = '.'
        path = os.path.abspath(path)
        if not os.path.isfile(os.path.join(path, 'wscript')):
            self.path = None
            self._waf = None
            return
        _wafs = glob.glob(os.path.join(path, 'tools/waf-*'))
        if len(_wafs) < 1:
            self.path = None
            self._waf = None
            return
        self._waf = _wafs[-1]
        self.path = path

        if os.path.isfile(os.path.join(self.path, 'build', 'foxbmsconfig.h')):
            self.status['initialized'] = True


    def onOpenDocumentation(self, evt):
        _path = os.path.abspath('build/doc/sphinx/html/index.html')
        webbrowser.open('file://' + _path)


    def runWaf(self, *args):
        xrc.XRCCTRL(self, 'details_tc').Clear()
        _fo = True
        if len(args) < 1: 
            return
        _CMD = [sys.executable, self._waf]
        _fo = True
        _CMD += args
        rt = RunThread(self, _CMD, fulloutput = _fo)
        rt.start()

    def onClear(self, evt):
        xrc.XRCCTRL(self, 'details_tc').Clear()

    def writeLog(self, msg):
        if msg == '__all_done__':
            self.setProgress(1, 1)
            return

        g = self.PROGRESS_RE.match(msg)
        if g:
            self.setProgress(int(g.group(1)) - 1, int(g.group(2)))

        _ds = xrc.XRCCTRL(self, 'details_tc').GetDefaultStyle()
        _c = _ds.GetTextColour()

        if 'error:' in msg:
            _ds.SetTextColour(wx.Colour(240, 0, 0))
            xrc.XRCCTRL(self, 'details_tc').SetDefaultStyle(_ds)
        elif 'warning:' in msg:
            _ds.SetTextColour(wx.Colour(120, 120, 0))
            xrc.XRCCTRL(self, 'details_tc').SetDefaultStyle(_ds)
        elif 'finished successfully' in msg:
            _ds.SetTextColour(wx.Colour(0, 160, 0))
            xrc.XRCCTRL(self, 'details_tc').SetDefaultStyle(_ds)
        else:
            _ds.SetTextColour(wx.Colour(0, 0, 0))
            xrc.XRCCTRL(self, 'details_tc').SetDefaultStyle(_ds)

        xrc.XRCCTRL(self, 'details_tc').AppendText(msg)
        _ds.SetTextColour(_c)

    def setProgress(self, prog, ran):
        print prog, ran
        xrc.XRCCTRL(self, 'progress').SetRange(ran) 
        xrc.XRCCTRL(self, 'progress').SetValue(prog)

    def enableWidgets(self, enable = True):
        self.pages[self.pagekeys[self.nb.GetSelection()]].Enable(enable)
        self.nb.Enable(enable)

class FBFrontDeskApp(wx.App):

    def OnInit(self):
        _path = None
        try:
            _path = sys.argv[1]
        except:
            pass
        frame = FBFrontDeskFrame(None, path = _path)
        self.SetTopWindow(frame)
        frame.Show()
        return True

    def OnExit(self):
        wx.App.OnExit(self)

def main():
    app = FBFrontDeskApp(False)
    app.MainLoop()


if __name__ == '__main__':
    main()


