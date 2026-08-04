# Build the tutorial slides:  make   ->  flowcept_academy.pdf
TEX = flowcept_academy
LATEX = pdflatex -interaction=nonstopmode -halt-on-error

all: $(TEX).pdf

$(TEX).pdf: $(TEX).tex
	$(LATEX) $(TEX).tex
	$(LATEX) $(TEX).tex

clean:
	rm -f $(TEX).aux $(TEX).log $(TEX).nav $(TEX).out $(TEX).snm $(TEX).toc $(TEX).vrb

distclean: clean
	rm -f $(TEX).pdf

.PHONY: all clean distclean
