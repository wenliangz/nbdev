#AUTOGENERATED! DO NOT EDIT! File to edit: dev/01_export.ipynb (unless otherwise specified).

__all__ = ['read_nb', 'check_re', 'is_export', 'find_default_export', 'export_names', 'extra_add', 'reset_nbdev_module',
           'get_nbdev_module', 'save_nbdev_module', 'notebook2script', 'get_name', 'qual_name', 'source_nb',
           'script2notebook', 'diff_nb_script']

#Cell
from .imports import *
from .core import *

#Cell
def read_nb(fname):
    "Read the notebook in `fname`."
    with open(Path(fname),'r', encoding='utf8') as f: return nbformat.reads(f.read(), as_version=4)

#Cell
def check_re(cell, pat, code_only=True):
    "Check if `cell` contains a line with regex `pat`"
    if code_only and cell['cell_type'] != 'code': return
    if isinstance(pat, str): pat = re.compile(pat, re.IGNORECASE | re.MULTILINE)
    return pat.search(cell['source'])

#Cell
_re_blank_export = re.compile(r"""
# Matches any line with #export or #exports without any module name:
^         # beginning of line (since re.MULTILINE is passed)
\s*       # any number of whitespace
\#\s*     # # then any number of whitespace
exports?  # export or exports
\s*       # any number of whitespace
$         # end of line (since re.MULTILINE is passed)
""", re.IGNORECASE | re.MULTILINE | re.VERBOSE)

#Cell
_re_mod_export = re.compile(r"""
# Matches any line with #export or #exports with a module name and catches it in group 1:
^         # beginning of line (since re.MULTILINE is passed)
\s*       # any number of whitespace
\#\s*     # # then any number of whitespace
exports?  # export or exports
\s*       # any number of whitespace
(\S+)     # catch a group with any non-whitespace chars
\s*       # any number of whitespace
$         # end of line (since re.MULTILINE is passed)
""", re.IGNORECASE | re.MULTILINE | re.VERBOSE)

#Cell
def is_export(cell, default):
    "Check if `cell` is to be exported and returns the name of the module."
    if check_re(cell, _re_blank_export):
        if default is None:
            print(f"This cell doesn't have an export destination and was ignored:\n{cell['source'][1]}")
        return default
    tst = check_re(cell, _re_mod_export)
    return os.path.sep.join(tst.groups()[0].split('.')) if tst else None

#Cell
_re_default_exp = re.compile(r"""
# Matches any line with #default_exp with a module name and catches it in group 1:
^            # beginning of line (since re.MULTILINE is passed)
\s*          # any number of whitespace
\#\s*        # # then any number of whitespace
default_exp  # export or exports
\s*          # any number of whitespace
(\S+)        # catch a group with any non-whitespace chars
\s*          # any number of whitespace
$            # end of line (since re.MULTILINE is passed)
""", re.IGNORECASE | re.MULTILINE | re.VERBOSE)

#Cell
def find_default_export(cells):
    "Find in `cells` the default export module."
    for cell in cells:
        tst = check_re(cell, _re_default_exp)
        if tst: return tst.groups()[0]

#Cell
def _create_mod_file(fname, nb_path):
    "Create a module file for `fname`."
    fname.parent.mkdir(parents=True, exist_ok=True)
    with open(fname, 'w') as f:
        f.write(f"#AUTOGENERATED! DO NOT EDIT! File to edit: dev/{nb_path.name} (unless otherwise specified).")
        f.write('\n\n__all__ = []')

#Cell
_re_patch_func = re.compile(r"""
# Catches any function decorated with @patch, its name in group 1 and the patched class in group 2
@patch         # At any place in the cell, something that begins with @patch
\s*def         # Any number of whitespace (including a new line probably) followed by def
\s+            # One whitespace or more
([^\(\s]*)     # Catch a group composed of anything but whitespace or an opening parenthesis (name of the function)
\s*\(          # Any number of whitespace followed by an opening parenthesis
[^:]*          # Any number of character different of : (the name of the first arg that is type-annotated)
:\s*           # A column followed by any number of whitespace
(?:            # Non-catching group with either
([^,\s\(\)]*)  #    a group composed of anything but a comma, a parenthesis or whitespace (name of the class)
|              #  or
(\([^\)]*\)))  #    a group composed of something between parenthesis (tuple of classes)
\s*            # Any number of whitespace
(?:,|\))       # Non-catching group with either a comma or a closing parenthesis
""", re.VERBOSE)

