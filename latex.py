#!/usr/bin/env python
r'''usage: latex.py [args] file [file2 ...]

Latex preprocessor. There are three main use cases:

1) Write macros in python. Because it's simpler? More powerful libraries?
   Use '@' instead of '\' as macro prefix. Typical build process:
       python parse.py -i macros.py -o manuscript.pdf manuscript.tex

2) Expand user-defined macros in text, because some journals don't like these.
   Uses '\' as macro prefix, but replaces as many as possible with their
   expansions. Add "-e 'input=ignore(input)'" after -L to leave \input
   statements alone (they are still parsed for \newcommand; '-I input' or
   '-e input=ignore' stops parsing too).
       python parse.py -L -o manuscript.texp manuscript.tex

3) Parse a latex file to determine its dependencies, for use in makefiles etc.
       deps=$(python parse.py \
              -P includegraphics:1:%s.pdf \
              -P input:1:%s.tex \
              -P bibliography:1:%s.bib \
              manuscript.tex)
   (or if python macros are used:)
       deps=$(python parse.py -i macros.py manuscript.tex | python parse.py \
              -P includegraphics:1:%s.pdf \
              -P bibliography:1:%s.bib)

Note that python3 syntax is used.

=== Optional arguments ===

    -o <file>
    --output <file>      Output filename [stdout]. If extension is .ps, .dvi
                         or .pdf, build this file using *latex (preprocessed
                         file will then be called <basename>.texp).
    -v <level>
    --verbose <level>    0: print nothing, 1: print errors except KeyError,
                         [2]: print all errors, 3: print a lot.
    -M
    --show-macros        After execution, list the defined macros.

    -B
    --show-blocks        Leave exec'ed blocks in the output, commented out

    -a <level>
    --abort <level>      Abort on any error that the same verbosity level
                         would print (with -v). It should normally not be set
                         higher than the verbosity.
    -i <file>
    --include <file>     Execute python file in the parser namespace. Some
                         substitutions are done on the input file (it is
                         treated like an "%@" exec block, only without the
                         prefix).
    -e <expr>
    --expression <expr>  Execute an expression in the parser namespace.

    -q
    --quiet              Don't output anything. Same effect as '-o /dev/null'.

    -L
    --parse-latex-commands
                         Parse a latex file. Understands '\newcommand' and
                         '\input'. The effect is to expand any user-defined
                         latex macros in the text.
                         Implies '-v 1', since we expect a lot of KeyErrors.
    -P <cmd>
    --print-cmd <cmd>    Make the given command print its arguments.
                         Implies '-L -q', and additionally defines a macro
                         '\<cmd>' that simply prints its argument to stdout.
                         Can also use <cmd>:<n> which prints only the n'th
                         argument, or <cmd>:<n>:<format_str> which applies
                         <format_str> to print the argument. See (3) above.
    -I <cmd>
    --ignore <cmd>       Ignore this macro (leave it unexpanded).
                         Useful also to silence unwanted warnings, for example
                         in e-mail addresses (use '-I gmail -I simula'). Note
                         that this is not needed for correctness, since
                         '@gmail' will just raise KeyError and be left alone.
                         Alternatively, use '-v 1' to ignore all KeyErrors.
    -2
    --two-pass           Two passes over the input file, allowing the first
                         pass to collect information for the whole file.
    -V
    --version            Print the version number. The major (integer) part
                         is bumped when incompatible changes are made.
    -h
    --help               Print this text and more

=== Known bugs / limitations ===

Text passed to macros may not contain three double quotes (""") in a row or
end with a bare backslash (\).

=== License, author ===

latex.py was written in 2010 by Joachim B Haga (jobh@simula.no).
It is licensed under GPL v2 (or later).
'''

# Make python2.6 work like python3
#from __future__ import unicode_literals # doesn't work right: r'\u' gives error
from __future__ import print_function, absolute_import, division

import sys
import os
import subprocess
import re
import itertools
import collections
import contextlib
try:
    import __builtin__
except ImportError:
    import builtins as __builtin__ # python3

########## Scopes ###############################

# Note that the scopes are a bit weird. In effect, attributes containing
# underscores are shared between all scopes. See 
# examples/simple/multi_prefix.tex for example of use.
class __macros:
    pass
