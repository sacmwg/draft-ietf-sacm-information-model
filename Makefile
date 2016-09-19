include lib/main.mk

lib/main.mk:
	git submodule update --init

drafts_html = $(drafts_html) im.html

im.html:
	python check/check.py --html --output im.html draft-ietf-sacm-information-model.xml

impages: $(GHPAGES_TMP) im.html
	cp im.html $(GHPAGES_TMP)
	cp -r css/* $(GHPAGES_TMP)
	ls -R $(GHPAGES_TMP)

ghpagesAll: ghpages
