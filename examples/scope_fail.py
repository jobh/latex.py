'''
From: Joachim B Haga <jobh@broadpark.no>
Newsgroups: gmane.comp.python.devel
Subject: Inconsistent nesting of scopes in exec(..., locals())
Date: Fri, 23 Apr 2010 15:41:55 +0200
Archived-At: <http://permalink.gmane.org/gmane.comp.python.devel/112830>
--text follows this line--
There seem to be an inconsistency in the handling of local scopes in
exec. Consider the following code, which raises NameError if the '#' is
removed from the second last line.


block = """
b = 'ok'
def f():
    print(b)    # raises NameError here
f()
"""
scope = locals()#.copy()
exec(block, globals(), scope)


The intermediate scope is searched for the variable name if the third
argument to exec() is locals(), but not if it is locals().copy().
Testing further, it looks like NameError is raised for any dict which 
is not identically equal to either globals() or locals().

This behaviour is quite unexpected, and I believe it qualifies as a 
bug. Tested with python 2.6.5 and 3.1.2.

-- 
Joachim B Haga
'''


block = __doc__.split('"""')[1]
print('block="""'+block+'"""')

scope = globals()#.copy()
exec(block, globals(), scope)