main_parser_scope = {'__builtin__': __builtin__, '__macros__': __macros()}
parser_scopes = {} # populated in get_scope()

def builtin(f):
    """Decorator which adds the function (or class) to the
    parser scopes."""
    global main_parser_scope
    if hasattr(__builtin__, f.__name__):
        raise RuntimeError('Shadowing builtin name %s', f.__name__)
    setattr(__builtin__, f.__name__, f)
    return f

@builtin
def get_scope(x=None):
    global main_parser_scope, parser_scopes
    if not x:
        return main_parser_scope
    if not parser_scopes:
        parser_scopes[x] = main_parser_scope
    if not x in parser_scopes:
        new_scope = main_parser_scope.copy()
        remove_macros_from(new_scope)
        new_scope['__macros__'] = __macros()
        parser_scopes[x] = new_scope
        if not x in args.macro_prefix:
            args.macro_prefix.append(x)
    else:
        new_scope = parser_scopes[x]
    if new_scope != main_parser_scope:
        # ensure the hidden attributes are the same everywhere
        copy_hidden(main_parser_scope, new_scope)
    return new_scope

@builtin
def get_macro(x=None, scope=None):
    scope = get_scope(scope)
    macros = scope['__macros__']
    if x is None:
        return macros
    macro = getattr(macros, x, None)
    if macro is None:
        macro = scope.get(x)
    return macro

@builtin
def call(x, *args, **kwargs):
    if isinstance(x, str):
        return prepare_format(x).format(*args, **kwargs)
    else:
        return x(*args, **kwargs)


@builtin
@contextlib.contextmanager
def scope(x):
    orig_scope = get_scope()
    new_scope = get_scope(x)
    if orig_scope == new_scope:
        yield orig_scope
    else:
        scope_copy = orig_scope.copy()
        try:
            # set macros in the running scope to those in x
            remove_macros_from(orig_scope)
            copy_macros(new_scope, orig_scope)
            yield orig_scope
        finally:
            # make x identical to the running scope (including hidden)
            new_scope.clear()
            copy_macros(orig_scope, new_scope)
            # reset macros in the running scope (but leave hidden alone)
            remove_macros_from(orig_scope)
            copy_macros(scope_copy, orig_scope)

@contextlib.contextmanager
def eval_scope(x):
    global main_parser_scope
    orig_scope = get_scope()
    new_scope = get_scope(x)
    try:
        main_parser_scope = new_scope
        yield new_scope
    finally:
        main_parser_scope = orig_scope

@builtin
def current_match(idx=1):
    if (idx == 0):
        out, cur = _current_match[0]
        return bracket_unescape(''.join(out[-1:]) + unescape(cur))
    return bracket_unescape(_current_match[idx])

def remove_macros_from(s):
    for k in list(s.keys()):
        if not '_' in k or k in ['__macros__', '__missing__']:
            del s[k]
def copy_macros(fro, to):
    for k in fro.keys():
        if not '_' in k or k in ['__macros__', '__missing__']:
            to[k] = fro[k]
def copy_hidden(fro, to):
    for k in fro.keys():
        if '_' in k and k not in ['__macros__', '__missing__']:
            to[k] = fro[k]

########## Arguments #####################

@builtin
class args(object):
    __init__     = None         # disallow instantiation
    build_type   = None
    outf         = sys.stdout
    errf         = sys.stderr
    verbose      = 2
    abort        = 1
    output       = True
    show_macros  = False
    show_blocks  = False
    two_pass     = False
    block_prefix = '%@'
    macro_prefix = ['@']
    escape       = ('{_}', '{__}', '{___}', '{____}')
    dummy        = '{^}'
    pattern      = r'a-zA-Z0-9*'
    version      = 2.00

    bracket_words  = [r'\left[', r'\right]', 
                      r'\left{', r'\right}',
                      r'\{', r'\}',
                      r'\%']
    bracket_escape = '_{_%d}'
    custom_replacers = []


usage_count = collections.defaultdict(int)
get_scope()['usage_count'] = usage_count

##### Support functions for the ':' string syntax (see fixup_line) ######

pending_output = []
def pop_pending_output():
    global pending_output
    if pending_output:
        pending_output.append('')
    ret = '\n'.join(pending_output)
    pending_output = []
    return ret

