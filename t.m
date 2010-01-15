z : [1/4, 1/2]$
N : [30, 60, 60]$
F : 1$

Lambda: [1, 10^-10, 1]$
alpha : [1, 1, 1]$
tau : 1$
mu : [1, 1, 1]$
lambda: [1, 1, 1]$


phi: lambda+2*mu$
A: alpha / sqrt(phi*tau*Lambda)$
B: sqrt(tau*Lambda/phi)$




kosh(x) := (exp(x)+exp(-x))/2$
zinh(x) := (exp(x)-exp(-x))/2$

eqns: [
      b1*A[1],
      b1*B[1]+d1,
      a3*kosh(A[3])+b3*zinh(A[3])+c3,
      phi[3]*B[3]*A[3]*(a3*kosh(A[3])+b3*zinh(A[3]))+F,
       Lambda[1]*A[1]*(a1*zinh(A[1]*z[1])+b1*kosh(A[1]*z[1]))
      -Lambda[2]*A[2]*(a2*zinh(A[2]*z[1])+b2*kosh(A[2]*z[1])),
       Lambda[2]*A[2]*(a2*zinh(A[2]*z[2])+b2*kosh(A[2]*z[2]))
      -Lambda[3]*A[3]*(a3*zinh(A[3]*z[2])+b3*kosh(A[3]*z[2])),
       B[1]*(a1*zinh(A[1]*z[1])+b1*kosh(A[1]*z[1]))+d1
      -B[2]*(a2*zinh(A[2]*z[1])+b2*kosh(A[2]*z[1]))-d2,
       B[2]*(a2*zinh(A[2]*z[2])+b2*kosh(A[2]*z[2]))+d2
      -B[3]*(a3*zinh(A[3]*z[2])+b3*kosh(A[3]*z[2]))-d3,
       phi[1]*B[1]*A[1]*(a1*kosh(A[1]*z[1])+b1*zinh(A[1]*z[1]))
      -phi[2]*B[2]*A[2]*(a2*kosh(A[2]*z[1])+b2*zinh(A[2]*z[1])),
       phi[2]*B[2]*A[2]*(a2*kosh(A[2]*z[2])+b2*zinh(A[2]*z[2]))
      -phi[3]*B[3]*A[3]*(a3*kosh(A[3]*z[2])+b3*zinh(A[3]*z[2])),
       a1*kosh(A[1]*z[1])+b1*zinh(A[1]*z[1])+c1
      -a2*kosh(A[2]*z[1])-b2*zinh(A[2]*z[1])-c2,
       a2*kosh(A[2]*z[2])+b2*zinh(A[2]*z[2])+c2
      -a3*kosh(A[3]*z[2])-b3*zinh(A[3]*z[2])-c3
]$
display2d: false$
solns: linsolve(eqns,[a1,b1,c1,d1,a2,b2,c2,d2,a3,b3,c3,d3])$

fpprec: 128$
X[1]: makelist(float(i/N[1]*z[1]), i,0,N[1])$
X[2]: makelist(float(z[1]+(z[2]-z[1])/N[2]*(i*2-i^2/N[2])), i,0,N[2])$
X[3]: makelist(float(z[2]+i/N[3]*(1-z[2])), i,0,N[3])$






keepfloat:true$

p1(x) := fullratsimp(ev(a1*kosh(A[1]*x)+b1*zinh(A[1]*x)+c1, solns))$
p2(x) := fullratsimp(ev(a2*kosh(A[2]*x)+b2*zinh(A[2]*x)+c2, solns))$
p3(x) := fullratsimp(ev(a3*kosh(A[3]*x)+b3*zinh(A[3]*x)+c3, solns))$

outf: openw("P.dat")$
for x in X[1] do printf(outf, "~12f ~g~%", x, bfloat(p1(x)))$
for x in X[2] do printf(outf, "~12f ~g~%", x, bfloat(p2(x)))$
for x in X[3] do printf(outf, "~12f ~g~%", x, bfloat(p3(x)))$
close(outf)$

u1(x) := fullratsimp(ev(B[1]*(a1*zinh(A[1]*x)+b1*kosh(A[1]*x))+d1, solns))$
u2(x) := fullratsimp(ev(B[2]*(a2*zinh(A[2]*x)+b2*kosh(A[2]*x))+d2, solns))$
u3(x) := fullratsimp(ev(B[3]*(a3*zinh(A[3]*x)+b3*kosh(A[3]*x))+d3, solns))$

outf: openw("U.dat")$
for x in X[1] do printf(outf, "~12f ~g~%", x, bfloat(u1(x)))$
for x in X[2] do printf(outf, "~12f ~g~%", x, bfloat(u2(x)))$
for x in X[3] do printf(outf, "~12f ~g~%", x, bfloat(u3(x)))$
close(outf)$

s1(x) := fullratsimp(ev(phi[1]*A[1]*B[1]*(a1*kosh(A[1]*x)+b1*zinh(A[1]*x)), solns))$
s2(x) := fullratsimp(ev(phi[2]*A[2]*B[2]*(a2*kosh(A[2]*x)+b2*zinh(A[2]*x)), solns))$
s3(x) := fullratsimp(ev(phi[3]*A[3]*B[3]*(a3*kosh(A[3]*x)+b3*zinh(A[3]*x)), solns))$

outf: openw("S.dat")$
for x in X[1] do printf(outf, "~12f ~g~%", x, bfloat(s1(x)))$
for x in X[2] do printf(outf, "~12f ~g~%", x, bfloat(s2(x)))$
for x in X[3] do printf(outf, "~12f ~g~%", x, bfloat(s3(x)))$
close(outf)$

v1(x) := fullratsimp(ev(-Lambda[1]*A[1]*(a1*zinh(A[1]*x)+b1*kosh(A[1]*x)), solns))$
v2(x) := fullratsimp(ev(-Lambda[2]*A[2]*(a2*zinh(A[2]*x)+b2*kosh(A[2]*x)), solns))$
v3(x) := fullratsimp(ev(-Lambda[3]*A[3]*(a3*zinh(A[3]*x)+b3*kosh(A[3]*x)), solns))$

outf: openw("V.dat")$
for x in X[1] do printf(outf, "~12f ~g~%", x, bfloat(v1(x)))$
for x in X[2] do printf(outf, "~12f ~g~%", x, bfloat(v2(x)))$
for x in X[3] do printf(outf, "~12f ~g~%", x, bfloat(v3(x)))$
close(outf)$
