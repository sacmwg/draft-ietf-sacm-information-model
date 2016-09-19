include lib/main.mk

lib/main.mk:
	git submodule update --init

im.html:
	python check/check.py --html --output im.html draft-ietf-sacm-information-model.xml

impages: $(GHPAGES_TMP) im.html
	cp im.html $(GHPAGES_TMP)
	cp -r css $(GHPAGES_TMP)/css

ghpagesAll: impages ghpages
