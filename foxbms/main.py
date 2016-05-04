"""
foxBMS Software License

Copyright 2010-2016, Fraunhofer-Gesellschaft zur Foerderung 
                     der angewandten Forschung e.V.
All rights reserved.

BSD 3-Clause License

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  1.  Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.
  2.  Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
  3.  Neither the name of the copyright holder nor the names of its
      contributors may be used to endorse or promote products derived from
      this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

We kindly request you to use one or more of the following phrases to refer
to foxBMS in your hardware, software, documentation or advertising
materials:

"This product uses parts of foxBMS"
"This product includes parts of foxBMS"
"This product is derived from foxBMS"

If you use foxBMS in your products, we encourage you to contact us at:

CONTACT INFORMATION
Fraunhofer IISB ; Schottkystrasse 10 ; 91058 Erlangen, Germany
Dr.-Ing. Vincent LORENTZ
+49 9131-761-346
info@foxbms.org
www.foxbms.org

:since:     Tue Dec 01 12:21:09 CET 2015
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
"""

import wx
import wx.xrc as xrc
import os
import sys
import glob
import subprocess
import select
import threading
import re
import webbrowser


class RunThread(threading.Thread):

    def __init__(self, parent, cmd):
        self.parent = parent
        threading.Thread.__init__(self)
        self.canceling = False
        self.cmd = cmd

    def run(self):

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

        wx.CallAfter(self.parent.enableWidgets, True)


def _getpath(*args):
    path = [os.path.dirname(__file__)] + list(args)
    return os.path.join(*path)

class FBFrontDeskPanel(wx.Panel):

    _COMMANDS = ['configure', 'generate', 'build', 'build documentation', 'clean', 'flash']

    def PreCreate(self, pre):
        pass
    
    def __init__(self, parent):

        self.PROGRESS_RE = re.compile('\[\s*(\d+)/(\d+)\] .*')

        self.parent = parent
        self._resources = xrc.EmptyXmlResource()
        self._resources.Load(_getpath('xrc', 'fbfrontdesk.xrc'))

        pre = wx.PrePanel()
        self.PreCreate(pre)
        self._resources.LoadOnPanel(pre, parent, "container_panel")
        self.PostCreate(pre)

        
        xrc.XRCCTRL(self, 'commands_box').InsertItems(self._COMMANDS, 0)
        xrc.XRCCTRL(self, 'run_b').Bind(wx.EVT_BUTTON, self.onRun)
        xrc.XRCCTRL(self, 'details_tc').SetMinSize((-1, 150))
        xrc.XRCCTRL(self, 'commands_box').SetMinSize((200, 200))
        xrc.XRCCTRL(self, 'progress').SetSize((-1, 3))
        xrc.XRCCTRL(self, 'progress').SetMaxSize((-1, 3))

        self.selectProject(None)

    def onRun(self, evt):
        _sel = xrc.XRCCTRL(self, 'commands_box').GetSelections()
        if len(_sel) < 1: 
            return
        _CMD = [sys.executable, self.parent._waf]
        for i in _sel:
            cmd = xrc.XRCCTRL(self, 'commands_box').GetString(i)
            if cmd == 'build documentation':
                _CMD += ['doxygen', 'sphinx']
            else:
                _CMD += [cmd]
        rt = RunThread(self, _CMD)
        rt.start()

    def enableWidgets(self, enable = True):
        xrc.XRCCTRL(self, 'run_b').Enable(enable)
        xrc.XRCCTRL(self, 'commands_box').Enable(enable)

    def setProgress(self, prog, ran):
        xrc.XRCCTRL(self, 'progress').SetRange(ran) 
        xrc.XRCCTRL(self, 'progress').SetValue(prog)

    def selectProject(self, path):
        if not path:
            self.enableWidgets(False)
        else:
            self.enableWidgets(True)

    def writeLog(self, msg):
        g = self.PROGRESS_RE.match(msg)
        if g:
            self.setProgress(int(g.group(1)), int(g.group(2)))

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

class DemoTaskBarIcon(wx.TaskBarIcon):
     
    def __init__(self, frame):
        wx.TaskBarIcon.__init__(self)
        self.frame = frame
 
        # Set the image
        _icon = wx.Icon(_getpath('xrc', 'foxbms100px.png'))
        print _icon.IsOk()
        self.SetIcon(_icon)


class FBFrontDeskFrame(wx.Frame):

    __COPYRIGHT = '(c) 2015, Fraunhofer IISB'

    def PreCreate(self, pre):
        pass

    def __init__(self, parent):
        self.parent = parent
        self.path = None
        self._resources = xrc.EmptyXmlResource()
        self._resources.Load(_getpath('xrc', 'fbfdframe.xrc'))

        pre = wx.PreFrame()
        self._resources.LoadOnFrame(pre, parent, "fbfrontdesk_frame")
        self.PostCreate(pre)

        self.SetIcon(wx.Icon(_getpath('xrc', 'foxbms100px.png')))
        self.tbicon = DemoTaskBarIcon(self)
        print self.tbicon.IsOk()

        self.Bind(wx.EVT_MENU, self.onProjectSelect, id=xrc.XRCID("folder_tb"))
        self.Bind(wx.EVT_MENU, self.onOpenDocumentation, id=xrc.XRCID("help_tb"))


        self.panel = FBFrontDeskPanel(self)
        self.SetMinSize((800, 700))
        self.Fit()

        self.detect(self.path)
        self.selectProject(self.path)

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

    def onOpenDocumentation(self, evt):
        _path = os.path.abspath('build/doc/sphinx/html/index.html')
        print _path
        webbrowser.open('file://' + _path)

    def onProjectSelect(self, evt):
        _path = self.path
        if _path is None:
            _path = os.path.abspath('.')
        dd = wx.DirDialog(self, 'Select a project folder', _path)
        if dd.ShowModal() != wx.ID_OK:
            evt.Skip()
            return
        path = dd.GetPath()
        self.detect(path)
        self.selectProject(self.path)

    def setStatusText(self, txt = ''):
        xrc.XRCCTRL(self, 'statusbar').SetStatusText(txt)
        self.SetStatusText(self.__COPYRIGHT + '                                            ' + txt)

    def selectProject(self, path):
        if path is None:
            self.setStatusText('No project selected')
        else:
            self.setStatusText('project: ' + path)
        self.panel.selectProject(path)


class FBFrontDeskApp(wx.App):

    def OnExit(self):
        wx.App.OnExit(self)

def main():
    app = FBFrontDeskApp(False)
    frame = FBFrontDeskFrame(None)
    frame.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()


