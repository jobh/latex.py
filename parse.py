"""
The rules:
-- lines starting with %@ are executed normally in python
-- same for lines between "%@{" and "%@}"
-- execution happens after a block
-- can be redefined by "%@ RAW='%%%'" which takes hold after block

-- these are used to define MACROS as python functions
-- replaced by the RETURN VALUE of the function
-- the 'print' goes to stdout, possibly for debugging
%@def middle(a,b,c):
%@    print '% picking option 2 of 3'
%@    return b
-> % picking option 2 of 3

--- Typical definitions are like the following. These work exactly
--- the same, roman2 is only useful for simple substitutions though.
%@roman1 = lambda x,y: r'\mathrm{%s/%s}'%(x,y)
%@roman2 = r'\mathrm{%s/%s}'

--- more debugging?
%@print roman1('a','b')
-> \mathrm{a/b}
%@print middle(1,2,3)
-> 2

%@ABORT_=False
--- Check it out. If replacement fails (@roman1), it is an error; 
--- but with ABORT_=False, it is left in place.
|@middle{a}{b}| |@roman2{yo}{no}| |@roman1{yo}|
-> |b| |\mathrm{yo/no}| |(at)roman1{yo}|

--- Multiple lines are ok EXCEPT the opening '{' must immediately follow 
--- the command name and closing '}' of previous arg.
--- A no-argument macro may also be followed by any other non-alphanumerical
--- character (or end-of-line).
--- Notice also the recursive expansion happening here.
And now, |@roman1{@middle{a}{
{yo}yo
}{b}}{no}|
-> \mathrm{{yo}yo/no}

--- OK. We can allow a '%' following a '}' to break line.
@middle{}%
{WOrked?}%
{yy}
-> WOrked?

--- recursive expansion works with mixed defined/undefined/etc
|@roman1{@comb{a}{{yo}yo}{b}}{no}|
-> \mathrm{@.../no}

%@VERBOSE_ = 3
%@triplicate = '{1}{%s}{2}'
Or try this, |@roman1{@middle@triplicate{yo}}{no}|
-> |\mathrm{(at)middle{1}{yo}{3}/no}|
--- Line is evaluated left-to-right

--- The command prefix can be redefined. This can be handy to
--- expand macros in a latex file without changing them.
%@VERBOSE_ = 1
%@PREFIX_ = '\\'
%@EXEC_ = '%'

--- Let's try a more complicated one:
\newcommand{\comment}{}
\comment{
%{
### (must use @out, magical syntax r'^\s+:\s*<strs>'->out(<strs>))
@out
def automat(f,a):
  lines = [l.strip()+r'\\' for l in a.split(r'\\')]
  : r'\begin{matrix}{%s%s}' % (f[0], f[1]*lines[0].count('&'))
  : r'\toprule'
  : lines[0]
  : r'\midrule'
  : lines[1:]
  : r'\bottomrule'
  : r'\end{matrix}'
%}
}
\automat{rc}{
x & y & z\\
r & b & x\\
a & f & f
}

--- Try something with no args
%Z = 'Zappa dude'
(expands)
\Z
\Z\now
\Z now
\Z%now
(expands not)
\Zxnow
\triplicate%now

--- Working around python reserved words
%VERBOSE_ = 3

%del = 'yammer'
\del
-> yammer

Ok, let's get out of \roman2{here}{now}!
%ABORT_=True
\roman2
"""

import sys, re

macros = { 'EXEC_'    : '%@',
           'PREFIX_' : '@',
           'ESCAPE_' : '{_}',
	   'ABORT_'  : True,
           'VERBOSE_': 2,
	   'WRAP_'   : False,
	   'OUTPUT_' : True}

try:
	import textwrap
	wrapper = textwrap.TextWrapper(break_long_words=False, break_on_hyphens=False)
except:
	wrapper = None

out_lines = []
def print_out(str_or_list):
	global out_lines
	if type(str_or_list) is str:
		out_lines.append(str_or_list)
	else:
		out_lines += str_or_list
def out(func):
	def func_composed(*args):
		global out_lines
		func(*args)
		result = '\n'.join(out_lines)
		if macros['WRAP_'] and wrapper:
			result = wrapper.fill(result)
		out_lines = []
		return result
	return func_composed