format_replacer = (re.compile(r'#\(([^)]+)\)'), r'{\1}')
format_replacer2 = (re.compile(r'#\(([^0-9)]+)\)'), r'{\1}')
@builtin
def prepare_format(s, kwargs_only=False):
    replace_re, replace_with = format_replacer2 if kwargs_only else format_replacer
    s = s.replace('{', '{{').replace('}', '}}')
    s = replace_re.sub(replace_with, s)
    return s

@builtin
def output(s):
    pending_output.append(s)

#### Parsing arguments. Not easily done with regexps because of possible nesting. #####

# Return one argument, formatted as a python string.
def consume_arg(l, brak):
    level = 0
    pos = 0
    for c in l:
        if   c == brak[0]: level += 1
        elif c == brak[1]: level -= 1
        pos += 1
        if level == 0:
            (arg, rest_of_line) = l[1:pos-1], l[pos:]
            assert not '"""' in arg
            return ('r"""%s"""'%arg, rest_of_line)
    raise TypeError('Argument not closed')

# Return as many arguments as possible. Ignore spaces between arguments,
# and allow exactly one optional argument [] if it comes first. The optional
# argument is moved to the last position, to allow the standard "def a(x,y='')".
# The awkward implementation is to avoid eating spaces unless they are followed
# by an argument (but maybe we should never eat spaces?)
def consume_args(l):
    args = []
    optarg = None
    pos = 0
    while len(l) > pos and l[pos] == ' ':
        pos += 1
    if len(l) > pos and l[pos] == '[':
        (optarg,l) = consume_arg(l[pos:], '[]')
    while True:
        pos = 0
        while len(l) > pos and l[pos] == ' ':
            pos += 1
        if len(l) <= pos or l[pos] != '{':
            if optarg: args.append(optarg)
            return args, l
        (arg,l) = consume_arg(l[pos:], '{}')
        args.append(arg)

####### Support functions for exec'ing code blocks #############

# Some text substitutions on the line, to simplify the rest of the parsing.
# These are NOT applied to in-line macros, only to python definitions etc.
replacers = [
    # Convert and format RHS literal strings
    #    return : \vec{#(x)}
    #--> return prepare_format(r"""\vec{#(x)}""", True).format(**locals())
    #    del = : \nabla
    #--> del = prepare_format(r"""\nabla""", True).format(**locals())
    (re.compile(r'^(\s*([%s_.]*\s*=|return))\s*:\s*(\S.*)$'%args.pattern),
     r'\1 __builtin__.prepare_format(r"""\3""", kwargs_only=True).format(**__builtin__.locals())'),
    # Convert reserved words. Only at beginning of line (outer scope).
    #    del = prepare_format(r"""\nabla"", True).format(**locals())
    #--> get_scope()[r"del"] = ...
    (re.compile(r'^([%s]*)\s*='%args.pattern),
     r'__builtin__.get_scope()[r"\1"] ='),
    #    : \vec{#(x)}
    #--> output(prepare_format(r"""\vec{%(x)s}""").format(**locals()))
    (re.compile(r'^(\s*):\s*(.*)$'),
     r'\1__builtin__.output(__builtin__.prepare_format(r"""\2""").format(**__builtin__.locals()))'), 
    ]

def fixup_line(l):
    for replace_re, replace_with in replacers:
        l = replace_re.sub(replace_with, l)
    return l

warned = set(['input'])
def exec_block(lines):
    if args.verbose >= 3:
        debuglines = '>>> '+lines.replace('\n', '\n>>> ')+'\n'
        args.errf.write(debuglines);
    try:
        exec(lines, get_scope())
        if args.verbose >= 1:
            for k in get_scope().keys():
                if hasattr(__builtin__, k) and not k in warned:
                    log('Warning: %s shadows builtin'%k)
                warned.add(k)
    except Exception as e:
        log(repr(e))
        print('------ code block: -------', file=args.errf)
        print(lines, file=args.errf)
        print('--------------------------', file=args.errf)
        raise

######### Misc. support functions #################

@builtin
def escape(line):
    global args
    for a,b in zip(args.macro_prefix, args.escape):
        line = line.replace(a,b)
    return line
