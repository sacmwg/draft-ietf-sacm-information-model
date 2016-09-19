include lib/main.mk

lib/main.mk:
	git submodule update --init

im.html:
	python check/check.py --html --output im.html draft-ietf-sacm-information-model.xml

ghpages: im.html

