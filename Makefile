include prelude.mk

PKG_NAME ?= linux-status
DESTDIR  ?=

$(eval $(call noexpand,PKG_NAME))
$(eval $(call noexpand,DESTDIR))

.PHONY: all
all:

.PHONY: install
install:
	install -D -m 0644 -t '$(call escape,$(DESTDIR))/usr/share/$(call escape,$(PKG_NAME))' LICENSE.txt

	install -D -m 0644 -t '$(call escape,$(DESTDIR))/usr/share/doc/$(call escape,$(PKG_NAME))'     README.md
	install -D -m 0644 -t '$(call escape,$(DESTDIR))/usr/share/doc/$(call escape,$(PKG_NAME))/doc' doc/example.png

	install -D -m 0755 -t '$(call escape,$(DESTDIR))/srv/$(call escape,$(PKG_NAME))' src/app.py
	install -D -m 0755 -t '$(call escape,$(DESTDIR))/srv/$(call escape,$(PKG_NAME))' src/server.py

	cp -dr --preserve=mode,timestamp -- html '$(call escape,$(DESTDIR))/srv/$(call escape,$(PKG_NAME))'

	install -D -m 0644 -t '$(call escape,$(DESTDIR))/usr/lib/systemd/system' 'dist/systemd/$(call escape,$(PKG_NAME)).service'