def unescape(line):
    global args
    for a,b in zip(args.escape, args.macro_prefix):
        line = line.replace(a,b)
    # Remove space taken by macros that return nothing. It is complicated because we
    # do not want macros that expand to nothing to introduce new totally blank lines,
    # but blank lines in the original text should be preserved. Note also that line may
    # at this point contain multiple linebreaks.
    if args.dummy in line:
        l0 = line
        dummy = re.escape(args.dummy)
        line = re.sub(r'^(\s*('+dummy+r'\s*)+\n)+',  r'', line)   # lines at the start
        line = re.sub(r'\n(\s*('+dummy+r'\s*)+\n)+', r'\n', line) # ... in the middle
        line = re.sub(r'(\n\s*('+dummy+r'\s*)+)+$',  r'\n', line) # ... at the end
        line = line.replace(args.dummy, '') # and finally handle lines with other non-whitespace
        if args.verbose >= 3:
            log('"%s"'%l0.replace('\n',r'\n'), '==>', '"%s"'%line.replace('\n', r'\n'))
    return line

def bracket_escape(line):
    for i,kw in enumerate(args.bracket_words):
        line = line.replace(kw, args.bracket_escape%i)
    return line
def bracket_unescape(line):
    for i,kw in enumerate(args.bracket_words):
        line = line.replace(args.bracket_escape%i, kw)
    return line

_prev_prefix = None
@builtin
def log(*text):
    global prefix1, prefix2, _prev_prefix
    if prefix1 != _prev_prefix:
        prefix = prefix1
        _prev_prefix = prefix1
    else:
        prefix = prefix2
    print(prefix, *text, file=args.errf)


######### The actual parsing / preprocessing takes place here #########

