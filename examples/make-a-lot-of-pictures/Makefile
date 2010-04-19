GRAPHS := $(patsubst %.eps,%.pdf,$(wildcard *.eps))

doc.pdf: $(GRAPHS) doc.tex
	latex.py -L -o doc.pdf doc.tex

%.pdf: %.eps
	epstopdf $<
