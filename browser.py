from selenium import webdriver
from selenium.webdriver import FirefoxOptions
import copy
import time
from .helpers import format_dirpath
from .helpers import mydir, remove, isfile, url_formatter
import os
import shutil
import signal
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
import traceback


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

topdir = format_dirpath(mydir())

class HangingError(Exception):
    pass

def hang_handler(signum, frame):
    raise HangingError("browser is hanging and timed out")

def timeout_handler(signum, frame):
    raise HangingError("timed out")

##################################################################
#                           BROWSER CLASS
##################################################################


class firefox_manager:
    '''
    wrapper for selenium Firefox webdriver.
    1) ensures that hanging page loads don't hang forever
        signal.signal(signal.SIGALRM, hang_handler)
        redundant; TODO: check into this
    2) automatic/simple profile management
    '''
    def __init__(self, headless=False, profile_dir=None, **kwargs):
        time.sleep(1)
        if 'browser_pid' in kwargs and 'active_browser' in kwargs:
            self.browser_pid = kwargs['browser_pid']
            self.active_browser = kwargs['active_browser']
        else:
            self.browser_pid = None
            self.active_browser = None
        self.headless = headless
        self.profile_dir = profile_dir
        self.tmp_profile_dir = None

    def launch_browser(self):
        try:
            opts = FirefoxOptions()
            if self.profile_dir is not None:
                opts.profile = self.profile_dir
            if self.headless:
                opts.add_argument('--headless')
            self.active_browser = webdriver.Firefox(options=opts)
            self.browser_pid = self.active_browser.capabilities['moz:processID']
            self.tmp_profile_dir = self.active_browser.capabilities['moz:profile']
            self.active_browser.fullscreen_window()
        except Exception as e:
            logger.error('failed to create browser because '+str(e))
            traceback.print_exc()

    def destroy_tmp(self):
        if self.tmp_profile_dir is not None:
            if os.path.exists(self.tmp_profile_dir):
                if self.profile_dir is not None:
                    if os.path.exists(self.profile_dir):
                        try:
                            shutil.copytree(self.tmp_profile_dir, self.profile_dir,
                                    ignore=shutil.ignore_patterns("parent.lock",
                                        "lock", ".parentlock"))
                        except Exception as e:
                            logger.error("failed to copy "+self.tmp_profile_dir+" to "\
                                    + self.profile_dir+ " due to: "+str(e))
                try:
                    shutil.rmtree(self.tmp_profile_dir)
                except Exception as e:
                    logger.error("failed to delete "+self.tmp_profile_dir+" due to: "+str(e))
        self.tmp_profile_dir = None

    def close_browser(self):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)
        try:
            self.close_browser()
        except HangingError:
            logger.error("failed to close browser "+str(self.browser_pid))
            self.kill_browser()
        finally:
            signal.alarm(0)
            self.active_browser = None
            self.browser_pid = None

    def quit_browser(self):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)
        try:
            self.active_browser.quit()
        except Exception as e:
            logger.warning("failed to close "+str(self.browser_pid)+", killing...")
            logger.error(str(e))
            self.kill_browser()
        finally:
            signal.alarm(0)
            self.browser_pid = None
            self.active_browser = None

    def kill_browser(self):
        # try to kill firefox by pid
        logger.debug("killing..."+str(self.browser_pid))
        os.kill(self.browser_pid, signal.SIGTERM)
        self.browser_pid = None
        self.active_browser = None
        self.destroy_tmp()

    def get(self, url, tries=20, dwell=5, failkill=True):
        logger.debug('called GET: ' + url)
        src = ''
        for count in range(tries):
            signal.signal(signal.SIGALRM, hang_handler)
            signal.alarm(15+count)
            try:
                try:
                    if self.browser_pid is None:
                        self.launch_browser()
                    self.active_browser.get(url_formatter(url))
                    time.sleep(dwell)
                    src = self.active_browser.page_source
                    break
                except HangingError:
                    raise HangingError
                except Exception as e:
                    logger.error(str(e))
                    signal.alarm(0)
                    if failkill:
                        self.close_browser()
                finally:
                    signal.alarm(0)
            except HangingError:
                logger.warning("hanging error!! "+str(self.browser_pid))
                self.kill_browser()
                if count < tries - 1:
                    logger.debug("trying "+str(count)+"th time...")
        return src
