#
# (с) 2025 gSpot (https://github.com/gSpotx2f/ruantiblock_openwrt)
#

include $(TOPDIR)/rules.mk

PKG_NAME:=ruantiblock
PKG_VERSION:=2.2.0
PKG_RELEASE:=1
PKG_MAINTAINER:=gSpot <https://github.com/gSpotx2f/ruantiblock_openwrt>

include $(INCLUDE_DIR)/package.mk

define Package/$(PKG_NAME)
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Ruantiblock
  URL:=https://github.com/gSpotx2f/ruantiblock_openwrt
  PKGARCH:=all
  DEPENDS:=+dnsmasq-full +kmod-nft-tproxy
endef

define Package/$(PKG_NAME)/description
endef

define Package/$(PKG_NAME)/conffiles
/etc/config/ruantiblock
/etc/ruantiblock/ruantiblock.conf
/etc/ruantiblock/fqdn_filter
/etc/ruantiblock/ip_filter
/etc/ruantiblock/bypass_entries
/etc/ruantiblock/gr_excluded_nets
/etc/ruantiblock/gr_excluded_sld
/etc/ruantiblock/user_lists/list1
/etc/ruantiblock/user_lists/list2
/etc/ruantiblock/user_lists/list3
/etc/ruantiblock/user_lists/list4
/etc/ruantiblock/user_lists/list5
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/$(PKG_NAME)/install
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/ruantiblock $(1)/etc/config/ruantiblock
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/ruantiblock $(1)/etc/init.d/ruantiblock
	$(INSTALL_DIR) $(1)/etc/hotplug.d/iface
	$(INSTALL_BIN) ./files/etc/hotplug.d/iface/40-ruantiblock $(1)/etc/hotplug.d/iface/40-ruantiblock
	$(INSTALL_DIR) $(1)/etc/ruantiblock
	$(INSTALL_CONF) ./files/etc/ruantiblock/ruantiblock.conf $(1)/etc/ruantiblock/ruantiblock.conf
	$(INSTALL_DATA) ./files/etc/ruantiblock/fqdn_filter $(1)/etc/ruantiblock/fqdn_filter
	$(INSTALL_DATA) ./files/etc/ruantiblock/ip_filter $(1)/etc/ruantiblock/ip_filter
	$(INSTALL_DATA) ./files/etc/ruantiblock/bypass_entries $(1)/etc/ruantiblock/bypass_entries
	$(INSTALL_DATA) ./files/etc/ruantiblock/gr_excluded_nets $(1)/etc/ruantiblock/gr_excluded_nets
	$(INSTALL_DATA) ./files/etc/ruantiblock/gr_excluded_sld $(1)/etc/ruantiblock/gr_excluded_sld
	$(INSTALL_DIR) $(1)/etc/ruantiblock/user_lists
	$(INSTALL_DATA) ./files/etc/ruantiblock/user_lists/list1 $(1)/etc/ruantiblock/user_lists/list1
	$(INSTALL_DATA) ./files/etc/ruantiblock/user_lists/list2 $(1)/etc/ruantiblock/user_lists/list2
	$(INSTALL_DATA) ./files/etc/ruantiblock/user_lists/list3 $(1)/etc/ruantiblock/user_lists/list3
	$(INSTALL_DATA) ./files/etc/ruantiblock/user_lists/list4 $(1)/etc/ruantiblock/user_lists/list4
	$(INSTALL_DATA) ./files/etc/ruantiblock/user_lists/list5 $(1)/etc/ruantiblock/user_lists/list5
	$(INSTALL_DIR) $(1)/usr/share/ruantiblock
	$(INSTALL_DATA) ./files/usr/share/ruantiblock/blacklist_sources $(1)/usr/share/ruantiblock/blacklist_sources
	$(INSTALL_DATA) ./files/usr/share/ruantiblock/config_script $(1)/usr/share/ruantiblock/config_script
	$(INSTALL_DATA) ./files/usr/share/ruantiblock/config_script_user_instances $(1)/usr/share/ruantiblock/config_script_user_instances
	$(INSTALL_DATA) ./files/usr/share/ruantiblock/info_output $(1)/usr/share/ruantiblock/info_output
	$(INSTALL_DATA) ./files/usr/share/ruantiblock/nft_functions $(1)/usr/share/ruantiblock/nft_functions
	$(INSTALL_DATA) ./files/usr/share/ruantiblock/user_instances_common $(1)/usr/share/ruantiblock/user_instances_common
	$(INSTALL_DIR) $(1)/usr/libexec/ruantiblock
	$(INSTALL_BIN) ./files/usr/libexec/ruantiblock/ruab_route_check $(1)/usr/libexec/ruantiblock/ruab_route_check
	$(INSTALL_BIN) ./files/usr/libexec/ruantiblock/ruab_list_cache $(1)/usr/libexec/ruantiblock/ruab_list_cache
	$(INSTALL_BIN) ./files/usr/libexec/ruantiblock/ruab_parser_user_entries $(1)/usr/libexec/ruantiblock/ruab_parser_user_entries
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) ./files/usr/bin/ruantiblock $(1)/usr/bin/ruantiblock
endef

