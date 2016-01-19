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

def _getpath(*args):
    path = [os.path.dirname(__file__)] + list(args)
    return os.path.join(*path)

class FBFrontDeskFrame(wx.Frame):

    __COPYRIGHT = '(c) 2015, 2016 Fraunhofer IISB'

    def PreCreate(self, pre):
        pass

    def __init__(self, parent):
        self.parent = parent

        self.path = None

        self.dest = None
        self.archive = None
        self.existing = None

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

        #self.Bind(wx.EVT_MENU, self.onProjectSelect, id=xrc.XRCID("folder_tb"))
        #self.Bind(wx.EVT_MENU, self.onOpenDocumentation, id=xrc.XRCID("help_tb"))

        xrc.XRCCTRL(self, 'project_radio').Bind(wx.EVT_RADIOBOX,
                self.onProjectRadio)
        self.nb = xrc.XRCCTRL(self, 'main_nb')
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self.onPageChanging)

        xrc.XRCCTRL(self, 'archive_fp').Bind(wx.EVT_FILEPICKER_CHANGED, self.onArchiveSelected)
        xrc.XRCCTRL(self, 'dest_dp').Bind(wx.EVT_DIRPICKER_CHANGED, self.onDestinationSelected)
        xrc.XRCCTRL(self, 'existing_dp').Bind(wx.EVT_DIRPICKER_CHANGED, self.onExistingSelected)


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

        #self.detect(self.path)
        #self.selectProject(self.path)

    def onInstall(self, evt):
        # FIXME bad hack
        self.nb.root = self.path
        wx.CallAfter(self.pages['config'].clear)
        wx.CallAfter(self.pages['config'].collect)
        self.status['initialized'] = True

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


class FBFrontDeskApp(wx.App):

    def OnInit(self):
        frame = FBFrontDeskFrame(None)
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
