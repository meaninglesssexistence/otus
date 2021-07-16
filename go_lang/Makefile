# Сборка
build: appsinstalled.pb.go
	go build

# Инициализация и загрузка зависимостей
init: go.mod
	go get github.com/bradfitz/gomemcache/memcache
	go get github.com/golang/protobuf/proto
	go get google.golang.org/protobuf/reflect/protoreflect
	go get google.golang.org/protobuf/runtime/protoimpl

# Удаление временных файлов
clean:
	-rm go.mod go.sum appsinstalled.pb.go memc_load.exe memc_load

# Запуск программы в "простом" тестовом режиме
test-soft: build
	./memc_load -t

# Запуск программы в "боевом" тестовом режиме
test-hard: build
	./memc_load -pattern *.tsv.gz

# Запуск четырех копий memcached
startsvc:
	memcached.exe -d -p 33013
	memcached.exe -d -p 33014
	memcached.exe -d -p 33015
	memcached.exe -d -p 33016

go.mod:
	go mod init example.com/memc_load

appsinstalled.pb.go: appsinstalled.proto
	protoc --go_out=. --go_opt=Mappsinstalled.proto=. appsinstalled.proto
