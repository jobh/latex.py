#!/usr/bin/env python3
r'''usage: latex.py [args] file [file2 ...]
OR:    python2.6 latex.py ...  (if python3 is not installed)

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

=== Optional arguments ===

    -o <file>
    --output <file>      Output filename [stdout]. If extension is .ps, .dvi
                         or .pdf, build document using latexmk (preprocessed
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
#from __future__ import unicode_literals
from __future__ import print_function, absolute_import, division

import sys
import os
import subprocess
import re
import itertools
import collections

########## Global variables ###############################
parser_scope = type('Dict', (dict,), {})()
parser_scope['parser_scope'] = parser_scope
def in_parser_scope(s=None):
    def wrap(f):
        global parser_scope
        parser_scope[s or f.__code__.co_name] = f
        return f
    return wrap

@in_parser_scope('_args')
class args:
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
    macro_prefix = '@'
    escape       = '{_}'
    dummy        = '{__}'
    pattern      = r'a-zA-Z0-9*'
    version      = 1.01

usage_count = collections.defaultdict(int)
parser_scope['usage_count'] = usage_count

########## Used by the @out definitions (see above) ###############
pending_output = []
def pop_pending_output():
    global pending_output
    if pending_output:
        pending_output.append('')
    ret = '\n'.join(pending_output)
    pending_output = []
    return ret

format_replacer = (re.compile(r'#\(([^)]+)\)'), r'%(\1)s')
@in_parser_scope('_format')
def format(s):
    replace_re, replace_with = format_replacer
    s = s.replace('%', '%%')
    s = replace_re.sub(replace_with, s)
    return s

@in_parser_scope('_output')
def output(s):
    pending_output.append(s)

###################################################################

# Return one argument, formatted as a python string.
def consume_arg(l):
    level = 0
    pos = 0
    for c in l[pos:]:
        if   c in ['{','[']: level += 1
        elif c in ['}',']']: level -= 1
        pos += 1
        if level == 0:
            (arg, rest_of_line) = l[1:pos-1], l[pos:]
            assert not '"""' in arg
            return ('r"""%s"""'%arg, rest_of_line)

# Return as many arguments as possible. Ignore spaces between arguments,
# and allow exactly one optional argument [] if it comes first. The optional
# argument is moved to the last position, to allow the standard "def a(x,y='')".
def consume_args(l):
    args = []
    optarg = None
    pos = 0
    while len(l) > pos and l[pos] == ' ':
        pos += 1
    if len(l) > pos and l[pos] == '[':
        (optarg,l) = consume_arg(l[pos:])
    while True:
        pos = 0
        while len(l) > pos and l[pos] == ' ':
            pos += 1
        if len(l) <= pos or l[pos] != '{':
            if optarg: args.append(optarg)
            return args, l
        (arg,l) = consume_arg(l[pos:])
        args.append(arg)

# Some text substitutions on the line, to simplify the rest of the parsing.
# These are NOT applied to in-line macros, only to python definitions etc.
replacers = [
    # Convert and format RHS literal strings
    #    return : \vec{#(x)}
    #--> return _format(r"""\vec{#(x)}""" % locals()
    #    del = : \nabla
    #--> del = _format(r"""\nabla""") % locals()
    (re.compile(r'^(\s*([%s]*\s*=|return))\s*:\s*(\S.*)$'%args.pattern),
     r'\1 _format(r"""\3""") % locals()'),
    # Convert reserved words. Only at beginning of line (outer scope).
    #    del = _format(r"""\nabla"") % locals()
    #--> parser_scope[r"del"] = ...
    (re.compile(r'^([%s]*)\s*='%args.pattern),
     r'parser_scope[r"\1"] ='),
    #    : \vec{#(x)}
    #--> _output(r"""\vec{%(x)s}""" % locals())
    (re.compile(r'^(\s*):\s*(.*)$'),
     r'\1_output(_format(r"""\2""") % locals())'), 
    ]

def fixup_line(l):
    for replace_re, replace_with in replacers:
        l = replace_re.sub(replace_with, l)
    return l

# Returns the index of a comment / line continuation, or None if not found
def comment_idx(l):
    if l[0] == '%':
        return 0
    cmatch = re.search(r'[^\\]%', l)
    return cmatch and cmatch.start()+1

@in_parser_scope('_escape')
def escape(line, count=-1):
    global args
    return line.replace(args.macro_prefix, args.escape, count)
def unescape(line):
    global args
    line = line.replace(args.escape, args.macro_prefix)
    # Remove space taken by macros that return nothing. It is complicated because we
    # do not want macros that expand to nothing to introduce new totally blank lines,
    # but blank lines in the original text should be preserved. Note also that l may
    # at this point contain multiple linebreaks.
    if args.dummy in line:
        l0 = line
        line = re.sub(r'^(\s*('+args.dummy+r'\s*)+\n)+',  r'', line)   # lines at the start
        line = re.sub(r'\n(\s*('+args.dummy+r'\s*)+\n)+', r'\n', line) # ... in the middle
        line = re.sub(r'(\n\s*('+args.dummy+r'\s*)+)+$',  r'\n', line) # ... at the end
        line = line.replace(args.dummy, '') # and finally handle lines with other non-whitespace
        if args.verbose >= 3:
            log('"%s"'%l0.replace('\n',r'\n'), '==>', '"%s"'%line.replace('\n', r'\n'))
    return line


_prev_prefix = None
@in_parser_scope('_log')
def log(*text):
    global prefix1, prefix2, _prev_prefix
    if prefix1 != _prev_prefix:
        prefix = prefix1
        _prev_prefix = prefix1
    else:
        prefix = prefix2
    print(prefix, *text, file=args.errf)


def exec_block(lines):
    global args, parser_scope
    if args.verbose >= 3:
        debuglines = '>>> '+lines.replace('\n', '\n>>> ')+'\n'
        args.errf.write(debuglines);
    try:
        exec(lines, parser_scope)
    except Exception as e:
        log(repr(e))
        print('------ code block: -------', file=args.errf)
        print(lines, file=args.errf)
        print('--------------------------', file=args.errf)
        raise

def parse(inf_name):
    global args, parser_scope

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

            if collected:
                l = collected+l
                collected = ''

            # Handle in-line macros. We need to save up enough lines to be certain that
            # all arguments are present (i.e., until braces are balanced and 
            # line continuations (%) are eaten).
            if args.macro_prefix in l:
                if '%' in l:
                    # line continuations?
                    idx = comment_idx(l)
                    if idx != None:
                        collected = l[:idx]
                        continue
                if l.count('{')>l.count('}') or l.count('[')>l.count(']'):
                    # balanced braces
                    collected = l
                    continue

                re_string = re.escape(args.macro_prefix)+r'([%s]*)[^%s]'%(args.pattern,args.pattern)

                # Run through line repeatedly until no more matches are found. This means
                # that a macro can use other macros, by repeated expansion.
                while True:
                    # Try to match a macro name (should be successful, but maybe not
                    # if e.g. the line ends with '\\'.
                    match = re.search(re_string, l)
                    if not match:
                        break

                    l_before_macro = l[:match.start()]
                    l_after_macro = l[match.end()-1:]
                    len_of_match = len(l) - len(l_after_macro) - len(l_before_macro)
                    comm = match.group(1) # the command (macro) name
                    comm_args = eval_str = ''
                    try:
                        comm_args,l_after_macro = consume_args(l_after_macro)
                        len_of_match = len(l) - len(l_after_macro) - len(l_before_macro)
                        comm_args = ','.join(comm_args)

                        l_in_macro = l[match.start():match.start()+len_of_match]
                        parser_scope['current_match'] = [''.join(output[-1:])+unescape(l_before_macro),
                                                         l_in_macro,
                                                         l_after_macro]

                        comm_obj = parser_scope[comm]
                        usage_count[comm] += 1
                        if isinstance(comm_obj, str):
                            # The definition is a format string
                            eval_str = 'r"""%s"""%%((%s))'%(comm_obj,comm_args)
                        else:
                            # The definition is a function. Protect reserved words
                            # by calling parser_scope['func'] instead of func.
                            eval_str = 'parser_scope[r"%s"](%s)'%(comm, comm_args)
                        try:
                            result = eval(eval_str, parser_scope) or args.dummy
                        except StopIteration:
                            result = escape(l_in_macro, 1)
                        if pending_output:
                            result = pop_pending_output() + result
                        if args.verbose >= 3:
                            log(l.rstrip().replace('\n', r'~'))
                            log(' '*match.start() + '^'*len_of_match)
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
                        result = escape(l_in_macro, 1)

                    l = '%s%s%s' % (l_before_macro,str(result),l_after_macro)

                # Replace any escape sequences by the original
                l = unescape(l)

            if l:
                output.append(l)

    return output

#################### Definitions used by the process-latex-commands mode ##################

# Three cases to handle:
# 1) \newcommand{\x}{text}
#   1: newcommand('\x', 'text')     --> ''
# 2) \newcommand{\x}[2]{text $#1^#2$}
#   1: newcommand('\x')             --> '\x'
#   2: x('text $#1^#2$', '2')       --> ''
# 3) \newcommand{\x}[3][+]{$#2^{#1#3}$}
#   1: newcommand('\x')             --> '\x'
#   2: x('2')                       --> '\x'
#   3: x('$#2^{#1#3}$', '+')        --> ''
#
# The last one, for example, results in a definition roughly equivalent to
# def x(arg1, arg2, arg3='+'):
#     return '$%(2)s^{%(1)s%(2)s}$' % {'2':arg1, '3':arg2, '1':arg3}

class latex_new_comm(object):
    def __init__(self, name, definition=None):
        if definition:
            # Case (1.1)
            self.finished = True
            self.set_definition(definition)
            self.set_nargs(0)
        else:
            # Case (2.1) or (3.1)
            self.finished = False
        self.name = name
        self.has_opt_arg = False

    def set_definition(self, definition):
        definition = definition.replace('%', '%%')
        self.definition = re.sub(r'#([0-9])', r'%(\1)s', definition)

    def set_nargs(self, nargs):
        self.arg_keys = [str(i+1) for i in range(nargs)]
        self.nargs = nargs

    def format(self, *args):
        if self.has_opt_arg:
            args = list(args)
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
        return self.definition % dict(zip(self.arg_keys, args))

    def __call__(self, *args):
        if self.finished:
            return self.format(*args)

        if len(args) == 1:
            # Case (3.2)
            self.set_nargs(int(args[0]))
            self.has_opt_arg = True
            return self.name    # definition still not finished, call me again

        (definition, nargs_or_opt_arg) = args
        if self.has_opt_arg:
            # Case (3.3)
            self.opt_arg = nargs_or_opt_arg
        else:
            # Case (2.2)
            self.set_nargs(int(nargs_or_opt_arg))
        self.set_definition(definition)
        self.finished = True

def latex_newcommand(name, definition=None):
    global args, parser_scope
    if parser_scope.get(name[1:]) == ignore:
        if args.verbose >= 3:
            print(r'++ Ignoring \newcommand{%s}'%name, file=sys.stderr)
        ignore()
    command = latex_new_comm(name, definition)
    old_cmd = parser_scope.get(name[1:])
    if old_cmd and args.verbose >= 2:
        print(r'++ Redefining %s'%name, file=sys.stderr)
    parser_scope[name[1:]] = command
    if not command.finished:
        return name             # finish definition in new_comm.__call__

def latex_renewcommand(name, definition=None):
    global args, parser_scope
    if parser_scope.get(name[1:]) == ignore:
        if args.verbose >= 3:
            print(r'++ Ignoring \renewcommand{%s}'%name, file=sys.stderr)
        ignore()
    if name[1:] in parser_scope:
        del parser_scope[name[1:]]
    return latex_newcommand(name, definition)

def latex_input(name):
    lines = parse(name+'.tex')
    if lines:
        lines[-1] = lines[-1].strip()
    # parse() has already processed the lines, don't do it again
    lines = map(escape, lines)
    return ''.join(lines)

_latex = {'environment': []}
parser_scope['_latex'] = _latex

def latex_usepackage(names, opt=None):
    if opt: opt = opt.split(',')
    else:   opt = []
    for name in names.split(','):
        _latex[name] = opt
    ignore()
def latex_documentclass(name, opt=None):
    if opt: opt = opt.split(',')
    else:   opt = []
    _latex['documentclass'] = name
    _latex['documentclass_opts'] = opt
    ignore()

def latex_begin(name, *args):
    _latex['environment'].append(name)
    ignore()
def latex_end(name):
    expected_name = _latex['environment'].pop()
    if expected_name != name:
        global prefix1
        print(prefix1, 'Expected "\end{%s}", not "%s"'%(expected_name, name), file=args.errf)
    ignore()

def set_latex_parse_mode():
    global args, parser_scope
    parser_scope['newcommand']    = latex_newcommand
    parser_scope['renewcommand']  = latex_newcommand
    parser_scope['input']         = latex_input
    parser_scope['usepackage']    = latex_usepackage
    parser_scope['documentclass'] = latex_documentclass
    parser_scope['begin']         = latex_begin
    parser_scope['end']           = latex_end
    args.verbose = 1
    args.macro_prefix = '\\'
############################################################################

############### Definitions used by the dependency-printing mode ###############
def latex_print(n, format, chained_cmd):
    def one_printer(*args):
        print(format%args[n])
        if chained_cmd:
            return chained_cmd(*args)
    def all_printer(*args):
        print('|'.join(args))
        if chained_cmd:
            return chained_cmd(*args)
    if n == None:
        return all_printer
    else:
        return one_printer

def set_print_mode(cmd, n=None, format='%s'):
    global args, parser_scope
    set_latex_parse_mode()
    parser_scope[cmd] = latex_print(n, format, parser_scope.get(cmd))
    args.output = False
##########################################################################

@in_parser_scope('_ignore')
def ignore(*args):
    if len(args) == 1 and hasattr(args[0], '__call__'):
        func = args[0]
        def f(*args):
            func(*args)
            ignore()
        return f
    else:
        raise StopIteration

@in_parser_scope()
def is_sentence_start():
    global parser_scope
    b = parser_scope['current_match'][0]
    # Check if text preceding match ends with a character that is not '.' or ':'
    if re.search(r'[^:.\s]\s*$', b):
        return False
    else:
        return True

@in_parser_scope()
def upcase_at_start(func_or_str):
    """Decorator (or function, if called with string) to upcase first character
    if it is at the beginning of a sentence."""
    def wrapper(*args, **kwargs):
        if isinstance(func_or_str, str):
            ret = func_or_str % args
        else:
            ret = func_or_str(*args, **kwargs)
        if is_sentence_start() and ret and isinstance(ret, str):
            ret = ret[0].upper()+ret[1:]
        return ret
    return wrapper

@in_parser_scope('_eval')
def do_eval(x):
    try:
        return str(eval(x))
    except:
        ignore()

def match_has_optional_parameter():
    global parser_scope, args
    m = parser_scope['current_match'][1]
    return re.match(r'.[%s]*[[]'%args.pattern, m)
    
@in_parser_scope()
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

@in_parser_scope()
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

@in_parser_scope()
def expect_version(expected):
    if args.version < expected:
        raise RuntimeError('latex.py v%.2f is too old; %.2f required' % (args.version, expected))
    if int(args.version) > int(expected):
        log('latex.py v%.2f may be too new; expected version %.2f' % (args.version, expected))


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
    global parser_scope
    builtin_macros = []
    builtin_hidden = []
    macros = []
    hidden = []
    glob_vals = list(globals().values())
    for key,val in parser_scope.items():
        if val in glob_vals or key in ['current_match', '__builtins__']:
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


import contextlib
@contextlib.contextmanager
def closing(f):
    try:
        yield f
    finally:
        if not f.isatty(): # <-- here
            f.close()

def main():
    global args
    parse_args()

    with closing(args.errf):
        if args.two_pass:
            for inf in args.infiles:
                parse(inf)
        with closing(args.outf):
            for inf in args.infiles:
                lines = parse(inf)
                if args.output:
                    args.outf.writelines(lines)

        if args.show_macros:
            show_macros()

        if args.build_type:
            def system(cmd):
                if args.verbose > 0:
                    print('>>>', cmd, file=args.errf)
                os.system(cmd)
            if any(os.path.exists(os.path.join(d,'latexmk')) for d in os.environ['PATH'].split(os.pathsep)):
                system("latexmk -f -quiet -%s %s" % (args.build_type, args.outf_name)) \
                    or system("grep -A15 -m1 '^!' %s.log" % args.base_name)
            else:
                print('*** Error: "latexmk" not found in PATH, skipping build.', file=args.errf)
                print('*** Use "-o %s" instead, and run %slatex on that one yourself.' \
                    % (args.outf_name, args.build_type), file=args.errf)

if __name__ == '__main__':
    main()
