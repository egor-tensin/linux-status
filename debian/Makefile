include prelude.mk

NAME      ?= Egor Tensin
EMAIL     ?= egor@tensin.name
PPA_OWNER ?= egor-tensin
PPA_NAME  ?= linux-status
GPG_KEY   ?= 09AEA2BAD52882A1AF9D6042F218DB829A9905B5
DIST      ?= focal

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
	apt update
	DEBIAN_FRONTEND=noninteractive apt install -y --no-install-recommends \
		build-essential \
		cowbuilder \
		devscripts \
		dh-make \
		dput \
		git-buildpackage \
		vim

.PHONY: dch
dch:
	gbp dch --distribution=unstable --commit

.PHONY: changelog
changelog: dch

.PHONY: tag
tag:
	gbp tag

.PHONY: push
push:
	env GIT_SSH_COMMAND='ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no' gbp push

.PHONY: src/test
src/test:
	cd -- '$(call escape,$(root))' && gbp buildpackage -S --no-sign --git-ignore-new

.PHONY: src
src:
	cd -- '$(call escape,$(root))' && gbp buildpackage -S '-k0x$(call escape,$(GPG_KEY))' --changes-option=-sa

.PHONY: bin/test
bin/test:
	cd -- '$(call escape,$(root))' && gbp buildpackage -b --no-sign --git-ignore-new

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
