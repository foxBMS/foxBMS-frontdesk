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
import shutil

import configure
import rcfile
import threading
import glob
import subprocess
import select
import re
import tarfile
import logging
import webbrowser

from foxbmsflashtool import inari
from Queue import Queue, Empty
from threading import Thread

reload(sys)
sys.setdefaultencoding('utf8')


class CustomConsoleHandler(logging.StreamHandler):
 
    def __init__(self, textctrl):
        logging.StreamHandler.__init__(self)
        self.textctrl = textctrl
 
    def emit(self, record):
        msg = self.format(record)
        self.textctrl.WriteText(msg + "\n")
        self.flush()
        
        
        
        
def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
         queue.put(line)
    out.close()

class RunThread(threading.Thread):




    def __init__(self, parent, cmd, fulloutput = True, wd = '.'):
        self.parent = parent
        threading.Thread.__init__(self)
        self.canceling = False
        self.cmd = cmd
        self.wd = wd
        self.fulloutput = fulloutput

    def run(self):
        _curdir = os.path.abspath('.')
        os.chdir(self.wd)
        if self.fulloutput:
            self.runFull()
        else:
            self.runSilent()
        os.chdir(_curdir)

    def runFull(self):
        wx.CallAfter(self.parent.enableWidgets, False)
        p = subprocess.Popen(self.cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if sys.platform.startswith('win'):
            stdout_q = Queue()
            stdout_t = Thread(target=enqueue_output, args=(p.stdout, stdout_q))
            stdout_t.start()
            stderr_q = Queue()
            stderr_t = Thread(target=enqueue_output, args=(p.stderr, stderr_q))
            stderr_t.start()
        while True:

            if self.canceling:
                p.stdout.close()
                p.stderr.close()
                break

            if sys.platform.startswith('win'):

                    
                    try:  line = stdout_q.get_nowait() # or q.get(timeout=.1)
                    except Empty:
                        pass
                    else:
                        wx.CallAfter(self.parent.writeLog, line)
                    try:  line = stderr_q.get_nowait() # or q.get(timeout=.1)
                    except Empty:
                        pass
                    else:
                        wx.CallAfter(self.parent.writeLog, line)

            else:
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
        stdout_t.join()
        stderr_t.join()

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
        self.parent = parent
        self.rcfile = rcfile.FoxBMSConfig()

        self.path = None

        self.dest = None
        self.archive = None
        self.existing = path

        self.oldProjectSel = -1

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


        xrc.XRCCTRL(self, 'workspace_dp').SetPath(self.rcfile.get('workspace'))
        xrc.XRCCTRL(self, 'add_archive_b').Bind(wx.EVT_BUTTON, self.onAddArchive)
        xrc.XRCCTRL(self, 'add_dir_b').Bind(wx.EVT_BUTTON, self.onAddDir)
        xrc.XRCCTRL(self, 'projects_lb').Bind(wx.EVT_LIST_ITEM_SELECTED, self.onPLSel)

        self.menu = self._resources.LoadMenuBar("main_menu")
        self.SetMenuBar(self.menu)
        self.menu.FindItemById(xrc.XRCID('reference_mi')).Enable(False)
        self.menu.FindItemById(xrc.XRCID('documentation_mi')).Enable(False)

        self.Bind(wx.EVT_MENU, self.onOpenDocumentation,
                id=xrc.XRCID("documentation_mi"))
        self.Bind(wx.EVT_MENU, self.onOpenReference,
                id=xrc.XRCID("reference_mi"))


        self.nb = xrc.XRCCTRL(self, 'main_nb')
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self.onPageChanging)

        self.genProjectList(True)


        xrc.XRCCTRL(self, 'clear_b').Bind(wx.EVT_BUTTON, self.onClear)
        xrc.XRCCTRL(self, 'progress').SetSize((-1, 3))
        xrc.XRCCTRL(self, 'progress').SetMaxSize((-1, 3))

        self.pages = {}
        self.pagekeys = ['projects', 'config', 'build', 'flash']
        for k in ['projects', 'build']:
            self.pages[k] = xrc.XRCCTRL(self, k + '_page')
        self.pages['config'] = configure.FBConfigurePanel(self.nb)
        self.nb.InsertPage(1, self.pages['config'], 'Configuration')

        self.pages['flash'] = inari.FBInariPanel(self.nb)
        self.nb.AddPage(self.pages['flash'], 'Flash foxBMS')

        '''
        for k in ['config', 'build', 'flash']:
            self.pages[k].Enable(False)
        '''

        
        #self.onProjectRadio(None)
        #self.panel = FBFrontDeskPanel(self)
        self.SetSize((1024, 800))
        #self.Fit()

        xrc.XRCCTRL(self, 'initialize_b').Bind(wx.EVT_BUTTON, self.onInstall)
        xrc.XRCCTRL(self, 'build_b').Bind(wx.EVT_BUTTON, self.onBuild)
        self.installLogger()

        #self.detectWaf(self.path)
        #self.selectProject(self.path)

    def onClose(self, evt):
        self.Close()

    def installLogger(self):
        _rootlogger = logging.getLogger()
        self.logHandler = CustomConsoleHandler(xrc.XRCCTRL(self, 'details_tc'))
        _rootlogger.addHandler(self.logHandler)

        '''
        dictLogConfig = {
                "version":1,
                "handlers":{
                    "fileHandler":{
                        "class":"logging.FileHandler",
                        "formatter":"myFormatter",
                        "filename":"test.log"
                        },
                    "consoleHandler":{
                        "class":"logging.StreamHandler",
                        "formatter":"myFormatter"
                        }
                    },        
                "loggers":{
                    "wxApp":{
                        "handlers":["fileHandler", "consoleHandler"],
                        "level":"INFO",
                        }
                    },

                "formatters":{
                    "myFormatter":{
                        "format":"%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                        }
                    }
                }
        logging.config.dictConfig(dictLogConfig)
        #logger = logging.getLogger("wxApp")
        '''


    def genProjectList(self, init = False):
        _lb = xrc.XRCCTRL(self, 'projects_lb')
        _sel = -1
        if not init:
            _sel = _lb.GetNextSelected(-1)
        self.SetTitle('foxBMS Front Desk')
        xrc.XRCCTRL(self, 'initialize_b').SetLabel('Initialize project')
        xrc.XRCCTRL(self, 'initialize_b').Enable(False)

        if init:
            _lb.InsertColumn(0, 'name', width = 200) 
            _lb.InsertColumn(1, 'path', width = 400) 
            _lb.InsertColumn(2, 'initialized', width = 100)
        else:
            _lb.DeleteAllItems()

        # only if on start page
        if self.nb.GetSelection() == 0:
            self.name, self.path = None, None
            if _sel == -1:
                self.status['initialized'] = False
         
        for p in self.rcfile.get('projects'):
             index = _lb.InsertStringItem(sys.maxint, p['name']) 
             _lb.SetStringItem(index, 1, p['path']) 
             if configure.isInitialized(p['path']):
                 _lb.SetStringItem(index, 2, 'yes')
             else:
                 _lb.SetStringItem(index, 2, 'no')
             #self.list.SetStringItem(index, 2, i[2]) 

        if not init and _sel > -1:
            _lb.Select(_sel)

    def onAddArchive(self, evt):
        # update workspace dir
        self.rcfile.set('workspace', xrc.XRCCTRL(self, 'workspace_dp').GetPath())
        if not os.path.exists(self.rcfile.get('workspace')):
            try:
                os.makedirs(self.rcfile.get('workspace'))
            except Exception, e:
                logging.error(str(e))
        d = AddArchiveDialog(self)
        if d.ShowModal() == wx.ID_OK:
            self.genProjectList()

    def onPLSel(self, evt):

        _idx = evt.GetIndex()
        _name = xrc.XRCCTRL(self, 'projects_lb').GetItemText(_idx, 0)
        _path = xrc.XRCCTRL(self, 'projects_lb').GetItemText(_idx, 1)
        _init = xrc.XRCCTRL(self, 'projects_lb').GetItemText(_idx, 2)

        self.name, self.path, = _name, _path 
        self.SetTitle('foxBMS Front Desk | %s' % _name)


        if _idx != self.oldProjectSel:
            self.status['configured'] = False
            self.status['initialized'] = (_init == 'yes')

        self.oldProjectSel = _idx

        if _init == 'yes':
            xrc.XRCCTRL(self, 'initialize_b').SetLabel('Re-initialize project')

            self.menu.FindItemById(xrc.XRCID('reference_mi')).Enable(True)
            self.menu.FindItemById(xrc.XRCID('documentation_mi')).Enable(True)

        else:
            xrc.XRCCTRL(self, 'initialize_b').SetLabel('Initialize project')
            self.menu.FindItemById(xrc.XRCID('reference_mi')).Enable(False)
            self.menu.FindItemById(xrc.XRCID('documentation_mi')).Enable(False)

        xrc.XRCCTRL(self, 'initialize_b').Enable(True)
        self.pages['flash'].setPaths(self.path)

    def onAddDir(self, evt):
        d = AddDirDialog(self)
        if d.ShowModal() == wx.ID_OK:
            self.genProjectList()

    def onInstall(self, evt):
        # FIXME bad hack
        self.status['initialized'] = True
        self.menu.FindItemById(xrc.XRCID('reference_mi')).Enable(True)
        self.menu.FindItemById(xrc.XRCID('documentation_mi')).Enable(True)
        self.detectWaf(self.path)
        self._tasks = 4
        self.runWaf('configure', 'doxygen', 'sphinx', wd = self.path)

    def onBuild(self, evt):
        self.detectWaf(self.path)
        print self.path, self._waf
        self._tasks = 1
        self.runWaf('build', wd = self.path)
        self.status['built'] = True

    def onPageChanging(self, evt):
        _old = self.nb.GetSelection() 
        _new = evt.GetSelection()

        print self.pagekeys[_old], self.pagekeys[_new], _old, _new, self.pagekeys.index('build')
        for k,v in self.status.iteritems():
            print k,v

        # page change logic
        # you can always go back

        if _old > _new:
            return

        if not self.status['initialized']:
            evt.Veto()
            return

        if not self.status['configured']:
            if _new > self.pagekeys.index('config'):
                evt.Veto()
                return
            self.nb.root = self.path
            wx.CallAfter(self.pages['config'].clear)
            wx.CallAfter(self.pages['config'].collect)
            self.status['configured'] = True
            return
            
        if self.status['configured']:
           xrc.XRCCTRL(self, 'build_b').Enable(True)
           return
           
        if _new > self.pagekeys.index('build') and not self.status['built']:
            evt.Veto()
            return

        return


    def onPageChangingVeto(self, evt):
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


    def detectWaf(self, path):
        _wafs = [w for w in glob.glob(os.path.join(path, 'tools/waf-*')) if os.path.isfile(w)]
        logging.debug('wafs found: %s' % _wafs)
        self._waf = _wafs[-1]

    def onOpenDocumentation(self, evt):
        _path = os.path.abspath(os.path.join(self.path, 'build/doc/sphinx/html/index.html'))
        webbrowser.open('file://' + _path)

    def onOpenReference(self, evt):
        _path = os.path.abspath(os.path.join(self.path, 'build/doc/doxygen/html/index.html'))
        webbrowser.open('file://' + _path)

    def runWaf(self, *args, **kwargs):
        xrc.XRCCTRL(self, 'details_tc').Clear()
        _fo = True
        if len(args) < 1: 
            return
        _CMD = [sys.executable, self._waf]
        _fo = True
        _CMD += args
        rt = RunThread(self, _CMD, fulloutput = _fo, **kwargs)
        rt.start()
        return rt

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
        #_ds.SetTextColour(_c)


    def setProgress(self, prog, ran):
        xrc.XRCCTRL(self, 'progress').SetRange(ran) 
        xrc.XRCCTRL(self, 'progress').SetValue(prog)

    def enableWidgets(self, enable = True):
        for widget in self.GetChildren(): 
            widget.Enable(enable) 
        xrc.XRCCTRL(self, 'projects_lb').Enable(enable)

        if enable:
            self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self.onPageChanging)
        else:
            self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self.onPageChangingVeto)

        self.genProjectList()



