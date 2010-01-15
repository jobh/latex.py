z : [1/4, 3/4]$
N : [30, 120, 30]$
F : 1$

Lambda: [1, 1, 1]$
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
      b[1]*A[1],
      b[1]*B[1]+d[1],
      a[3]*kosh(A[3])+b[3]*zinh(A[3])+c[3],
      phi[3]*B[3]*A[3]*(a[3]*kosh(A[3])+b[3]*zinh(A[3]))+F,
       Lambda[1]*A[1]*(a[1]*zinh(A[1]*z[1])+b[1]*kosh(A[1]*z[1]))
      -Lambda[2]*A[2]*(a[2]*zinh(A[2]*z[1])+b[2]*kosh(A[2]*z[1])),
       Lambda[2]*A[2]*(a[2]*zinh(A[2]*z[2])+b[2]*kosh(A[2]*z[2]))
      -Lambda[3]*A[3]*(a[3]*zinh(A[3]*z[2])+b[3]*kosh(A[3]*z[2])),
       B[1]*(a[1]*zinh(A[1]*z[1])+b[1]*kosh(A[1]*z[1]))+d[1]
      -B[2]*(a[2]*zinh(A[2]*z[1])+b[2]*kosh(A[2]*z[1]))-d[2],
       B[2]*(a[2]*zinh(A[2]*z[2])+b[2]*kosh(A[2]*z[2]))+d[2]
      -B[3]*(a[3]*zinh(A[3]*z[2])+b[3]*kosh(A[3]*z[2]))-d[3],
       phi[1]*B[1]*A[1]*(a[1]*kosh(A[1]*z[1])+b[1]*zinh(A[1]*z[1]))
      -phi[2]*B[2]*A[2]*(a[2]*kosh(A[2]*z[1])+b[2]*zinh(A[2]*z[1])),
       phi[2]*B[2]*A[2]*(a[2]*kosh(A[2]*z[2])+b[2]*zinh(A[2]*z[2]))
      -phi[3]*B[3]*A[3]*(a[3]*kosh(A[3]*z[2])+b[3]*zinh(A[3]*z[2])),
       a[1]*kosh(A[1]*z[1])+b[1]*zinh(A[1]*z[1])+c[1]
      -a[2]*kosh(A[2]*z[1])-b[2]*zinh(A[2]*z[1])-c[2],
       a[2]*kosh(A[2]*z[2])+b[2]*zinh(A[2]*z[2])+c[2]
      -a[3]*kosh(A[3]*z[2])-b[3]*zinh(A[3]*z[2])-c[3]
]$
display2d: false$
solns: linsolve(eqns,[a[1],b[1],c[1],d[1],a[2],b[2],c[2],d[2],a[3],b[3],c[3],d[3]]);

fpprec: 256$
for i thru 3 do
    p[i](x) := fullratsimp(ev(a[i]*kosh(A[i]*x)+b[i]*zinh(A[i]*x)+c[i], solns))$
for i thru 3 do
    u[i](x) := fullratsimp(ev(B[i]*a[i]*zinh(A[i]*x)+B[i]*b[i]*kosh(A[i]*x)+d[i], solns))$
for i thru 3 do
    v[i](x) := at(-Lambda[i]*diff(p[i](y),y), [y=x])$
for i thru 3 do
    s[i](x) := at(phi[i]*diff(u[i](y),y), [y=x])$

X[1]: makelist(i/N[1]*z[1], i,0,N[1])$
X[2]: makelist(z[1]+(z[2]-z[1])/N[2]*(i*2-i^2/N[2]), i,0,N[2])$
X[3]: makelist(z[2]+i/N[3]*(1-z[2]), i,0,N[3])$

for i thru 3 do
    P[i]: makelist([x,bfloat(p[i](x))], x,X[i])$
outf: openw("P.dat")$
for i thru 3 do
    for f in P[i] do
     printf(outf, "~12f ~g~%", f[1], f[2])$
close(outf)$

for i thru 3 do
    U[i]: makelist([x,bfloat(u[i](x))], x,X[i])$
outf: openw("U.dat")$
for i thru 3 do
    for f in U[i] do
     printf(outf, "~12f ~g~%", f[1], f[2])$
close(outf)$

for i thru 3 do
    V[i]: makelist([x,bfloat(v[i](x))], x,X[i])$
outf: openw("V.dat")$
for i thru 3 do
    for f in V[i] do
     printf(outf, "~12f ~g~%", f[1], f[2])$
close(outf)$

for i thru 3 do
    S[i]: makelist([x,bfloat(s[i](x))], x,X[i])$
outf: openw("S.dat")$
for i thru 3 do
    for f in S[i] do
     printf(outf, "~12f ~g~%", f[1], f[2])$
close(outf)$

plot2d([[discrete,U[1]],[discrete,U[2]],[discrete,U[3]],
 [discrete,P[1]],[discrete,P[2]],[discrete,P[3]]]);
