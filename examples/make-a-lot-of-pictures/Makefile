latex.py := ../../latex.py
GRAPHS := $(patsubst %.eps,%.pdf,$(wildcard *.eps))

doc.pdf: $(GRAPHS) doc.tex
	$(latex.py) -o doc.pdf doc.tex

doc.texp: doc.tex
	$(latex.py) -o $@ $<

%.pdf: %.eps
	epstopdf $<
