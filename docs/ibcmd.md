"c:\Program Files\1cv8\8.3.27.1508\bin\ibcmd.exe" infobase config -c "dump-standalone.cfg" export --sync --force --data=d:\tmp\ibcmd-data\ "d:\Repos\BIT\src\cf" < logo-pass.txt

содержимое dump-standalone.cfg :
database:
    dbms: MSSQLServer
    server: sql-server
    name: dbName
    user: dbUser
    password: dbPass

А в файле "logo-pass.txt" - две строки - логин и пароль от базы 1с.
Раньше ibcmd не умела принимать логопасы базы и приходилось каждый раз вбивать их вручную. Выкрутился вот таким способом.
Возможно сейчас с этим уже всё нормально и можно логопас базы передавать параметрами командной строки или в конфиг-файлах. Не проверял