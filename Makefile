PDFDEPS := $(shell python parse.py -P includegraphics:1:%s.pdf -P input:1:%s.tex report.tex)
EPSDEPS := $(patsubst %.pdf,%.eps,$(PDFDEPS))
ALLFILES := $(shell git ls-files | grep -v ^data/raw)

report.pdf: report.tex $(PDFDEPS)
	python parse.py -L -o $@ $<

view: report.pdf
	@exec evince report.pdf 2>/dev/null &
kview: report.pdf
	@exec okular report.pdf 2>/dev/null &

publish: .published
.published: sync report.pdf bibtex diff.pdf
	scp report.pdf diff.pdf gogmagog.simula.no:www_docs/
	git tag -f published HEAD
	touch $@

data/iter-%.gp: data/iter-template.gpt
	(n=$@; n=$${n#data/iter-}; n=$${n%.gp}; \
	sed -e "s/XX/$$n/g" data/iter-template.gpt > $@)

#%.gp: data/gptoeps
#	data/gptoeps $@
#
#%.pdf: %.gp
#	epstopdf --outfile $@.tmp $(subst .gp,.eps,$<)
#	pdfcrop $@.tmp $@
#	rm -f $@.tmp

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
	rm -f *.aux *.blg *.log *~ data/*~ *.bak
proper: clean
	git clean -f
	rm -f *.bbl *.pdf data/*.pdf
	rm -rf auto

.PHONY: publish view bibtex clean proper viewdiff sync

REV := diff
diff.pdf: report.pdf $(wildcard .git/refs/tags/$(REV))
	! git diff --quiet $(REV) -- report.tex # Abort if no diff
	git cat-file blob $(REV):report.tex >diff-base.tex
	python parse.py -L -e "BASE_REV=$(REV)" -o diff-base.texp diff-base.tex
	latexdiff --append-textcmd="fig,twofig,twofigh,threefig,fourfig,todo,todop" \
		--exclude-textcmd='cmidrule' diff-base.texp report.texp \
		| grep -v 'cmidrule.DIFaddFL' >diff.texp
	rm -f diff-base.tex*
	latexmk -f -quiet -pdf diff

viewdiff: diff.pdf
	evince diff.pdf 2>/dev/null

%.eps: %.pdf
	pdftops -eps $< $@

%.eps: %.png
	convert $< $@

report.ps: report.dvi
	dvips -o $@ $<
report.dvi: report.tex header.tex $(PSGRAPHS)
	latex -interaction nonstopmode report.tex


sync:
	git diff --quiet || git commit -a -m "checkpoint"
	yes|unison -auto sync

