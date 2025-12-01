chcp 65001
set V8=C:\Program Files\1cv8\8.3.27.1786\bin
set NameSrvc=ras_1539
set DisplName="Сервер администрирования 1С:Предприятия 8.3 (x86-64) (ragent:1540)"
set Command="\"%V8%\ras.exe\" --service cluster --address 0.0.0.0 -p 1539 127.0.0.1:1540"
sc create %NameSrvc% binPath= %Command% start= auto obj= .\USR1CV8 password= p-123456 DisplayName= %DisplName% depend= Tcpip/Dnscache/lanmanworkstation/lanmanserver/