class AddDirDialog(wx.Dialog):
    # FIXME 

    def __init__(self, parent):
        pre = wx.PreDialog()
        self.parent = parent
        parent._resources.LoadOnDialog(pre, parent, "add_dir_dlg")
        self.PostCreate(pre)
        xrc.XRCCTRL(self, 'add_dir_dlg').Bind(wx.EVT_DIRPICKER_CHANGED, self.onFC)
        xrc.XRCCTRL(self, 'project_name_tc').Bind(wx.EVT_TEXT, self.onTC)
        self.Bind(wx.EVT_BUTTON, self.onOK, id=wx.ID_OK)
        self.Fit()

    def onOK(self, evt):
        _name, _path = self.getNameAndPath()
        if _name in [p['name'] for p in self.parent.rcfile.get('projects')]:
            xrc.XRCCTRL(self, 'add_dir_error_txt').SetLabel('%s already exists.\nChoose different name.' % _name)
            return
        self.parent.rcfile.addProject(_name, _path)
        evt.Skip()

    def onTC(self, evt):
        xrc.XRCCTRL(self, 'add_dir_error_txt').SetLabel('')

    def onFC(self, evt):
        _name, _path = self.getNameAndPath()
        if _name.strip() == '':
            _name = _path.split(os.path.sep)[-1]
            xrc.XRCCTRL(self, 'project_name_tc').SetValue(_name)

    def getNameAndPath(self):
        _name = xrc.XRCCTRL(self, 'project_name_tc').GetValue()
        _path = xrc.XRCCTRL(self, 'add_dir_dp').GetPath()
        return _name, _path


