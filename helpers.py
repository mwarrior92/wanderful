import inspect
import os
import shutil
import logging.config
import json
import tarfile

"""
NOTE: most of the helper functions are just to make main code less cluttered
"""

##############################################################
#                       PATH SETUP
##############################################################


def mydir():
    f = os.path.abspath(inspect.stack()[1][1])  # source [1]
    d = "/".join(f.split("/")[:-1]) + "/"
    return d


self_file = os.path.abspath(inspect.stack()[0][1]) # source [1]
top_dir = "/".join(self_file.split("/")[:-1])+"/"


##############################################################
#                     LOGGING SETUP
##############################################################

# load logger config file and create logger
logging.config.fileConfig(top_dir+'logging.conf',
        disable_existing_loggers=False)
logger = logging.getLogger(__name__)
logger.debug("top directory level set to: "+top_dir)

##############################################################
#                        FILE I/O
##############################################################


def isfile(fname):
    # wrapper for checking to see if a file fname exists
    return os.path.isfile(fname)


def fix_ownership(path):
    # Change the owner of the file to SUDO_UID
    uid = os.environ.get('SUDO_UID')
    gid = os.environ.get('SUDO_GID')
    if uid is not None:
        os.chown(path, int(uid), int(gid))
        logger.debug("updated ownership of "+path)


def untar(fname, dst):
    tar = tarfile.open(fname)
    tar.extractall(path=dst)
    tar.close()
    fix_ownership(dst)


def make_tarfile(output_filename, source_dir):
    try:
        tar = tarfile.open(output_filename, "w:gz")
        try:
            tar.add(source_dir, arcname=os.path.basename(source_dir))
        except:
            logger.error("failed to make "+output_filename+" from "+source_dir)
    except IOError:
        logger.error("IOError: failed to make "+output_filename+" from "+source_dir)
    finally:
        tar.close()
    try:
        fix_ownership(output_filename)
    except:
        pass
    logger.debug("made tar ball named "+output_filename)


def overwrite(path, content):
    """
    :param path: (str) path to file to be written to (including file name)
    :param content: (str) data to be written to file

    this is a simple wrapper to reduce 'w+' writes into clean one-liners
    """
    try:
        f = open(path, 'w+')
        try:
            f.write(content)
        finally:
            f.close()
    except IOError:
        logger.error("failed to overwrite "+path)
        return
    logger.debug("successfully overwrote "+path)


def append_file(path, content):
    """
    :param path: (str) path to file to be written to (including file name)
    :param content: (str) data to be written to file

    this is a simple wrapper to reduce 'a+' writes into clean one-liners
    """

    try:
        f = open(path, 'a+')
        try:
            f.write(content)
        finally:
            f.close()
    except IOError:
        logger.error("failed to append to "+path)
        return
    logger.debug("successfully appended to "+path)


def format_dirpath(path):
    """
    :param path: (str) a path to a dir in a filesystem; assumes path uses '/' as
    dir delimitter
    :return: (str) a properly formatted, absolute path string

    This 1) removes relative '..' items from the path, 2) removes redundant '/'
    from the path, 3) creates any non-existant directories in the path, 4) ends
    thee path with '/'

    NOTE: this will build an ABSOLUTE path, CREATING any non-existant
    directories along the way as needed. ONLY use this when you KNOW the path is
    EXACTLY what you want/need it to be.
    """
    dirs = path.split('/')
    path = '/'
    if dirs[0] != "":
        raise ValueError('relative path not allowed')
    for d in dirs:
        # account for empty strings from split
        if d == '..':
            path = '/'.join(path.split('/')[:-2])+'/'
        elif d != '':
            path = path + d + '/'
        else:
            continue
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except OSError:
            logger.error('OSError creating file path for '+path)
    logger.debug("corrected path: "+path)
    return path


