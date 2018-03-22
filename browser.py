from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver import FirefoxOptions
import copy
import time
from helpers import format_dirpath
from helpers import mydir, remove, isfile, url_formatter
from helpers import copy as hcopy
import os
import shutil
import signal

##################################################################
#                           LOGGING
##################################################################
import logging
import logging.config

logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

# create logger
logger = logging.getLogger(__name__)
logger.debug(__name__+"logger loaded")

##################################################################
#                           GLOBAL
##################################################################

def_prefs = webdriver.FirefoxProfile().DEFAULT_PREFERENCES
topdir = format_dirpath(mydir())

class HangingError(Exception):
    pass

def hang_handler(signum, frame):
    raise HangingError("browser is hanging and timed out")

class my_ffprof(webdriver.firefox.firefox_profile.FirefoxProfile):
    def __init__(self, profile_directory=None):
        if not FirefoxProfile.DEFAULT_PREFERENCES:
            FirefoxProfile.DEFAULT_PREFERENCES = def_prefs

        self.default_preferences = copy.deepcopy(FirefoxProfile.DEFAULT_PREFERENCES['mutable'])
        self.native_events_enabled = True
        self.tempfolder = None
        self.profile_dir = profile_directory
        curr_time = str(time.time())
        if self.profile_dir is None:
            self.profile_dir = format_dirpath(topdir+"profiles/"+curr_time)
        else:
            self.tempfolder = format_dirpath(topdir+"profiles/"+curr_time)
            newprof = os.path.join(self.tempfolder, "webdriver-py-profilecopy")
            shutil.copytree(self.profile_dir, newprof,
                    ignore=shutil.ignore_patterns("parent.lock", "lock",
                        ".parentlock"))
            self.profile_dir = newprof
            self._read_existing_userjs(os.path.join(self.profile_dir,
                "user.js"))
        self.extensionsDir = os.path.join(self.profile_dir, "extensions")
        self.userPrefs = os.path.join(self.profile_dir, "user.js")


##################################################################
#                           BROWSER CLASS
##################################################################


