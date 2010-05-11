PYTHON := python3
latex.py := ../../latex.py

graphs.pdf: graphs.tex $(wildcard data/*.pdf)
	$(PYTHON) $(latex.py) -o $@ $<
graphs.texp: graphs.tex
	$(PYTHON) $(latex.py) -o $@ $<

expand-macros.pdf: expand-macros.tex
	$(PYTHON) $(latex.py) -L -o $@ $<
expand-macros.texp: expand-macros.tex
	$(PYTHON) $(latex.py) -L -o $@ $<

eval.texp: eval.tex
	$(PYTHON) $(latex.py) -B -o $@ $<

messy-example.texp: messy-example.tex
	$(PYTHON) $(latex.py) -B -o $@ $<

various.texp: various.tex
	$(PYTHON) $(latex.py) -L -o $@ $<

missing.texp: missing.tex
	$(PYTHON) $(latex.py) -o $@ $<

multi_prefix.texp: multi_prefix.tex
	$(PYTHON) $(latex.py) -L -o $@ $<
