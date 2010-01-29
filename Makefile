PDFGRAPHS := $(patsubst %,data/%.pdf,$(shell python ./parse.py report.tex))
PSGRAPHS := $(patsubst %.pdf,%.eps,$(PDFGRAPHS))
ALLFILES := $(shell git ls-files | grep -v ^data/raw)

report.pdf: report.tex header.tex $(PDFGRAPHS) version
	pdflatex -interaction nonstopmode report.tex

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

%.gp: data/gptoeps
	data/gptoeps $@

%.pdf: %.gp
	epstopdf --outfile $@.tmp $(subst .gp,.eps,$<)
	pdfcrop $@.tmp $@
	rm -f $@.tmp

data/%.pdf: data/%.tex
	pdflatex --output-directory data/ $<

bibtex: version
	latexmk -f -quiet -pdf report

clean:
	rm -f *.aux *.blg *.log *~ data/*~ *.bak
proper: clean
	git clean -f
	rm -f *.bbl *.pdf data/*.pdf
	rm -rf auto

.PHONY: publish view bibtex clean proper viewdiff sync

REV := diff
diff.pdf: report.tex $(GRAPHS) $(wildcard .git/refs/tags/$(REV)) version
	! git diff --quiet $(REV) -- report.tex # Abort if no diff
	git cat-file blob $(REV):report.tex >diff-base.tex
	latexdiff --append-textcmd="fig,twofig,twofigh,threefig,fourfig,todo,todop" \
		--exclude-textcmd='cmidrule' diff-base.tex report.tex \
		| grep -v 'cmidrule.DIFaddFL' >diff.tex
	rm -f diff-base.tex
	gitver="\\DIFdel{$$(git rev-parse --short $(REV))}"; \
	gitver="$$gitver \\DIFadd{$$(cat version)}"; \
	printf "$$gitver" >version
	latexmk -f -quiet -pdf diff
	rm -f version

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
	rm -f version
	yes|unison -auto sync


version: $(ALLFILES) $(wildcard .git/refs/heads/*)
	@( \
	gitver=$$(git rev-parse --short HEAD); \
	git diff --quiet || gitver=$$gitver+; \
	[ -f $@ ] && oldver=$$(cat $@); \
	[ "$$gitver" = "$$oldver" ] || printf $$gitver >$@ \
	)
