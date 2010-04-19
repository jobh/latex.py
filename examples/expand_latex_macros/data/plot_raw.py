#!/usr/bin/python

import sys

import os
import numpy
import matplotlib
import matplotlib.pyplot
from matplotlib.lines import Line2D

NaN = float('nan')
Inf = float('inf')

matplotlib.rc('text', usetex=True)
matplotlib.rc('text.latex', preamble=r'\usepackage{amsmath}')


nc = -1
def colour():
    global nc
    nc += 1
    return ['red','blue','green','black'][nc]

class fdata(object):
    miny = Inf
    maxy = -Inf
    def __init__(self, fname):
        X = []
        Y = []
        f = open(fname)
        lasty = valid = 0
        for line in f:
            try:
                (x,y) = map(float, line.split())
                if valid>1 and abs(y-lasty) < 1e-4:
                    X[-1] = x
                    Y[-1] = y
                else:
                    X.append(x)
                    Y.append(y)
                    valid += 1
                lasty = y
            except:
                Y.append(NaN)
                X.append(NaN)
                valid = 0

        #print X
        self.x = numpy.array(X)
        self.y = numpy.array(Y)
        self.c = colour()
        self.fname = fname

        fdata.miny = min(fdata.miny,min(self.y))
        fdata.maxy = max(fdata.maxy,max(self.y))

    def fix(self):
        # Eliminate small steps (draw as continuous line)
        x = self.x
        y = self.y
        eps = (fdata.maxy-fdata.miny) * 3e-3
        nans = numpy.nonzero(y != y)[0]
        for i in nans:
            if abs(y[i-1]-y[i+1]) < eps:
                x[i] = (x[i+1]+x[i-1])/2
                y[i] = (y[i+1]+y[i-1])/2


def newfig():
    global nc
    nc = -1
    fig = matplotlib.pyplot.figure(figsize=(6,5))
    ax = fig.add_subplot(111)
    ax.xaxis.set_ticks([0,.25,.75,1])
    ax.xaxis.grid()
    matplotlib.pyplot.xlabel('$z$')
    fig.canvas.mpl_connect('key_press_event', lambda event: event.key=='q' and sys.exit())
    return ax

if __name__ == '__main__':
    datasets = [(r'$p_{\mathrm{f}}$',              14),
                (r'$p_{\mathrm{s}}$',              25),
                (r'$2\mu\boldsymbol{\nabla}\cdot\boldsymbol{u}$',   26)]

    for fname in sys.argv[1:]:
        if not 'EPS' in fname:
            continue

        ax = newfig()

        rname = fname.replace('/', '.')
        rname = rname.replace('data.','data/raw/')
        rname = rname.replace('.pdf','')
        rname = rname.replace(',EPS', '.EPS')

        data = []
        for d in datasets:
            data.append(fdata('%s_p0000_%d'%(rname, d[1])))

        idx = 0
        for d in data:
            d.fix()
            line = Line2D(d.x, d.y,
                          label=datasets[idx][0], alpha=0.5, lw=2,
                          c=d.c, solid_capstyle='butt')
            ax.add_line(line)
            idx += 1

        line = Line2D(data[0].x, data[0].y+data[1].y+data[2].y,
                      label=r'$\mathrm{Tr}\,\tilde{\boldsymbol{\sigma}}/3$', alpha=0.3, lw=6,
                      c=colour(), solid_capstyle='butt')
        ax.add_line(line)

        ax.autoscale_view(scalex=False)
        if 'barry' in fname:
            loc = 'upper right'
            (ymin,ymax) = ax.get_ylim()
            if ymax < 0.011:
                ax.set_ylim(ymin, 0.011)
        else:
            loc = 'upper left'
        leg = ax.legend(loc=loc, ncol=2)
        leg.get_frame().set_alpha(0.2)

        if 'SAVE' in os.environ:
            print 'creating '+fname
            matplotlib.pyplot.savefig(fname)
        else:
            matplotlib.pyplot.show()