define Package/$(PKG_NAME)/preinst
#!/bin/sh

PREFIX="$${PREFIX:-}"
FILE_MAIN_SCRIPT="$${PREFIX}/usr/bin/ruantiblock"
FILE_INIT_SCRIPT="$${PREFIX}/etc/init.d/ruantiblock"
STATE_FILE="$${PREFIX}/tmp/ruantiblock.opkg-state"

rm -f "$$STATE_FILE"
if [ "$$1" = "upgrade" ]; then
	ENABLED=0
	RUNNING=0
	if [ -x "$$FILE_INIT_SCRIPT" ] && "$$FILE_INIT_SCRIPT" enabled >/dev/null 2>&1; then
		ENABLED=1
	fi
	if [ -x "$$FILE_MAIN_SCRIPT" ]; then
		STATUS="$$("$$FILE_MAIN_SCRIPT" raw-status 2>/dev/null)"
		case "$$STATUS" in
			0|3|4) RUNNING=1 ;;
		esac
	fi
	printf '%s\n%s\n' "$$ENABLED" "$$RUNNING" > "$$STATE_FILE"
fi

[ -x "$$FILE_MAIN_SCRIPT" ] && "$$FILE_MAIN_SCRIPT" destroy

exit 0
endef

define Package/$(PKG_NAME)/prerm
#!/bin/sh

PREFIX="$${PREFIX:-}"
FILE_MAIN_SCRIPT="$${PREFIX}/usr/bin/ruantiblock"
FILE_INIT_SCRIPT="$${PREFIX}/etc/init.d/ruantiblock"
CRONTAB_FILE="$${PREFIX}/etc/crontabs/root"
CRON_INIT_SCRIPT="$${PREFIX}/etc/init.d/cron"

if [ "$$1" = "remove" ]; then
	[ -x "$$FILE_MAIN_SCRIPT" ] && "$$FILE_MAIN_SCRIPT" destroy
	[ -x "$$FILE_INIT_SCRIPT" ] && "$$FILE_INIT_SCRIPT" disable
	if [ -f "$$CRONTAB_FILE" ]; then
		awk -v FILE_MAIN_SCRIPT="/usr/bin/ruantiblock" '$$0 !~ FILE_MAIN_SCRIPT {
			print $$0;
		}' "$$CRONTAB_FILE" > "$${CRONTAB_FILE}.tmp" && mv -f "$${CRONTAB_FILE}.tmp" "$$CRONTAB_FILE"
	fi
	[ -x "$$CRON_INIT_SCRIPT" ] && "$$CRON_INIT_SCRIPT" restart
fi

exit 0
endef

define Package/$(PKG_NAME)/postinst
#!/bin/sh

PREFIX="$${PREFIX:-}"
FILE_INIT_SCRIPT="$${PREFIX}/etc/init.d/ruantiblock"
STATE_FILE="$${PREFIX}/tmp/ruantiblock.opkg-state"

if [ "$$1" = "configure" ] && [ -f "$$STATE_FILE" ]; then
	ENABLED=0
	RUNNING=0
	{
		read -r ENABLED
		read -r RUNNING
	} < "$$STATE_FILE"
	if [ "$$ENABLED" = "1" ] && [ -x "$$FILE_INIT_SCRIPT" ]; then
		"$$FILE_INIT_SCRIPT" enable
	fi
	if [ "$$RUNNING" = "1" ] && [ -x "$$FILE_INIT_SCRIPT" ]; then
		"$$FILE_INIT_SCRIPT" start
	fi
fi
rm -f "$$STATE_FILE"

exit 0
endef

$(eval $(call BuildPackage,$(PKG_NAME)))