#Cell
_re_typedispatch_func = re.compile(r"""
# Catches any function decorated with @typedispatch
(@typedispatch  # At any place in the cell, catch a group with something that begins with @patch
\s*def          # Any number of whitespace (including a new line probably) followed by def
\s+             # One whitespace or more
[^\(]*          # Anything but whitespace or an opening parenthesis (name of the function)
\s*\(           # Any number of whitespace followed by an opening parenthesis
[^\)]*          # Any number of character different of )
\)\s*:)         # A closing parenthesis followed by whitespace and :
""", re.VERBOSE)

#Cell
_re_class_func_def = re.compile(r"""
# Catches any 0-indented function or class definition with its name in group 1
^              # Beginning of a line (since re.MULTILINE is passed)
(?:def|class)  # Non-catching group for def or class
\s+            # One whitespace or more
([^\(\s]*)     # Catching group with any character except an opening parenthesis or a whitespace (name)
\s*            # Any number of whitespace
(?:\(|:)       # Non-catching group with either an opening parenthesis or a : (classes don't need ())
""", re.MULTILINE | re.VERBOSE)

#Cell
_re_obj_def = re.compile(r"""
# Catches any 0-indented object definition (bla = thing) with its name in group 1
^          # Beginning of a line (since re.MULTILINE is passed)
([^=\s]*)  # Catching group with any character except a whitespace or an equal sign
\s*=       # Any number of whitespace followed by an =
""", re.MULTILINE | re.VERBOSE)

#Cell
def _not_private(n):
    for t in n.split('.'):
        if (t.startswith('_') and not t.startswith('__')) or t.startswith('@'): return False
    return '\\' not in t and '^' not in t and '[' not in t

def export_names(code, func_only=False):
    "Find the names of the objects, functions or classes defined in `code` that are exported."
    #Format monkey-patches with @patch
    def _f(gps):
        nm, cls, t = gps.groups()
        if cls is not None: return f"def {cls}.{nm}():"
        return '\n'.join([f"def {c}.{nm}():" for c in re.split(', *', t[1:-1])])

    code = _re_typedispatch_func.sub('', code)
    code = _re_patch_func.sub(_f, code)
    names = _re_class_func_def.findall(code)
    if not func_only: names += _re_obj_def.findall(code)
    return [n for n in names if _not_private(n)]

#Cell
_re_all_def   = re.compile(r"""
# Catches a cell with defines \_all\_ = [\*\*] and get that \*\* in group 1
^_all_   #  Beginning of line (since re.MULTILINE is passed)
\s*=\s*  #  Any number of whitespace, =, any number of whitespace
\[       #  Opening [
([^\n\]]*) #  Catching group with anything except a ] or newline
\]       #  Closing ]
""", re.MULTILINE | re.VERBOSE)

#Same with __all__
_re__all__def = re.compile(r'^__all__\s*=\s*\[([^\]]*)\]', re.MULTILINE)

#Cell
def extra_add(code):
    "Catch adds to `__all__` required by a cell with `_all_=`"
    if _re_all_def.search(code):
        names = _re_all_def.search(code).groups()[0]
        names = re.sub('\s*,\s*', ',', names)
        names = names.replace('"', "'")
        code = _re_all_def.sub('', code)
        code = re.sub(r'([^\n]|^)\n*$', r'\1', code)
        return names.split(','),code
    return [],code

#Cell
def _add2add(fname, names, line_width=120):
    if len(names) == 0: return
    with open(fname, 'r', encoding='utf8') as f: text = f.read()
    tw = TextWrapper(width=120, initial_indent='', subsequent_indent=' '*11, break_long_words=False)
    re_all = _re__all__def.search(text)
    start,end = re_all.start(),re_all.end()
    text_all = tw.wrap(f"{text[start:end-1]}{'' if text[end-2]=='[' else ', '}{', '.join(names)}]")
    with open(fname, 'w', encoding='utf8') as f: f.write(text[:start] + '\n'.join(text_all) + text[end:])

#Cell
def _relative_import(name, fname):
    mods = name.split('.')
    splits = str(fname).split(os.path.sep)
    if mods[0] not in splits: return name
    i=len(splits)-1
    while i>0 and splits[i] != mods[0]: i-=1
    splits = splits[i:]
    while len(mods)>0 and splits[0] == mods[0]: splits,mods = splits[1:],mods[1:]
    return '.' * (len(splits)) + '.'.join(mods)

#Cell
#Catches any from nbdev.bla import something and catches nbdev.bla in group 1, the imported thing(s) in group 2.
_re_import = re.compile(r'^(\s*)from (' + Config().lib_name + '.\S*) import (.*)$')

#Cell
def _deal_import(code_lines, fname):
    def _replace(m):
        sp,mod,obj = m.groups()
        return f"{sp}from {_relative_import(mod, fname)} import {obj}"
    return [_re_import.sub(_replace,line) for line in code_lines]