def parse(inf_name):
    output = []
    lines = ''
    collected = ''
    consuming = False
    if inf_name == '-':
        inf = sys.stdin
        inf_name = 'sys.stdin'
    else:
        inf = open(inf_name)

    with inf:
        for lno,l in enumerate(itertools.chain(inf, [''])):
            lno += 1

            global prefix1, prefix2
            prefix1 = inf_name+' '+str(lno)+':'
            prefix2 = ' '*(len(prefix1)-1)+':'

            # Handle {%@ ... }%@. We need to save up a full block of code before
            # exec'ing.
            if l.startswith('{'+args.block_prefix):
                consuming = True
                continue
            elif consuming:
                if l.startswith('}'+args.block_prefix):
                    consuming = False
                    exec_block(lines)
                    lines = ''
                    l = pop_pending_output()
                else:
                    new_l = fixup_line(l)
                    lines += new_l
                    if args.show_blocks:
                        if l == new_l:
                            output.append(args.block_prefix+l)
                        else:
                            output.append('%-'+l)
                            output.append('%+'+new_l)
                    continue

            # Handle %@ lines. We need to save up a full block before exec'ing.
            if l.startswith(args.block_prefix):
                l = l[len(args.block_prefix):]
                new_l = fixup_line(l)
                lines += new_l
                if args.show_blocks:
                    if l == new_l:
                        output.append(args.block_prefix+l)
                    else:
                        output.append('%-'+l)
                        output.append('%+'+new_l)
                continue
            elif lines:
                exec_block(lines)
                lines = ''
                collected = pop_pending_output()

            for func in args.custom_replacers:
                l = func(l)

            if collected:
                l = collected+l
                collected = ''

            # Handle in-line macros. We need to save up enough lines to be certain that
            # all arguments are present (i.e., until braces are balanced and 
            # line continuations (%) are eaten).
            if any(prefix in l for prefix in args.macro_prefix):
                if '%' in l:
                    collected = l[:l.index('%')]
                    continue
                l = bracket_escape(l)

                re_string = r'[%s]([%s]*)[^%s]' \
                    % (re.escape(''.join(args.macro_prefix)), args.pattern, args.pattern)

                # Run through line repeatedly until no more matches are found. This means
                # that a macro can use other macros, by repeated expansion.
                while True:
                    # Try to match a macro name (should be successful, but maybe not
                    # if e.g. the line ends with '\\'.
                    match = re.search(re_string, l)
                    if not match:
                        break

                    l_before_macro = l[:match.start()]
                    len_of_match = match.end()-1-match.start()
                    l_after_macro = l[match.end()-1:]
                    comm = match.group(1) # the command (macro) name
                    comm_args = eval_str = ''
                    try:
                        try:
                            comm_args,l_after_macro = consume_args(l_after_macro)
                        except TypeError:
                            # An unclosed argument was seen. Retry with next line appended.
                            collected = l
                            l = ''
                            break
                        l_in_macro = l[match.start():len(l)-len(l_after_macro)]
                        len_of_match = len(l_in_macro)
                        comm_args = ','.join(comm_args)
                        m_prefix = l_in_macro[0]
                        with eval_scope(m_prefix):
                            global _current_match
                            _current_match = [(output, l_before_macro),
                                              l_in_macro,
                                              l_after_macro]
                            scope = get_scope()
                            comm_obj = get_macro(comm)
                            if comm_obj is None:
                                comm_obj = scope.get('__missing__')
                                if comm_obj is not None:
                                    comm_args = 'r"""%s""",'%comm + comm_args
                                    comm = '__missing__'
                            if comm_obj is None:
                                raise KeyError(comm)
                            usage_count[comm] += 1

                            eval_str = '__builtin__.call(__builtin__.get_macro(r"%s"),%s)'%(comm, comm_args)

                            try:
                                result = str(eval(eval_str, get_scope()) or args.dummy)
                            except StopIteration:
                                result = escape(l_in_macro[0]) + l_in_macro[1:]

                            if pending_output:
                                result = pop_pending_output() + result
                            if args.verbose >= 3:
                                log(l.rstrip().replace('\n', r'~'))
                                log(' '*match.start() + '^'*len(l_in_macro))
                                log('>>>', eval_str, '==> """%s"""'%result)
                    except Exception as e:
                        if isinstance(e, KeyError) and e.args[0]==comm: severity = 2
                        else:                                           severity = 1

                        if args.verbose >= severity:
                            log(l.rstrip().replace('\n', r'~'))
                            log(' '*match.start() + '^'*len_of_match)
                            for s in match.group(0), comm_args, eval_str, repr(e):
                                if s:
                                    log('!!!', s)

                        if args.abort >= severity:
                            raise

                        # Replace the first prefix by an escape sequence, so that we don't try
                        # to expand this (failed) macro again.
                        result = escape(l_in_macro[0]) + l_in_macro[1:]

                    if args.verbose >= 1 and l_in_macro in result and not l_in_macro in warned:
                        log('Possible recursion in %s->%s'% (l_in_macro,result))
                        warned.add(l_in_macro)
                    l = '%s%s%s' % (l_before_macro, bracket_escape(str(result)), l_after_macro)

                # Replace any escape sequences by the original
                l = unescape(l)
                l = bracket_unescape(l)

            if l:
                output.append(l)

    if collected:
        raise RuntimeError('Argument not closed, starting at %s:%d\n>>> '
                           % (inf_name,lno-collected.count('\n')-3)
                           +collected.split('\n')[0])
    return output

########## Definitions used by the process-latex-commands (-L) mode ###########

# Parsing latex command definitions. There are three cases to handle, and the
# idiosyncratic placement of optional parameters makes it complicated to do
# in the current framework. But hey, it's a challenge... The definition is
# done in up to three stages:
#                                       ret:      remaining text:
# 1) \newcommand{\x}{text}
#   1: newcommand('\x', 'text')     --> ''
# 2) \newcommand{\x}[2]{text $#1^#2$}
#   1: newcommand('\x')             --> '\x'  --> '\x[2]{text$#1^#2$}'
#   2: x('text $#1^#2$', '2')       --> ''
# 3) \newcommand{\x}[3][+]{$#2^{#1#3}$}
#   1: newcommand('\x')             --> '\x'  --> '\x[3][+]{$#2^{#1#3}$}'
#   2: x('3')                       --> '\x'  --> '\x[+]{$#2^{#1#3}$}'
#   3: x('$#2^{#1#3}$', '+')        --> ''
#
# The last one, for example, results in a definition roughly equivalent to
# def x(arg1, arg2, arg3='+'):
#     return '$%(2)s^{%(1)s%(3)s}$' % {'2':arg1, '3':arg2, '1':arg3}

