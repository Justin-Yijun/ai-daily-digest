@echo off
rem ssh ProxyCommand wrapper: tunnel SSH through the local HTTP proxy.
rem Needed because (a) GitHub port 22 is blocked here and (b) ssh.github.com:443
rem only works while the TUN adapter is up. Routing SSH through the local HTTP
rem proxy (v2rayN mixed port) makes git work with TUN switched off.
rem Usage (from ssh -o ProxyCommand): ssh_proxy.bat <host> <port>
"C:\Program Files\Git\mingw64\bin\connect.exe" -H 127.0.0.1:10808 %1 %2
