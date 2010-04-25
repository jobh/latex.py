latex.py := ../../latex.py
PDFDEPS := $(shell $(latex.py) -P includegraphics:1:%s.pdf -P input:1:%s.tex report.tex)
EPSDEPS := $(patsubst %.pdf,%.eps,$(PDFDEPS))

report.pdf: report.tex $(PDFDEPS)
	$(latex.py) -L -o $@ $<
report.texp: report.tex
	$(latex.py) -L -e "_REV='xxxxxx'" -o $@ $<

view: report.pdf
	exec evince report.pdf 2>/dev/null &
kview: report.pdf
	exec okular report.pdf 2>/dev/null &

publish: .published
.published: sync report.pdf diff.pdf
	scp report.pdf diff.pdf gogmagog.simula.no:www_docs/
	git tag -f published HEAD
	touch $@

data/%.pdf: data/%.tex
	pdflatex --output-directory data/ $<
data/%.pdf: data/%.py
	data/pyplot $< $@
data/%.pdf: data/plot_raw.py
	data/pyplot $< $@

clean:
	rm -f *.aux *.blg *.log *~ data/*~ *.bak *.texp
proper: clean
	git clean -f
	rm -f *.bbl *.pdf data/*.pdf
	rm -rf auto

.PHONY: publish view clean proper viewdiff sync

REV := diff
diff-base.tex: $(wildcard .git/refs/tags/$(REV))
	git cat-file blob $(REV):report.tex > $<
diff-curr.texp: report.tex
	$(latex.py) -L -e "BASE_REV='$(REV)'" -o $@ $<
diff-base.texp: diff-base.tex
	$(latex.py) -L -a 0 -o $@ $<

diff.pdf: diff-curr.texp diff-base.texp
	latexdiff \
		--exclude-textcmd='cmidrule' diff-base.texp diff-curr.texp \
		| grep -v 'cmidrule.DIFaddFL' >diff.texp
	latexmk -f -quiet -pdf diff.texp

viewdiff: diff.pdf
	evince diff.pdf 2>/dev/null

data/%.eps: data/%.tex
	pdflatex --output-directory data/ $<
	pdftops $(patsubst %.tex,%.pdf,$<)
	ps2eps -f $(patsubst %.tex,%.ps,$<)
	rm -f $(patsubst %.tex,%.ps,$<)
%.eps: %.pdf
	pdftops -eps $< $@
%.eps: %.png
	convert $< $@

report.ps: report.dvi
	dvips -o $@ $<
report.dvi: report.tex $(EPSDEPS)
	$(latex.py) -L -o $@ $<

sync:
	git diff --quiet || git commit -a -m "checkpoint"
	yes|unison -auto sync

