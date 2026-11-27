## Ruantiblock


Выборочная маршрутизация для обхода блокировок в OpenWrt.

* Решение построено на стандартных системных службах и утилитах OpenWrt (nftables, dnsmasq).

* Поддерживаются L3 VPN с маршрутизацией на сетевой интерфейс (OpenVPN, Wireguard, PPTP, Sing-box в режиме tun и пр.), прозрачные прокси с перенаправлением на порт (Sing-box в режиме TProxy, Xray, V2Ray, Shadowsock-libev, Redsocks и пр.), Tor.

* Перенаправление трафика на основе доменов и IP адресов.

* Гибкие настройки для пользовательских списков, использование нескольких VPN/прокси для разных списков с приоритетами.

* Интеграция с веб-интерфейсом OpenWrt.

* Постоянный снимок обработанных списков в <code>/etc/ruantiblock/cache/lists.tar.gz</code> восстанавливается при старте и при ошибках сетевого обновления; обновление по-прежнему всегда начинается с сети.


Пакеты для OpenWrt 24.10 и инструкции по установке и обновлению: [https://vadash.github.io/ruantiblock_openwrt/](https://vadash.github.io/ruantiblock_openwrt/)

Подробно об установке и настройке: [https://github.com/gSpotx2f/ruantiblock_openwrt/wiki](https://github.com/gSpotx2f/ruantiblock_openwrt/wiki)

___________________
