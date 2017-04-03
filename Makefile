include lib/main.mk

lib/main.mk:
ifneq (,$(shell git submodule status lib 2>/dev/null))
	git submodule sync
	git submodule update --init
else
	git clone -q --depth 10 -b master https://github.com/martinthomson/i-d-template.git lib
endif

im.html:
	python check/generate.py --html --output im.html im.csv

draft-ietf-sacm-information-model.xml: im.xml

im.xml: im.csv
	python check/generate.py --xml --output im.xml im.csv

ghpages: im.html