class latex_new_comm(object):
    r"""A class to hold the state of the \newcommand definition."""
    def __init__(self, name, definition=None):
        if definition:
            # Case (1.1)
            self.finished = True
            self.set_definition(definition)
            self.nargs = 0
        else:
            # Case (2.1) or (3.1)
            self.finished = False
        self.name = name
        self.has_opt_arg = False

    def set_definition(self, s):
        s = s.replace('{', '{{').replace('}', '}}')
        self.definition = re.sub(r'#([0-9])', r'{\1}', s)

    def format(self, *args):
        args = list(args)
        if self.has_opt_arg:
            if len(args) == self.nargs-1:
                args = [self.opt_arg] + args
            else:
                args = [args[-1]] + args[:-1]
        if len(args) < self.nargs:
            raise RuntimeError('%s called with only %d args' % (self.name, len(args)))
        if len(args) > self.nargs:
            for arg in args[self.nargs:]:
                if arg != '':
                    raise RuntimeError('%s called with extra arg "%s"' % (self.name, arg))
        args = [None]+args
        return self.definition.format(*args)

    def __call__(self, *args):
        if self.finished:
            return self.format(*args)

        if len(args) == 1:
            # Case (3.2)
            self.nargs = int(args[0])
            self.has_opt_arg = True
            return self.name    # definition still not finished, call me again

        (definition, nargs_or_opt_arg) = args
        if self.has_opt_arg:
            # Case (3.3)
            self.opt_arg = nargs_or_opt_arg
        else:
            # Case (2.2)
            self.nargs = int(nargs_or_opt_arg)
        self.set_definition(definition)
        self.finished = True

def latex_newcommand(name=None, definition=None, redefine=False):
    if name is None:
        if args.verbose >= 3:
            log(r'Ignoring \newcommand, not on standard form (no proper argument)')
        ignore()
    # Check if the command is one that is explicitly ignored by user
    if get_macro(name[1:]) == ignore:
        if args.verbose >= 3:
            log(r'Ignoring \newcommand{%s}'%name)
        ignore()
    command = latex_new_comm(name, definition)
    old_cmd = get_macro(name[1:])
    if not redefine and old_cmd and args.verbose >= 2 and args.two_pass != 2:
        log('Redefining %s'%name)
    setattr(get_macro(), name[1:], command)
    if not command.finished:
        return name             # finish definition in new_comm.__call__

def latex_renewcommand(name, definition=None):
    return latex_newcommand(name, definition, redefine=True)

def latex_input(name):
    lines = parse(name+'.tex')
    if lines:
        lines[-1] = lines[-1].strip()
    # parse() has already processed the lines, don't do it again
    lines = map(escape, lines)
    return ''.join(lines)


# _latex holds various info about the document; the document class, 
# any loaded packages, the current environment stack, ...
_latex = {'environment': []}
get_scope()['_latex'] = _latex

@builtin
def latex_usepackage(names, opt=None):
    if opt: opt = opt.split(',')
    else:   opt = []
    for name in names.split(','):
        _latex[name] = opt
    ignore()
@builtin
def latex_documentclass(name, opt=None):
    if opt: opt = opt.split(',')
    else:   opt = []
    _latex['documentclass'] = name
    _latex['documentclass_opts'] = opt
    ignore()

@builtin
def latex_begin(name, *args):
    _latex['environment'].append(name)
    ignore()
@builtin
def latex_end(name):
    expected_name = _latex['environment'].pop()
    if expected_name != name:
        global prefix1
        log(prefix1, 'Expected "\end{%s}", not "%s"'%(expected_name, name))
    ignore()

def set_latex_parse_mode():
    args.verbose = 1
    args.macro_prefix[0] = '\\'
    macros = get_macro()
    macros.newcommand    = latex_newcommand
    macros.renewcommand  = latex_renewcommand
    macros.input         = latex_input
    macros.usepackage    = latex_usepackage
    macros.documentclass = latex_documentclass
    macros.begin         = latex_begin
    macros.end           = latex_end
############################################################################

############### Definitions used by the dependency-printing mode ###############
def latex_print(n, format, chained_cmd):
    def printer(*args, **kwargs):
        if n is None:
            print('|'.join(args))
        else:
            print(format%args[n])
        if chained_cmd:
            return chained_cmd(*args, **kwargs)
    return printer

