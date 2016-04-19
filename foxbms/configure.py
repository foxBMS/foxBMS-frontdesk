"""
:since:     Tue Jan 19 11:13:40 CET 2016 
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
$Id$
"""

import wx
import wx.xrc as xrc
from wx import html
import os
import sys
import glob
import subprocess
import select
import threading
import re
import webbrowser
import wx.propgrid as wxpg
import logging

from docutils.core import publish_parts


import foxygen
import threading

def isFoxBMS(path):
    '''
    Educated guess if a path contains the foxBMS sources.
    '''
    if not os.path.isfile(os.path.join(path, 'wscript')):
        return False
    if not os.path.isfile(os.path.join(path, 'wscript')):
        return False

def isInitialized(path):
    '''
    Educated guess if configure and documentation generation have been
    performed.
    '''
    if not os.path.isfile(os.path.join(path, 'build', 'doc', 'doxygen',
        'html', 'index.html')):
        return False
    if not os.path.isfile(os.path.join(path, 'build', 'doc', 'sphinx', 'html', 'index.html')):
        return False
    if not os.path.isfile(os.path.join(path, 'build', 'foxbmsconfig.h')):
        return False
    return True

class FBIntProperty(wxpg.PyIntProperty):
    """

    """
    def __init__(self, label, name = wxpg.LABEL_AS_NAME, value=None,
            variables = None):
        self.variables = variables
        self.label = label
        wxpg.PyIntProperty.__init__(self, label, name, value)

    def ValidateValue(self, value, validationInfo):
        """ Let's limit the value to range -10000 and 10000.
        """
        # Just test this function to make sure validationInfo and
        # wxPGVFBFlags work properly.
        oldvfb__ = validationInfo.GetFailureBehavior()

        # Mark the cell if validaton failred
        validationInfo.SetFailureBehavior(wxpg.PG_VFB_MARK_CELL)

        if self.variables[self.label].validate(value):
            return (True, value)
        else:
            return False

class FBFloatProperty(wxpg.PyFloatProperty):
    """

    """
    def __init__(self, label, name = wxpg.LABEL_AS_NAME, value=None,
            variables = None):
        self.variables = variables
        self.label = label
        wxpg.PyFloatProperty.__init__(self, label, name, value)

    def ValidateValue(self, value, validationInfo):
        """ Let's limit the value to range -10000 and 10000.
        """
        # Just test this function to make sure validationInfo and
        # wxPGVFBFlags work properly.
        oldvfb__ = validationInfo.GetFailureBehavior()

        # Mark the cell if validaton failred
        validationInfo.SetFailureBehavior(wxpg.PG_VFB_MARK_CELL)

        if self.variables[self.label].validate(value):
            return (True, value)
        else:
            return False



class TestValidator(wx.Validator):

    def __init__(self):
        wx.Validator.__init__(self)

    def Clone(self):
        return TestValidator()

    def Validate(self,win):       
        return False

    def TransferToWindow(self):
        return True # Prevent wxDialog from complaining.

    def TransferFromWindow(self):
        return True # Prevent wxDialog from complaining.


class CollectThread(threading.Thread):

    def __init__(self, parent):
        self.parent = parent
        threading.Thread.__init__(self)

    def run(self):
        #progress bar
        wx.CallAfter(self.parent.update)



def _getpath(*args):
    path = [os.path.dirname(__file__)] + list(args)
    return os.path.join(*path)

