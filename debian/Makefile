MAKEFLAGS += --warn-undefined-variables
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:
.SUFFIXES:
SHELL := bash
.SHELLFLAGS := -e -o pipefail -c

escape = $(subst ','\'',$(1))

makefile_dir := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
repo_dir := $(makefile_dir)/..
build_area_dir := $(makefile_dir)/build-area

.PHONY: build/src
build/src:
	pushd '$(call escape,$(repo_dir))' && gbp buildpackage -S

.PHONY: build/bin
build/bin:
	pushd '$(call escape,$(repo_dir))' && gbp buildpackage

.PHONY: build/pbuilder
build/pbuilder:
	pushd '$(call escape,$(repo_dir))' && gbp buildpackage --git-pbuilder --git-dist=focal --git-arch=amd64

.PHONY: clean
clean:
	rm -rf -- '$(call escape,$(build_area_dir))'