class AddArchiveDialog(wx.Dialog):

    def __init__(self, parent):
        pre = wx.PreDialog()
        self.parent = parent
        parent._resources.LoadOnDialog(pre, parent, "add_archive_dlg")
        self.PostCreate(pre)
        xrc.XRCCTRL(self, 'add_archive_dlg').Bind(wx.EVT_FILEPICKER_CHANGED, self.onFC)
        xrc.XRCCTRL(self, 'project_name_tc').Bind(wx.EVT_TEXT, self.onTC)
        self.Bind(wx.EVT_BUTTON, self.onOK, id=wx.ID_OK)
        self.Fit()

    def onOK(self, evt):
        _name, _path = self.getNameAndPath()
        _name, _path = self.parent.rcfile.getProjectNameAndPath(_name)
        if os.path.exists(_path):
            xrc.XRCCTRL(self, 'add_archive_error_txt').SetLabel('%s already exists.\nChoose different name.' % _name)
            return
        xrc.XRCCTRL(self, 'add_archive_error_txt').SetForegroundColour((0,0,0))
        xrc.XRCCTRL(self, 'add_archive_error_txt').SetLabel('Extracting...')
        self.extract()
        evt.Skip()


    def getRootOfArchive(self, apath):
        with tarfile.open(apath, 'r:*') as f:
            for tarinfo in f:
                if tarinfo.isdir():
                    return tarinfo.name.split(os.path.sep)[0]
        raise RuntimeError('ill-organized archive')


    def extract(self):
        name, apath = self.getNameAndPath()
        self.parent.rcfile.addProject(name)

        # getName of root in archive
        _root = self.getRootOfArchive(apath)
        _curdir = os.path.abspath('.')
        if _root != name:
            _p = self.parent.rcfile.get('projects')[-1]
            try:
                os.makedirs(_p['path'])
            except Exception, e:
                logging.error(str(e))
            os.chdir(_p['path'])
            with tarfile.open(apath, 'r:*') as f:
                f.extractall()
            for filename in os.listdir(os.path.join(_p['path'], _root)):
                shutil.move(os.path.join(_p['path'], _root, filename), os.path.join(_p['path'], filename))
            os.rmdir(os.path.join(_p['path'], _root))
        else:
            os.chdir(self.parent.rcfile.get('workspace'))
            with tarfile.open(apath, 'r:*') as f:
                f.extractall()

        os.chdir(_curdir)

    def onTC(self, evt):
        xrc.XRCCTRL(self, 'add_archive_error_txt').SetLabel('')

    def onFC(self, evt):
        _name, _path = self.getNameAndPath()
        if _name.strip() == '':
            _name = _path.split(os.path.sep)[-1].split('.')[0]
            xrc.XRCCTRL(self, 'project_name_tc').SetValue(_name)

    def getNameAndPath(self):
        _name = xrc.XRCCTRL(self, 'project_name_tc').GetValue()
        _path = xrc.XRCCTRL(self, 'add_archive_fp').GetPath()
        return _name, _path


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
        pass
        #wx.App.OnExit(self)

def main():
    app = FBFrontDeskApp(False)
    app.MainLoop()


if __name__ == '__main__':
    main()