def consume_arg(l):
	level = 0
	pos = 0
	for c in l:
		if   c in ['{','[']: level += 1
		elif c in ['}',']']: level -= 1
		pos += 1
		if level == 0:
			return ('r"""%s"""'%l[1:pos-1],l[pos:])

def consume_args(l):
	args = []
	optarg = None
	if l and l[0] == '[':
		(optarg,l) = consume_arg(l)
	while True:
		if not l or l[0] != '{':
			if optarg: args.append(optarg)
			return args, l
		(arg,l) = consume_arg(l)
		args.append(arg)

replacers = [(re.compile(r'^(\s+):(.*)$'), r'\1print_out(\2)'), # ":" output
	     (re.compile(r'^(\w+)\s+='), r'macros[r"\1"] =')]   # reserved word?
def fixup_line(l):
	for replace_re, replace_with in replacers:
		l = replace_re.sub(replace_with, l)
	return l

inf = open(sys.argv[1])
errf = sys.stderr
outf = len(sys.argv)>2 and open(sys.argv[2],'w') or sys.stdout

lines = ''
collected = ''
consuming = False
for lno,l in enumerate(inf):
	# Handle %@{ ... %@}
	if l.startswith(macros['EXEC_']+'{'):
		consuming = True
		continue
	elif consuming:
		if l.startswith(macros['EXEC_']+'}'):
			consuming = False
			if macros['VERBOSE_']>2:
				debuglines = '>>> '+lines.replace('\n', '\n>>> ')+'\n'
				errf.write(debuglines);
			exec(lines, globals(), macros)
			lines = ''
		else:
			lines += fixup_line(l);
		continue

	# Handle $@
	if l.startswith(macros['EXEC_']):
		lines += fixup_line(l[len(macros['EXEC_']):])
		continue
	elif lines:
		if macros['VERBOSE_']>2:
			debuglines = '>>> '+lines.replace('\n', '\n>>> ')+'\n'
			errf.write(debuglines);
		exec(lines, globals(), macros)
		lines = ''

	# Handle in-line macros
	if collected:
		l = collected+l
		collected = ''
	if macros['PREFIX_'] in l:
		# Save up lines until we are certain to have enough to process all macro(s)
		if l.count('{') > l.count('}'):
			# balanced braces
			collected = l
			continue
		if l.endswith('}%\n'):
			# line continuations
			collected = l[:-2]
			continue

		re_string = re.escape(macros['PREFIX_'])+r'(\w+)[\W\n]'
		escaped = False
		while True:
			match = re.search(re_string, l)
			if not match:
				break

			start = l[:match.start()]
			comm = match.group(1)
			lno = str(lno)+':'
			try:
				comm_obj = macros[comm]
				args,end = consume_args(l[match.end()-1:])
				args = ','.join(args)
				if type(comm_obj) is str:
					eval_str = 'r"""%s"""%%((%s))'%(comm_obj,args)
				else:
					# protect reserved words
					eval_str = 'macros[r"%s"](%s)'%(comm, args)
				result = eval(eval_str, globals(), macros)
				if macros['VERBOSE_']>2:
					print >>errf, lno,l.rstrip().replace('\n',r'~')
					print >>errf, lno,' '*match.start()+'^'*(len(match.group(0))-1)
					print >>errf, lno,'-> """%s"""'%result
			except Exception,e:
				if macros['VERBOSE_']>1 or \
				  (macros['VERBOSE_']>0 and type(e) is not KeyError):
					print >>errf, lno,l.rstrip().replace('\n',r'~')
					print >>errf, lno,' '*match.start()+'^'*(len(match.group(0))-1)
					print >>errf, lno,repr(e)
				if macros['ABORT_']:
					raise
				escaped = True
				result = match.group(0).replace(macros['PREFIX_'], macros['ESCAPE_'], 1)
				end = l[match.end():]
			l = '%s%s%s' % (start,str(result),end)

		if escaped:
			l = l.replace(macros['ESCAPE_'], macros['PREFIX_'])

	if macros['OUTPUT_']:
		outf.write(l)
