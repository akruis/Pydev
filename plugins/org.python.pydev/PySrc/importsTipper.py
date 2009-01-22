import os.path
import re
import linecache
import inspect
import sys
from _tipper_common import DoFind


#completion types.
TYPE_IMPORT = '0'
TYPE_CLASS = '1'
TYPE_FUNCTION = '2'
TYPE_ATTR = '3'
TYPE_BUILTIN = '4'
TYPE_PARAM = '5'

def _imp(name):
    try:
        return __import__(name)
    except:
        if '.' in name:
            sub = name[0:name.rfind('.')]
            return _imp(sub)
        else:
            s = 'Unable to import module: %s - sys.path: %s' % (str(name), sys.path)
            raise ImportError(s)

def GetFile(mod):
    f = None
    try:
        f = inspect.getsourcefile(mod) or inspect.getfile(mod)
    except:
        if hasattr(mod, '__file__'):
            f = mod.__file__
            if f.lower(f[-4:]) in ['.pyc', '.pyo']:
                filename = f[:-4] + '.py'
                if os.path.exists(filename):
                    f = filename
            
    return f

def Find(name):
    f = None
    
    mod = _imp(name)
    parent = mod
    foundAs = ''
    
    if inspect.ismodule(mod):
        f = GetFile(mod)
        
    components = name.split('.')

    old_comp = None
    for comp in components[1:]:
        try:
            #this happens in the following case:
            #we have mx.DateTime.mxDateTime.mxDateTime.pyd
            #but after importing it, mx.DateTime.mxDateTime does shadows access to mxDateTime.pyd
            mod = getattr(mod, comp)
        except AttributeError:
            if old_comp != comp:
                raise
        
        if inspect.ismodule(mod):
            f = GetFile(mod)
        else:
            if len(foundAs) > 0:
                foundAs = foundAs+'.'
            foundAs = foundAs+comp
            
        old_comp = comp
        
    return f, mod, parent, foundAs

def Search(data):
    '''@return file, line, col
    '''
    
    data = data.replace('\n', '')
    if data.endswith('.'):
        data = data.rstrip('.')
    f, mod, parent, foundAs = Find(data)
    try:
        return DoFind(f, mod), foundAs
    except:
        return DoFind(f, parent), foundAs
    
    
def GenerateTip(data):
    data = data.replace('\n', '')
    if data.endswith('.'):
        data = data.rstrip('.')
        
    f, mod, parent, foundAs = Find(data)
    #print_ >> open('temp.txt', 'w'), f
    tips = GenerateImportsTipForModule(mod)
    return f, tips
    
    
def CheckChar(c):
    if c == '-' or c == '.':
        return '_'
    return c

def GenerateImportsTipForModule(obj_to_complete, dirComps=None, getattr=getattr, filter=lambda name:True):
    '''
        @param obj_to_complete: the object from where we should get the completions
        @param dirComps: if passed, we should not 'dir' the object and should just iterate those passed as a parameter
        @param getattr: the way to get a given object from the obj_to_complete (used for the completer)
        @param filter: a callable that receives the name and decides if it should be appended or not to the results
        @return: list of tuples, so that each tuple represents a completion with:
            name, doc, args, type (from the TYPE_* constants)
    '''
    ret = []
    
    if dirComps is None:
        dirComps = dir(obj_to_complete)
        if hasattr(obj_to_complete, '__dict__'):
            dirComps.append('__dict__')
        
    getCompleteInfo = True
    
    if len(dirComps) > 1000:
        #ok, we don't want to let our users wait forever... 
        #no complete info for you...
        
        getCompleteInfo = False
    
    dontGetDocsOn = (float, int, str, tuple, list, type)
    for d in dirComps:
        
        if d is None:
            continue
            
        if not filter(d):
            continue
        
        args = ''

        try:
            obj = getattr(obj_to_complete, d)
        except: #just ignore and get it without aditional info
            ret.append((d, '', args, TYPE_BUILTIN))
        else:

            if getCompleteInfo:
                try:
                    retType = TYPE_BUILTIN
        
                    #check if we have to get docs
                    getDoc = True
                    for class_ in dontGetDocsOn:
                        if isinstance(obj, class_):
                            getDoc = False
                            break
                            
                    doc = ''
                    if getDoc:
                        #no need to get this info... too many constants are defined and 
                        #makes things much slower (passing all that through sockets takes quite some time)
                        try:
                            doc = inspect.getdoc(obj)
                            if doc is None:
                                doc = ''
                        except: #may happen on jython when checking java classes (so, just ignore it)
                            doc = ''
                            
                            
                    if inspect.ismethod(obj) or inspect.isbuiltin(obj) or inspect.isfunction(obj) or inspect.isroutine(obj):
                        try:
                            args, vargs, kwargs, defaults = inspect.getargspec(obj)
                                
                            r = ''
                            for a in (args):
                                if len(r) > 0:
                                    r = r+', '
                                r = r+str(a)
                            args = '(%s)' % (r)
                        except TypeError:
                            #ok, let's see if we can get the arguments from the doc
                            args = '()'
                            try:
                                if len(doc) > 0:
                                    i = doc.find('->')
                                    if i < 0:
                                        i = doc.find('\n')
                                        if i < 0:
                                            i = doc.find('\r')
                                            
                                            
                                    if i > 0:
                                        s = doc[0:i]
                                        s = s.strip()
                                        
                                        #let's see if we have a docstring in the first line
                                        if s[-1] == ')':
                                            start = s.find('(')
                                            if start >= 0:
                                                end = s.find('[')
                                                if end <= 0:
                                                    end = len(s)
                                                
                                                args = s[start:end]
                                                if not args[-1] == ')':
                                                    args = args+')'
    
                                                
                                                #now, get rid of unwanted chars
                                                l = len(args)-1
                                                r = []
                                                for i in range(len(args)):
                                                    if i == 0 or i == l:
                                                        r.append(args[i])
                                                    else:
                                                        r.append(CheckChar(args[i]))
                                                        
                                                args = ''.join(r)
                                                
                            except:
                                pass
        
                        retType = TYPE_FUNCTION
                        
                    elif inspect.isclass(obj):
                        retType = TYPE_CLASS
                        
                    elif inspect.ismodule(obj):
                        retType = TYPE_IMPORT
                        
                    else:
                        retType = TYPE_ATTR
                    
                    
                    #add token and doc to return - assure only strings.
                    ret.append((d, doc, args, retType))
                    
                except: #just ignore and get it without aditional info
                    ret.append((d, '', args, TYPE_BUILTIN))
                
            else: #getCompleteInfo == False
                if inspect.ismethod(obj) or inspect.isbuiltin(obj) or inspect.isfunction(obj) or inspect.isroutine(obj):
                    retType = TYPE_FUNCTION
                    
                elif inspect.isclass(obj):
                    retType = TYPE_CLASS
                    
                elif inspect.ismodule(obj):
                    retType = TYPE_IMPORT
                    
                else:
                    retType = TYPE_ATTR
                #ok, no complete info, let's try to do this as fast and clean as possible
                #so, no docs for this kind of information, only the signatures
                ret.append((d, '', str(args), retType))
            
    return ret


    
    