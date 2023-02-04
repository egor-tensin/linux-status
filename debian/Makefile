MAKEFLAGS += --no-builtin-rules --no-builtin-variables --warn-undefined-variables
unexport MAKEFLAGS
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:
.SUFFIXES:
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c

escape = $(subst ','\'',$(1))

define noexpand
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

NAME      ?= Egor Tensin
EMAIL     ?= Egor.Tensin@gmail.com
PPA_OWNER ?= egor-tensin
PPA_NAME  ?= linux-status
GPG_KEY   ?= 3B3EF1235420917E0DB0723991D679FB92B036CB
DIST      ?= bionic

$(eval $(call noexpand,NAME))
$(eval $(call noexpand,EMAIL))
$(eval $(call noexpand,PPA_OWNER))
$(eval $(call noexpand,PPA_NAME))
$(eval $(call noexpand,GPG_KEY))
$(eval $(call noexpand,DIST))

export NAME
export EMAIL

this_dir   := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
root       := $(this_dir)/..
build_area := $(this_dir)/build-area

.PHONY: DO
DO:

.PHONY: deps
deps:
	apt-get update
	DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential cowbuilder devscripts dh-make dput git-buildpackage

.PHONY: dch
dch:
	gbp dch --distribution=unstable

.PHONY: commit
commit:
	cd -- '$(call escape,$(root))' && \
		version="$$( dpkg-parsechangelog --show-field Version )" && \
		git commit -m "debian: $$version"

.PHONY: tag
tag:
	cd -- '$(call escape,$(root))' && gbp buildpackage --git-tag-only

.PHONY: src/test
src/test:
	cd -- '$(call escape,$(root))' && gbp buildpackage --git-ignore-new -S -us -uc

.PHONY: src
src:
	cd -- '$(call escape,$(root))' && gbp buildpackage -S '-k0x$(call escape,$(GPG_KEY))'

.PHONY: bin/test
bin/test:
	cd -- '$(call escape,$(root))' && gbp buildpackage --git-ignore-new -b -us -uc

.PHONY: bin
bin:
	cd -- '$(call escape,$(root))' && gbp buildpackage -b '-k0x$(call escape,$(GPG_KEY))'

.PHONY: dist/create
dist/create:
	cd -- '$(call escape,$(root))' && env 'DIST=$(call escape,$(DIST))' git-pbuilder create

.PHONY: dist/update
dist/update:
	cd -- '$(call escape,$(root))' && env 'DIST=$(call escape,$(DIST))' git-pbuilder update

.PHONY: dist/test
dist/test:
	cd -- '$(call escape,$(root))' && gbp buildpackage --git-ignore-new --git-pbuilder '--git-dist=$(call escape,$(DIST))'

.PHONY: dist
dist:
	cd -- '$(call escape,$(root))' && gbp buildpackage --git-pbuilder '--git-dist=$(call escape,$(DIST))'
	cd -- '$(call escape,$(root))' && debsign '-k0x$(call escape,$(GPG_KEY))' --debs-dir '$(call escape,$(build_area))'

.PHONY: upload
upload:
	find '$(call escape,$(build_area))' -type f -name '*.changes' -exec dput '$(call escape,ppa:$(PPA_OWNER)/$(PPA_NAME)/ubuntu/$(DIST))' {} ';'

.PHONY: clean
clean:
	rm -rf -- '$(call escape,$(build_area))'
