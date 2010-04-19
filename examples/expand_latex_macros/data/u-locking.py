#!/usr/bin/python

from plot_raw import *

spaces = ['Q1,-,Q1,-', 'Q1-,Q2,Q2,Q1-']
labels = ['Mixed nothing', 'Mixed both']

ax = newfig()
files = ['data/raw/asymm.%s.EPS-14_p0000_19'%s for s in spaces]
data = map(fdata, files)
for idx,d in enumerate(data):
    d.fix()
    line = Line2D(d.x, d.y,
                  label=labels[idx], alpha=0.5, lw=2,
                  c=d.c, solid_capstyle='butt')
    ax.add_line(line)

ax.autoscale_view(scalex=False)
ax.set_ylim(None,0)
matplotlib.pyplot.ylabel(r'Displacement $\boldsymbol{u}_z$')
leg = ax.legend(loc='upper right', ncol=1)
leg.get_frame().set_alpha(0.2)

if 'SAVE' in os.environ:
    fname = sys.argv[1]
    print 'creating '+fname
    matplotlib.pyplot.savefig(fname)
else:
    matplotlib.pyplot.show()