class FBConfigurePanel(wx.Panel):

    def PreCreate(self, pre):
        pass
    
    def __init__(self, parent, init = False):

        self.parent = parent
        self.initialized = False

        self._resources = xrc.EmptyXmlResource()
        self._resources.Load(_getpath('xrc', 'configure.xrc'))

        pre = wx.PrePanel()
        self.PreCreate(pre)
        self._resources.LoadOnPanel(pre, parent, "configure_panel")
        self.PostCreate(pre)

        self.pg = wxpg.PropertyGridManager(self,
                style=wxpg.PG_SPLITTER_AUTO_CENTER | wxpg.PG_AUTO_SORT |
                wxpg.PG_TOOLBAR)

        self.pg_ctrl = self._resources.AttachUnknownControl("property_grid", self.pg, self)
        xrc.XRCCTRL(self, 'generate_b').Bind(wx.EVT_BUTTON, self.onGenerate)
        xrc.XRCCTRL(self, 'reset_b').Bind(wx.EVT_BUTTON, self.onReset)
        xrc.XRCCTRL(self, 'load_b').Bind(wx.EVT_BUTTON, self.onLoad)
        xrc.XRCCTRL(self, 'save_b').Bind(wx.EVT_BUTTON, self.onSave)

        if init: 
            wx.CallAfter(self.collect)
        
        #xrc.XRCCTRL(self, 'commands_box').InsertItems(self._COMMANDS, 0)
        #xrc.XRCCTRL(self, 'run_b').Bind(wx.EVT_BUTTON, self.onRun)
        #xrc.XRCCTRL(self, 'clear_b').Bind(wx.EVT_BUTTON, self.onClear)
        #xrc.XRCCTRL(self, 'details_tc').SetMinSize((-1, 150))
        #xrc.XRCCTRL(self, 'commands_box').SetMinSize((200, 200))
        #xrc.XRCCTRL(self, 'progress').SetSize((-1, 3))
        #xrc.XRCCTRL(self, 'progress').SetMaxSize((-1, 3))

        #self.selectProject(None)
        
    def update(self):

        # this is some dummy code to initialize the writer
        try:
            _helptxt = publish_parts('dummy', writer_name='html')['html_body']
        except Exception, e:
            pass


        self.variables = foxygen.Variables()

        xrc.XRCCTRL(self, 'project_description_tc').SetValue(self.variables.description)
        self.stree = foxygen.SourceTree(self.parent.root, self.variables)
        self.stree.collect()
        self.variables.fixDuplicates()

        _vars = self.variables.getVariables(sort = True)

        for kp,vp in self.pages.iteritems():

            _groups = sorted(self.variables.getGroups())

            for g in _groups + [None]:

                _vars = self.variables.getVariables(levels = [kp], groups = [g], sort = True)
                if len(_vars) < 1:
                    continue

                if g is None:
                    vp.Append(wxpg.PropertyCategory('misc', 'misc-group'))
                else:
                    vp.Append(wxpg.PropertyCategory(g, g + '-group'))

                for i,x in enumerate(_vars):
                    try:
                        if x.type == int:
                            prop = vp.Append(
                                    FBIntProperty(x.name,value=x.value,
                                        variables=self.variables) )
                        elif x.type == float:
                            prop = vp.Append(
                                    FBFloatProperty(x.name,value=x.value,
                                        variables = self.variables) )
                        elif x.type == "toggle":
                            prop = vp.Append( wxpg.BoolProperty(x.name,value=x.value) )
                            self.pg.SetPropertyAttribute(x.name, "UseCheckbox", True)
                        elif x.type in ["select", "switch"]:
                            prop = vp.Append( wxpg.EnumProperty(x.name, x.name,
                                x.choices, value = x.value))
                        else:
                            prop = vp.Append( wxpg.StringProperty(x.name,value=str(x.value)) )
                        if kp == 'read-only':
                            prop.Enable(False)
                    except Exception, e:
                        logging.warning('%s: %s:%d: %s' % (x.name, x.fname,
                            x.descrPos[0], str(e)))

    def clear(self):
        if self.initialized:
            self.pg.Clear()

    def onGenerate(self, evt):
        d = self.pg.GetPropertyValues(inc_attributes=False)
        self.variables.setValuesFromDict(d)
        self.stree.generate()

    def propagate(self):
        xrc.XRCCTRL(self, 'project_description_tc').SetValue(self.variables.description)
        _vars = self.variables.getVariables()
        for v in _vars:
            if v.type in ['select', 'switch']:
                _value = v.choices[v.value]
            else:
                _value = v.value
            self.pg.SetPropertyValue(v.name, v.value)

    def retrieve(self):
        _vars = self.variables.getVariables()
        for v in _vars:
            _val = self.pg.GetPropertyValue(v.name)
            if v.type in ['select', 'switch']:
                _value = _val
            else:
                _value = _val
            self.variables[v.name] = _value

    def onReset(self, evt):
        self.retrieve()
        self.stree.resetAll()
        self.propagate()

    def onLoad(self, evt):
        openFileDialog = wx.FileDialog(self, "Open configuration file", "", "", "", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if openFileDialog.ShowModal() == wx.ID_CANCEL:
            return
        _path = openFileDialog.GetPath()
        self.variables.loadJson(_path)
        self.propagate()

    def onSave(self, evt):
        d = self.pg.GetPropertyValues(inc_attributes=False)
        self.variables.setValuesFromDict(d)
        self.variables.description = xrc.XRCCTRL(self, 'project_description_tc').GetValue()
        openFileDialog = wx.FileDialog(self, "Save configuration file", "", "", "", wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if openFileDialog.ShowModal() == wx.ID_CANCEL:
            return
        _path = openFileDialog.GetPath()
        self.variables.dumpJson(_path)

    def onSelected(self, evt):
        _property = evt.GetProperty()
        if not _property is None:
            _helptxt = ""
            label = _property.GetLabel()
            try:
                _d = {}
                _var = self.variables[label]
                _h = _var.toReST()
                _helptxt = publish_parts(_h, writer_name='html')['html_body']
            except Exception, e:
                logging.warning(str(e), exc_info = 1)
                _helptxt = '<html><body>no help available</body><html>'
            xrc.XRCCTRL(self, 'help_txt').SetPage(_helptxt)

    def collect(self):

        self.pages = {}
        for k in foxygen.Variable.LEVELS:
            _icon = wx.Bitmap(_getpath('xrc', 'level-%s.png' % k))
            self.pages[k] = self.pg.AddPage(k, _icon) 
        #self.pg.Bind(wx.EVT_PG_DOUBLE_CLICK, self.onRun)
        self.pg.Bind(wxpg.EVT_PG_SELECTED, self.onSelected)

        rt = CollectThread(self)
        rt.start()

        self.initialized = True

    def onRun(self, evt):
        _fo = True
        _sel = xrc.XRCCTRL(self, 'commands_box').GetSelections()
        if len(_sel) < 1: 
            return
        _CMD = [sys.executable, self.parent._waf]
        for i in _sel:
            cmd = xrc.XRCCTRL(self, 'commands_box').GetString(i)
            if cmd == 'build documentation':
                _fo = True
                _CMD += ['doxygen', 'sphinx']
            else:
                _fo = True
                _CMD += [cmd]
        rt = RunThread(self, _CMD, fulloutput = _fo)
        rt.start()

    def onClear(self, evt):
        xrc.XRCCTRL(self, 'details_tc').Clear()


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
        self.SetIcon(_icon)


class FBTestFrame(wx.Frame):

    __COPYRIGHT = '(c) 2015, 2016 Fraunhofer IISB'

    def PreCreate(self, pre):
        pass

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1)

        self.parent = parent
        try:
            self.root = sys.argv[1]
        except:
            self.root = '.'

        self.panel = FBConfigurePanel(self, init = True)
        self.SetMinSize((800, 700))
        self.Fit()


TRAY_TOOLTIP = 'System Tray Demo'
TRAY_ICON = _getpath('xrc', 'icon-128.png')


def create_menu_item(menu, label, func):
    item = wx.MenuItem(menu, -1, label)
    menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.AppendItem(item)
    return item


class TaskBarIcon(wx.TaskBarIcon):
    def __init__(self):
        #super(TaskBarIcon, self).__init__()
        wx.TaskBarIcon.__init__(self)
        self.set_icon(TRAY_ICON)
        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        create_menu_item(menu, 'Say Hello', self.on_hello)
        menu.AppendSeparator()
        create_menu_item(menu, 'Exit', self.on_exit)
        return menu

    def set_icon(self, path):
        icon = wx.IconFromBitmap(wx.Bitmap(path))
        self.SetIcon(icon, TRAY_TOOLTIP)

    def on_left_down(self, event):
        print 'Tray icon was left-clicked.'

    def on_hello(self, event):
        print 'Hello, world!'

    def on_exit(self, event):
        wx.CallAfter(self.Destroy)


class FBFrontDeskApp(wx.App):

    def OnInit(self):
        frame = FBTestFrame(None)
        self.SetTopWindow(frame)
        TaskBarIcon()
        frame.Show()
        return True

    def OnExit(self):
        wx.App.OnExit(self)

def main():
    app = FBFrontDeskApp(False)
    app.MainLoop()


if __name__ == '__main__':
    main()