#Cell
def reset_nbdev_module():
    fname = Config().lib_path/'_nbdev.py'
    fname.parent.mkdir(parents=True, exist_ok=True)
    with open(fname, 'w') as f:
        f.write(f"#AUTOGENERATED BY NBDEV! DO NOT EDIT!")
        f.write('\n\n__all__ = ["index", "modules"]')
        f.write('\n\nindex = {}')
        f.write('\n\nmodules = []')

#Cell
def get_nbdev_module():
    try:
        mod = importlib.import_module(f'{Config().lib_name}._nbdev')
        mod = importlib.reload(mod)
        return mod
    except:
        print("Run `reset_nbdev_module` to create an empty skeletton.")

#Cell
_re_index_idx = re.compile(r'index\s*=\s*{[^}]*}')
_re_index_mod = re.compile(r'modules\s*=\s*\[[^\]]*\]')

#Cell
def save_nbdev_module(mod):
    fname = Config().lib_path/'_nbdev.py'
    with open(fname, 'r') as f: code = f.read()
    t = ',\n         '.join([f'"{k}": "{v}"' for k,v in mod.index.items()])
    code = _re_index_idx.sub("index = {"+ t +"}", code)
    t = ',\n           '.join([f'"{f}"' for f in mod.modules])
    code = _re_index_mod.sub(f"modules = [{t}]", code)
    with open(fname, 'w') as f: f.write(code)

#Cell
def _notebook2script(fname, silent=False, to_dict=None):
    "Finds cells starting with `#export` and puts them into a new module"
    if os.environ.get('IN_TEST',0): return  # don't export if running tests
    fname = Path(fname)
    nb = read_nb(fname)
    default = find_default_export(nb['cells'])
    if default is not None:
        default = os.path.sep.join(default.split('.'))
        if to_dict is None: _create_mod_file(Config().lib_path/f'{default}.py', fname)
    mod = get_nbdev_module()
    exports = [is_export(c, default) for c in nb['cells']]
    cells = [(i,c,e) for i,(c,e) in enumerate(zip(nb['cells'],exports)) if e is not None]
    for i,c,e in cells:
        fname_out = Config().lib_path/f'{e}.py'
        orig = ('#C' if e==default else f'#Comes from {fname.name}, c') + 'ell\n'
        code = '\n\n' + orig + '\n'.join(_deal_import(c['source'].split('\n')[1:], fname_out))
        # remove trailing spaces
        names = export_names(code)
        extra,code = extra_add(code)
        if to_dict is None: _add2add(fname_out, [f"'{f}'" for f in names if '.' not in f and len(f) > 0] + extra)
        mod.index.update({f: fname.name for f in names})
        code = re.sub(r' +$', '', code, flags=re.MULTILINE)
        if code != '\n\n' + orig[:-1]:
            if to_dict is not None: to_dict[fname_out].append((i, fname, code))
            else:
                with open(fname_out, 'a', encoding='utf8') as f: f.write(code)
        if f'{e}.py' not in mod.modules: mod.modules.append(f'{e}.py')
    save_nbdev_module(mod)

    if not silent: print(f"Converted {fname.name}.")
    return to_dict

#Cell
def notebook2script(fname=None, silent=False, to_dict=False):
    "Convert `fname` or all the notebook satisfying `all_fs`."
    # initial checks
    if os.environ.get('IN_TEST',0): return  # don't export if running tests
    if fname is None:
        reset_nbdev_module()
        files = [f for f in Config().nbs_path.glob('*.ipynb') if not f.name.startswith('_')]
    else: files = glob.glob(fname)
    d = collections.defaultdict(list) if to_dict else None
    for f in files: d = _notebook2script(f, silent=silent, to_dict=d)
    if to_dict: return d

#Cell
def _get_property_name(p):
    "Get the name of property `p`"
    if hasattr(p, 'fget'):
        return p.fget.func.__qualname__ if hasattr(p.fget, 'func') else p.fget.__qualname__
    else: return next(iter(re.findall(r'\'(.*)\'', str(p)))).split('.')[-1]

def get_name(obj):
    "Get the name of `obj`"
    if hasattr(obj, '__name__'):       return obj.__name__
    elif getattr(obj, '_name', False): return obj._name
    elif hasattr(obj,'__origin__'):    return str(obj.__origin__).split('.')[-1] #for types
    elif type(obj)==property:          return _get_property_name(obj)
    else:                              return str(obj).split('.')[-1]

#Cell
def qual_name(obj):
    "Get the qualified name of `obj`"
    if hasattr(obj,'__qualname__'): return obj.__qualname__
    if inspect.ismethod(obj):       return f"{get_name(obj.__self__)}.{get_name(fn)}"
    return get_name(obj)

