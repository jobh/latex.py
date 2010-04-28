latex.py := ../../latex.py

graphs.pdf: graphs.tex $(wildcard data/*.pdf)
	$(latex.py) -o $@ $<
graphs.texp: graphs.tex
	$(latex.py) -o $@ $<