def set_print_mode(cmd, n=None, format='%s'):
    args.output = False
    scope = get_scope()
    if hasattr(get_macro(), cmd):
        where = get_macro().__dict__
    elif cmd in scope:
        where = scope
    elif hasattr(scope['__builtin__'], cmd):
        where = scope['__builtin__'].__dict__
    else:
        where = scope
    old_cmd = where.get(cmd)
    where[cmd] = latex_print(n, format, old_cmd)

##########################################################################

############### Utility functions ###############
@builtin
def ignore(*args):
    if len(args) == 1 and hasattr(args[0], '__call__'):
        func = args[0]
        def f(*args):
            func(*args)
            ignore()
        return f
    else:
        raise StopIteration

@builtin
def is_sentence_start():
    b = current_match(0)
    # Check if text preceding match ends with a character that is not '.' or ':'
    if re.search(r'[^:.\s]\s*$', b):
        return False
    else:
        return True

@builtin
def upcase_at_start(func_or_str):
    """Decorator (or function, if called with string) to upcase first character
    if it is at the beginning of a sentence."""
    def wrapper(*args, **kwargs):
        ret = call(func_or_str, *args, **kwargs)
        if is_sentence_start() and ret and isinstance(ret, str):
            ret = ret[0].upper()+ret[1:]
        return ret
    return wrapper

def match_has_optional_parameter():
    m = current_match()
    return re.match(r'.[%s]*[[]'%args.pattern, m)
    
@builtin
def opt_kwargs(func):
    """Decorator to allow calling a function like \func[key=val,other=foo]{text}."""
    def wrapper(*args):
        kwargs = {}
        if match_has_optional_parameter():
            for kwarg in args[-1].split(','):
                try:
                    key,val = kwarg.split('=',1)
                    kwargs[key] = val
                except:
                    kwargs[kwarg] = ''
            args = args[:-1]
        return func(*args, **kwargs)
    return wrapper

@builtin
def shell_eval(cmd):
    import subprocess
    if isinstance(cmd, str):
        cmd = cmd.split()
    try:
        cmd = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except:
        print(cmd, file=args.errf)
        raise
    return cmd.communicate()[0].decode()

@builtin
def expect_version(expected):
    if args.version < expected:
        raise RuntimeError('latex.py v%.2f is too old; %.2f required' % (args.version, expected))
    if int(args.version) > int(expected):
        log('latex.py v%.2f may be too new; expected version %.2f' % (args.version, expected))


@builtin
def ensure_math(func):
    is_math = ['equation', 'eqnarray', 'align', 'equation*', 'eqnarray*']
    def wrapper(*args, **kwargs):
        result = call(func, *args, **kwargs)
        for env in reversed(_latex['environment']):
            if env in is_math:
                return result
        return r'\ensuremath{%s}' % result
    return wrapper

##########################################################################
# Command-line invocation
##########################################################################

def parse_args():
    global args

    if len(sys.argv) <= 1:
        print(__doc__)
        sys.exit(1)

    idx = 1
    while idx < len(sys.argv):
        arg = sys.argv[idx]
        if arg in ['-o', '--output']:
            idx += 1
            args.outf_name = sys.argv[idx]
            args.base_name, ext = os.path.splitext(args.outf_name)
            if ext in ['.dvi', '.pdf', '.ps']:
                args.build_type = ext[1:]
                args.outf_name = args.base_name+'.texp'
            args.outf = open(args.outf_name, 'w')
        elif arg in ['-v', '--verbose']:
            idx += 1
            args.verbose = int(sys.argv[idx])
        elif arg in ['-M', '--show-macros']:
            args.show_macros = True
        elif arg in ['-B', '--show-blocks']:
            args.show_blocks = True
        elif arg in ['-a', '--abort']:
            idx += 1
            args.abort = int(sys.argv[idx])
        elif arg in ['-i', '--include']:
            idx += 1
            code = map(fixup_line, open(sys.argv[idx]).readlines())
            exec_block(''.join(code))
        elif arg in ['-e', '--expression']:
            idx += 1
            code = fixup_line(sys.argv[idx])
            exec_block(code)
        elif arg in ['-q', '--quiet']:
            args.output = False
        elif arg in ['-L', '--parse-latex-commands']:
            set_latex_parse_mode()
        elif arg in ['-P', '--print-cmd']:
            idx += 1
            cmd = sys.argv[idx].split(':')
            if len(cmd) == 1:
                set_print_mode(cmd[0])
            elif len(cmd) == 2:
                set_print_mode(cmd[0], int(cmd[1])-1)
            elif len(cmd) == 3:
                set_print_mode(cmd[0], int(cmd[1])-1, cmd[2])
        elif arg in ['-2', '--two-pass']:
            args.two_pass = True
        elif arg in ['-h', '--help']:
            print(__doc__)
            sys.exit(0)
        elif arg in ['-V', '--version']:
            print('%.2f'%args.version)
            sys.exit(0)
        else:
            break
        idx += 1

    args.infiles = sys.argv[idx:]

