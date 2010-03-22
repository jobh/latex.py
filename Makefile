PDFDEPS := $(shell python parse.py -P includegraphics:1:%s.pdf -P input:1:%s.tex report.tex)
EPSDEPS := $(patsubst %.pdf,%.eps,$(PDFDEPS))

report.pdf: report.tex $(PDFDEPS)
	python parse.py -L -o $@ $<
view: report.pdf
	@exec evince report.pdf 2>/dev/null &
kview: report.pdf
	@exec okular report.pdf 2>/dev/null &

publish: .published
.published: sync report.pdf diff.pdf
	scp report.pdf diff.pdf gogmagog.simula.no:www_docs/
	git tag -f published HEAD
	touch $@

data/%.pdf: data/%.tex
	pdflatex --output-directory data/ $<

data/symm/%.pdf: data/plot_raw.py
	data/pyplot $< $@
data/asymm/%.pdf: data/plot_raw.py
	data/pyplot $< $@
data/barry-mercer/%.pdf: data/plot_raw.py
	data/pyplot $< $@
data/u-locking.pdf: data/u_locking.py
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
report.texp: report.tex
	python parse.py -L -o $@ $<
diff-base.texp: diff-base.tex
	python parse.py -L -e "BASE_REV='$(REV)'" -a 0 -o $@ $<

diff.pdf: report.texp diff-base.texp
	latexdiff --append-textcmd="fig,twofig,twofigh,threefig,fourfig,todo,todop" \
		--exclude-textcmd='cmidrule' diff-base.texp report.texp \
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
	python parse.py -L -o $@ $<

sync:
	git diff --quiet || git commit -a -m "checkpoint"
	yes|unison -auto sync

