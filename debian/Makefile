MAKEFLAGS += --warn-undefined-variables
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:
.SUFFIXES:
SHELL := bash
.SHELLFLAGS := -e -o pipefail -c

escape = $(subst ','\'',$(1))

# Don't expand parameters:
define escape_arg
ifeq ($$(origin $(1)),environment)
    $(1) := $$(value $(1))
endif
ifeq ($$(origin $(1)),environment override)
    $(1) := $$(value $(1))
endif
ifeq ($$(origin $(1)),command line)
    override $(1) := $$(value $(1))
endif
endef

PPA_OWNER ?= egor-tensin
PPA_NAME  ?= linux-status
GPG_KEY   ?= 3B3EF1235420917E0DB0723991D679FB92B036CB
DIST      ?= focal

$(eval $(call escape_arg,PPA_OWNER))
$(eval $(call escape_arg,PPA_NAME))
$(eval $(call escape_arg,GPG_KEY))
$(eval $(call escape_arg,DIST))

this_dir   := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
root       := $(this_dir)/..
build_area := $(this_dir)/build-area

.PHONY: DO
DO:

.PHONY: src/test
src/test:
	pushd '$(call escape,$(root))' && gbp buildpackage --git-ignore-new -S -us -uc

.PHONY: src
src:
	pushd '$(call escape,$(root))' && gbp buildpackage -S '-k0x$(call escape,$(GPG_KEY))'

.PHONY: bin/test
bin/test:
	pushd '$(call escape,$(root))' && gbp buildpackage --git-ignore-new -b -us -uc

.PHONY: bin
bin:
	pushd '$(call escape,$(root))' && gbp buildpackage -b '-k0x$(call escape,$(GPG_KEY))'

.PHONY: dist/create
dist/create:
	pushd '$(call escape,$(root))' && env 'DIST=$(call escape,$(DIST))' git-pbuilder create

.PHONY: dist/update
dist/update:
	pushd '$(call escape,$(root))' && env 'DIST=$(call escape,$(DIST))' git-pbuilder update

.PHONY: dist/test
dist/test:
	pushd '$(call escape,$(root))' && gbp buildpackage --git-ignore-new --git-pbuilder '--git-dist=$(call escape,$(DIST))'

.PHONY: dist
dist:
	pushd '$(call escape,$(root))' && gbp buildpackage --git-pbuilder '--git-dist=$(call escape,$(DIST))'
	pushd '$(call escape,$(root))' && debsign '-k0x$(call escape,$(GPG_KEY))' --debs-dir '$(call escape,$(build_area))'

.PHONY: upload
upload:
	find '$(call escape,$(build_area))' -type f -name '*.changes' -exec dput 'ppa:$(call escape,$(PPA_OWNER))/$(call escape,$(PPA_NAME))/ubuntu/$(DIST)' {} ';'

upload/%: DO
	find '$(call escape,$(build_area))' -type f -name '*.changes' -exec dput 'ppa:$(call escape,$(PPA_OWNER))/$(call escape,$(PPA_NAME))/ubuntu/$*' {} ';'

.PHONY: upload-all
upload-all: upload/bionic upload/focal upload/groovy

.PHONY: clean
clean:
	rm -rf -- '$(call escape,$(build_area))'