#Cell
def source_nb(func, is_name=None, return_all=False):
    "Return the name of the notebook where `func` was defined"
    is_name = is_name or isinstance(func, str)
    index = get_nbdev_module().index
    name = func if is_name else qual_name(func)
    while len(name) > 0:
        if name in index: return (name,index[name]) if return_all else index[name]
        name = '.'.join(name.split('.')[:-1])

#Cell
_re_default_nb = re.compile(r'File to edit: dev/(\S+)\s+')
_re_cell = re.compile(r'^#Cell|^#Comes from\s+(\S+), cell')

#Cell
def _split(code):
    lines = code.split('\n')
    default_nb = _re_default_nb.search(lines[0]).groups()[0]
    s,res = 1,[]
    while _re_cell.search(lines[s]) is None: s += 1
    e = s+1
    while e < len(lines):
        while e < len(lines) and _re_cell.search(lines[e]) is None: e += 1
        grps = _re_cell.search(lines[s]).groups()
        nb = grps[0] or default_nb
        content = lines[s+1:e]
        while len(content) > 1 and content[-1] == '': content = content[:-1]
        res.append((nb, '\n'.join(content)))
        s,e = e,e+1
    return res

#Cell
def _relimport2name(name, mod_name):
    if mod_name.endswith('.py'): mod_name = mod_name[:-3]
    mods = mod_name.split(os.path.sep)
    i = last_index(Config().lib_name, mods)
    mods = mods[i:]
    if name=='.': return '.'.join(mods[:-1])
    i = 0
    while name[i] == '.': i += 1
    return '.'.join(mods[:-i] + [name[i:]])

#Cell
#Catches any from .bla import something and catches .bla in group 1, the imported thing(s) in group 2.
_re_loc_import = re.compile(r'(^\s*)from (\.\S*) import (.*)$')

#Cell
def _deal_loc_import(code, fname):
    def _replace(m):
        sp,mod,obj = m.groups()
        return f"{sp}from {_relimport2name(mod, fname)} import {obj}"
    return '\n'.join([_re_loc_import.sub(_replace,line) for line in code.split('\n')])

#Cell
def _script2notebook(fname, dic, silent=False):
    "Put the content of `fname` back in the notebooks it came from."
    if os.environ.get('IN_TEST',0): return  # don't export if running tests
    fname = Path(fname)
    with open(fname, encoding='utf8') as f: code = f.read()
    splits = _split(code)
    assert len(splits)==len(dic[fname]), f"Exported file from notebooks should have {len(dic[fname])} cells but has {len(splits)}."
    assert np.all([c1[0]==c2[1]] for c1,c2 in zip(splits, dic[fname]))
    splits = [(c2[0],c1[0],c1[1]) for c1,c2 in zip(splits, dic[fname])]
    nb_fnames = {Config().nbs_path/s[1] for s in splits}
    for nb_fname in nb_fnames:
        nb = read_nb(nb_fname)
        for i,f,c in splits:
            c = _deal_loc_import(c, str(fname))
            if f == nb_fname:
                l = nb['cells'][i]['source'].split('\n')[0]
                nb['cells'][i]['source'] = l + '\n' + c
        NotebookNotary().sign(nb)
        nbformat.write(nb, str(nb_fname), version=4)

    if not silent: print(f"Converted {fname.relative_to(Config().lib_path)}.")

#Cell
def script2notebook(fname=None, silent=False):
    if os.environ.get('IN_TEST',0): return
    dic = notebook2script(silent=True, to_dict=True)
    exported = get_nbdev_module().modules

    if fname is None:
        files = [f for f in Config().lib_path.glob('**/*.py') if str(f.relative_to(Config().lib_path)) in exported]
    else: files = glob.glob(fname)
    [ _script2notebook(f, dic, silent=silent) for f in files]

#Cell
import subprocess
from distutils.dir_util import copy_tree

#Cell
def diff_nb_script():
    "Print the diff between the notebooks and the library in `lib_folder`"
    lib_folder = Config().lib_path
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        copy_tree(Config().lib_path, d1)
        notebook2script(silent=True)
        copy_tree(Config().lib_path, d2)
        shutil.rmtree(Config().lib_path)
        shutil.copytree(d1, str(Config().lib_path))
        for d in [d1, d2]:
            if (Path(d)/'__pycache__').exists(): shutil.rmtree(Path(d)/'__pycache__')
        res = subprocess.run(['diff', '-ru', d1, d2], stdout=subprocess.PIPE)
        print(res.stdout.decode('utf-8'))