latex.py := ../../latex.py

graphs.pdf: graphs.tex $(wildcard data/*.pdf)
	$(latex.py) -o $@ $<
graphs.texp: graphs.tex
	$(latex.py) -o $@ $<

expand-macros.pdf: expand-macros.tex
	$(latex.py) -L -o $@ $<
expand-macros.texp: expand-macros.tex
	$(latex.py) -L -o $@ $<

eval.texp: eval.tex
	$(latex.py) -o $@ $<