def show_macros():
    builtin_macros = []
    builtin_hidden = []
    macros = []
    hidden = []
    glob_vals = list(globals().values())
    for key,val in get_scope().items():
        if val in glob_vals or key == '__builtins__':
            if '_' in key:
                builtin_hidden.append(key)
            else:
                if not key in usage_count:
                    key += ' (unused)'
                builtin_macros.append(key)
        else:
            if '_' in key:
                hidden.append(key)
            else:
                if not key in usage_count:
                    key += ' (unused)'
                macros.append(key)

    print('Global (hidden):', ', '.join(sorted(builtin_hidden)), file=args.errf)
    print('User (hidden):', ', '.join(sorted(hidden)), file=args.errf)
    print('Global:', ', '.join(sorted(builtin_macros)), file=args.errf)
    print('User:', ', '.join(sorted(macros)), file=args.errf)
    print(dir(get_scope()['__macros__']))

    for s in args.macro_prefix[1:]:
        macros = []
        for key in get_scope(s).keys():
            if not '_' in key:
                macros.append(key)
        print('Scope %s:'%s, ', '.join(sorted(macros)), file=args.errf)
        print(dir(get_scope(s)['__macros__']))

import contextlib
@contextlib.contextmanager
def closing(f):
    try:
        yield f
    finally:
        if not f.isatty(): # <-- here
            f.close()

def in_path(cmd):
    return any(os.path.exists(os.path.join(d, cmd)) for d in os.environ['PATH'].split(os.pathsep))

def fgrep_file(string, fname):
    with open(fname) as f:
        for l in f:
            if l.startswith(string):
                return True

def hash_file(fname):
    import hashlib
    m = hashlib.md5()
    with open(fname, 'rb') as f:
        for l in f:
            m.update(l)
    return m.digest()

def build_latex():
    """Run *latex/bibtex until .aux file no longer changes (max 5 times)."""
    global args
    def system(cmd, N):
        if args.verbose > 0:
            print('[%d]'%(N+1), cmd, file=args.errf)
        return os.system(cmd)
    if args.build_type == 'dvi':
        latex = 'latex'
    else:
        latex = args.build_type + 'latex'
    if in_path(latex):
        aux_fname = '%s.aux' % args.base_name
        try:
            aux_hash = hash_file(aux_fname)
        except:
            aux_hash = None
        for i in range(5):
            if system('%s -interaction=batchmode %s >/dev/null' % (latex, args.outf_name), i):
                print('=== Error in build:')
                system("grep -A15 -m1 '^!' %s.log" % args.base_name, i)
                sys.exit(1)
            new_hash = hash_file(aux_fname)
            if new_hash == aux_hash:
                print('=== No change in %s; build finished' % aux_fname)
                break
            else:
                aux_hash = new_hash
            if i == 0 and fgrep_file(r'\bibdata{', aux_fname):
                system('bibtex %s' % args.base_name, i)
    else:
        print('*** Error: "%s" not found in PATH, skipping build.' % latex, file=args.errf)
        print('*** Use "-o %s" instead, and run latex on that one yourself.' % args.outf_name,
              file=args.errf)

def main():
    global args
    parse_args()

    with closing(args.errf):
        if args.two_pass:
            for inf in args.infiles:
                parse(inf)
            args.two_pass = 2
        with closing(args.outf):
            for inf in args.infiles:
                lines = parse(inf)
                if args.output:
                    args.outf.writelines(lines)

        if args.show_macros:
            show_macros()
        if args.build_type:
            build_latex()

if __name__ == '__main__':
    v = eval('%s.%s' % sys.version_info[:2])
    if v < 2.6:
        print('python version 2.6 or higher required (%.1f found)' % v, file=sys.stderr)
        sys.exit(1)
    main()