class firefox_manager:
    def __init__(self, **kwargs):
        time.sleep(1)
        if 'browser_pid' in kwargs and 'active_browser' in kwargs:
            self.browser_pid = kwargs['browser_pid']
            self.active_browser = kwargs['active_browser']
        else:
            self.browser_pid = None
            self.active_browser = None
        self.profile = None
        if 'profile' in kwargs:
            self.profile = kwargs['profile']
        if 'profile_name' in kwargs:
            self.profile_name = kwargs['profile_name']
            if self.profile is None:
                while True:
                    try:
                        self.profile = my_ffprof(format_dirpath(topdir+'browsers/'+profile_name))
                        break
                    except OSError:
                        time.sleep(random.randint(0, 5))
        else:
            if self.profile is None:
                while True:
                    try:
                        self.profile = my_ffprof()
                        break
                    except OSError:
                        time.sleep(random.randint(0, 5))
            self.profile_name = self.profile.profile_dir.split("/")[-1]
        if 'noimages' in kwargs:
            if kwargs['noimages']:
                self.profile.set_preference('permissions.default.stylesheet', 2)
                self.profile.set_preference('permissions.default.image', 2)
                self.profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
        if 'headless' in kwargs:
            self.headless = kwargs['headless']
        else:
            self.headless = False
        self.browser_dir = format_dirpath(topdir+'browsers/'+self.profile_name)
        self.cookies = format_dirpath(self.profile.path)+'cookies'

    def save_profile(self):
        """ Copies the temporary profile back into place """
        # Delete the old one
        try:
            remove(self.browser_dir)
            hcopy(format_dirpath(self.profile.path), self.browser_dir)
            # print self.profile.path
            # Delete the contents of "extensions"
            remove(self.browser_dir+'extensions/fxdriver@googlecode.com/')
            remove(self.browser_dir+'x86/')
            remove(self.browser_dir+'amd64/')
        except OSError:
            pass

    def savecookies(self, outcookiesf=None):
        # print 'saving cookies'
        mycookiesf = format_dirpath(self.profile.path)+'cookies'
        if outcookiesf is None:
            outcookiesf = format_dirpath(topdir+'cookies')+self.profile_name
        if isfile(self.cookies+'.sqlite'):
            try:
                # print mycookiesf
                # print outcookiesf
                hcopy(mycookiesf+'.sqlite', outcookiesf+'.sqlite')
                hcopy(mycookiesf+'.sqlite-shm', outcookiesf+'.sqlite-shm')
                hcopy(mycookiesf+'.sqlite-wal', outcookiesf+'.sqlite-wal')
            except OSError:
                pass

    def loadcookies(self, outcookiesf=None):
        # print 'loading cookies'
        mycookiesf = format_dirpath(self.profile.path)+'cookies'
        if outcookiesf is None:
            outcookiesf = format_dirpath(topdir+'cookies')+self.profile_name
        if isfile(outcookiesf+'.sqlite'):
            try:
                # print mycookiesf
                # print outcookiesf
                hcopy(outcookiesf+'.sqlite', mycookiesf+'.sqlite')
                hcopy(outcookiesf+'.sqlite-shm', mycookiesf+'.sqlite-shm')
                hcopy(outcookiesf+'.sqlite-wal', mycookiesf+'.sqlite-wal')
            except OSError:
                pass

    def browser(self):
        while True:
            try:
                opts = FirefoxOptions()
                if self.headless:
                    opts.add_argument("--headless")
                return webdriver.Firefox(self.profile, firefox_options=opts)
            except Exception as e:
                print 'failed to create browser because '+str(e)+', trying again...'

    def close_browser(self):
        signal.signal(signal.SIGALRM, hang_handler)
        signal.alarm(10)
        try:
            self.active_browser.close()
        except Exception as e:
            logger.warning("failed to close "+str(self.browser_pid)+", killing...")
            print e
            self.kill_browser()
        finally:
            signal.alarm(0)
            self.browser_pid = None
            self.active_browser = None

    def quit_browser(self):
        signal.signal(signal.SIGALRM, hang_handler)
        signal.alarm(10)
        try:
            self.active_browser.quit()
        except Exception as e:
            logger.warning("failed to close "+str(self.browser_pid)+", killing...")
            print e
            self.kill_browser()
        finally:
            signal.alarm(0)
            self.browser_pid = None
            self.active_browser = None

    def kill_browser(self):
        # try to kill firefox by pid
        print "killing..."
        print self.browser_pid
        os.kill(self.browser_pid, signal.SIGTERM)
        self.browser_pid = None
        self.active_browser = None

    def get(self, url, tries=20, dwell=5):
        print 'called GET-------------------------------------' + url
        src = ''
        for count in range(tries):
            signal.signal(signal.SIGALRM, hang_handler)
            signal.alarm(15+count)
            try:
                try:
                    self.active_browser = self.browser()
                    self.browser_pid = self.active_browser.context.im_self.capabilities['moz:processID']
                    #print("created browser for GET "+str(self.browser_pid))
                    self.active_browser.get(url_formatter(url))
                    time.sleep(dwell)
                    src = self.active_browser.page_source
                    #print("got src "+str(self.browser_pid))
                    break
                except Exception as e:
                    print(e)
                    print(self.browser_pid)
                    signal.alarm(0)
                    self.close_browser()
                finally:
                    signal.alarm(0)
            except HangingError:
                logger.warning("hanging error!! "+str(self.browser_pid))
                self.kill_browser()
                if count < tries - 1:
                    print "trying agian..."
        self.close_browser()
        return src

    def multiget(self, url, tries=20, dwell=3, passing=False):
        print 'called multiget--------------------------------------' + url
        src = ''
        for count in range(tries):
            signal.signal(signal.SIGALRM, hang_handler)
            signal.alarm(15+count)
            try:
                try:
                    if self.browser_pid is None:
                        print 'making browser...'
                        self.active_browser = self.browser()
                        print 'made browser'
                        self.browser_pid = self.active_browser.binary.process.pid
                        print 'got pid'
                        #print("created browser for multiGET "+str(self.browser_pid))
                    self.active_browser.get(url)
                    time.sleep(dwell)
                    src = self.active_browser.page_source
                    #print("got src "+str(self.browser_pid))
                    break
                except Exception as e:
                    print(e)
                    print 'other exception in multiget'
                    print(self.browser_pid)
                    signal.alarm(0)
                    self.close_browser()
                finally:
                    signal.alarm(0)
            except HangingError:
                print("timeout error in multiget!! "+str(self.browser_pid))
                self.kill_browser()
                if count < tries - 1:
                    print "trying agian..."
        if passing:
            return src, {'browser': self.active_browser,
                         'pid': self.browser_pid, 'profile': self.profile}
        else:
            return src

    def browse(self, url):
        src = ''
        self.active_browser = self.browser()
        self.browser_pid = self.active_browser.context.im_self.capabilities['moz:processID']
        print("created browser for GET "+str(self.browser_pid))
        try:
            self.active_browser.get(url)
            src = self.active_browser.page_source
            time.sleep(100000000)
        except Exception as e:
            print(e)
            self.close_browser()
        self.save_profile()
        self.close_browser()
        return src

    def cleanup(self):
        if self.profile.profile_dir[-1] == "/":
            remove('/'.join(self.profile.profile_dir.split('/')[:-2])+'/')
        else:
            remove('/'.join(self.profile.profile_dir.split('/')[:-1])+'/')

    def destroyself(self):
        if self.browser_pid is not None:
            self.quit_browser()
        if self.profile.profile_dir[-1] == "/":
            remove('/'.join(self.profile.profile_dir.split('/')[:-2])+'/')
        else:
            remove('/'.join(self.profile.profile_dir.split('/')[:-1])+'/')

    def destroysave(self):
        if self.browser_pid is not None:
            self.quit_browser()
        self.destroyself()
        rmdir = format_dirpath(topdir+'browsers/'+self.profile_name)
        remove(rmdir)
        outcookiesf = format_dirpath(topdir+'cookies')+self.profile_name
        if isfile(outcookiesf+'.sqlite'):
            try:
                remove(outcookiesf+'.sqlite')
                remove(outcookiesf+'.sqlite-shm')
                remove(outcookiesf+'.sqlite-wal')
            except OSError:
                pass
        time.sleep(5)