def listfiles(parentdir, prefix="", containing="", suffix=""):
    """
    :param parentdir: (str) the directory from which you would like the files listed
    :param prefix: (str) leading characters to match in returned file names
    :param containing: (str) substring to match in returned file names
    :param suffix: (str) trailing characters to match in returned file names
    :return: (list(str)) list of file names from parentdir that meet the param
    constraints
    """
    # return list of file names in parentdir;
    # setting fullpath to True will give filenames with the direct/full path as
    # a prefix
    for root, dirs, files in os.walk(parentdir):
        outlist = list()
        for f in files:
            if f.startswith(prefix) and containing in f and f.endswith(suffix):
                outlist.append(f)
        return outlist


def listdirs(parentdir, prefix="", containing="", suffix=""):
    """
    :param parentdir: (str) the directory from which you would like the dirs listed
    :param prefix: (str) leading characters to match in returned dir names
    :param containing: (str) substring to match in returned dir names
    :param suffix: (str) trailing characters to match in returned dir names
    :return: (list(str)) list of dir names from parentdir that meet the param
    constraints
    """
    # return list of file names in parentdir;
    # setting fullpath to True will give filenames with the direct/full path as
    # a prefix
    for root, dirs, files in os.walk(parentdir):
        outlist = list()
        for d in dirs:
            if d.startswith(prefix) and containing in d and d.endswith(suffix):
                outlist.append(d)
        return outlist


def remove(fname):
    """
    :param fname: (str) the name of the file to be removed

    removes (deletes) the file, 'fname'

    NOTE: also accepts directories and wildcards
    NOTE: directories must end in '/'
    """
    try:
        if fname[-1] == '*' or fname[-1] == '/':
            shutil.rmtree(fname)
        else:
            os.remove(fname)
    except OSError as e:
        logger.error('OSError removing '+fname+"; "+str(e))
        return
    logger.debug("Successfully removed "+fname)


def copy(src, dst):
    # copy file src to file or dir dst
    try:
        if src[-1] == '/':
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy(src, dst)
    except OSError:
        logger.error('OSError copying '+src+' to '+dst)
    logger.debug("copied "+src+" to "+dst)

##############################################################
#                   GENERIC BASE CLASSES
##############################################################


def to_dict(item):
    if hasattr(item, 'to_dict'):
        return item.to_dict()
    elif hasattr(item, '__iter__') and type(item) is not dict:
        return [to_dict(z) for z in item]
    else:
        # catch for objects I didn't make that need to be transformed into a str first
        try:
            _ = json.dumps({"entry": item})
            return item
        except:
            return str(item)


class Extendable(object):
    def get(self, member):
        """
        :param member: (str) name of member whose value should be returned
        :return:
        """
        if hasattr(self, "get_"+member):
            return getattr(self, "get_"+member)()
        else:
            return getattr(self, member)

    def set(self, member_name, val):
        """

        :param member_name:
        :param val:
        :return:
        """
        if hasattr(self, "set_"+member_name):
            getattr(self, "set_"+member_name)(val)
        else:
            setattr(self, member_name, val)

    def to_dict(self, skip_nones=True):
        members = [v for v in vars(self) if not callable(v) and not v.startswith('_')]
        d = dict()
        for m in members:
            tmp = to_dict(self.get(m))
            if tmp is not None and skip_nones: # skip None entries to save space
                d[m] = to_dict(self.get(m))
        d['CLASS'] = self.__class__.__name__
        return d

    def save_json(self, file_path=None, skip_nones=True):
        if file_path is None:
            if hasattr(self, 'file_path'):
                file_path = self.get('file_path')
            else:
                raise ValueError('file_path must be defined')
        data = self.to_dict(skip_nones)
        with open(file_path, "w+") as f:
            json.dump(data, f)

    def load_json(self, file_path):
        with open(file_path, "r+") as f:
            d = json.load(f)
        for k in d:
            self.set(k, d[k])


##############################################################
#                       PARSING
##############################################################

def url_formatter(url):
    if '//' not in url:
        url = "http://"+url
    return url

