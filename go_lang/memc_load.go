package main

import (
	"bufio"
	"compress/gzip"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/bradfitz/gomemcache/memcache"
	"github.com/golang/protobuf/proto"
)

type Config struct {
	TestRun bool   // Тестовый запуск
	LogFile string // Путь до лога
	Dry     bool   // Запуск с парсингом, но без сохранения данных
	Pattern string // Шаблон файлов для парсинга
	IdfaIP  string // Адрес IDFA memcache
	GaidIP  string // Адрес GAID memcache
	AdidIP  string // Адрес ADID memcache
	DvidIP  string // Адрес DVID memcache
}

type AppsInstalled struct {
	DevType string   // Тип устройства
	DevId   string   // Идентификатор устройства
	Lat     float64  // Широта
	Lon     float64  // Долгота
	Apps    []uint32 // Установленные приложения
}

type Stat struct {
	Processed uint64 // Количество обработанных записей
	Errors    uint64 // Количество необработанных записей
}

type PackedData struct {
	Key  string // Ключ для хранения в Memcache
	Data []byte // Значение для хранения в Memcache
}

const BufferSize = 30

// Парсим данные, заполняя результатом структуру AppsInstalled.
func parseAppsInstalled(s string) (*AppsInstalled, error) {
	lineParts := strings.Split(strings.TrimSpace(s), "\t")

	if len(lineParts) < 5 {
		return nil, errors.New("Too few parts in the string")
	}
	if len(lineParts[0]) == 0 {
		return nil, errors.New("Missed device type")
	}
	if len(lineParts[1]) == 0 {
		return nil, errors.New("Missed device id")
	}

	lat, err := strconv.ParseFloat(lineParts[2], 64)
	if err != nil {
		return nil, err
	}
	lon, err := strconv.ParseFloat(lineParts[3], 64)
	if err != nil {
		return nil, err
	}

	appParts := strings.Split(lineParts[4], ",")

	var appIds []uint32
	for _, appStr := range appParts {
		id, err := strconv.ParseUint(appStr, 10, 32)
		if err == nil {
			appIds = append(appIds, uint32(id))
		}
	}

	if len(appParts) != len(appIds) {
		log.Printf("Not all user apps are digits %s\n", lineParts[4])
	}

	a := &AppsInstalled{
		DevType: lineParts[0],
		DevId:   lineParts[1],
		Lat:     lat,
		Lon:     lon,
		Apps:    appIds,
	}

	return a, nil
}

// Тестируем парсинг данных, используя заданную строчку
// исходных данных.
func prototest() {
	sample := "idfa\t1rfw452y52g2gq4g\t55.55\t42.42\t1423,43,567,3,7,23\ngaid\t7rfw452y52g2gq4g\t55.55\t42.42\t7423,424"

	for _, line := range strings.Split(sample, "\n") {
		apps, err := parseAppsInstalled(line)
		if err != nil {
			log.Fatalln("Failed to parse string:", err)
		}

		ua := &UserApps{
			Apps: apps.Apps,
			Lat:  &apps.Lat,
			Lon:  &apps.Lon,
		}

		packed, err := proto.Marshal(ua)
		if err != nil {
			log.Fatalln("Failed to encode user applications:", err)
		}

		unpacked := &UserApps{}
		if err := proto.Unmarshal(packed, unpacked); err != nil {
			log.Fatalln("Failed to decode user applications:", err)
		}

		if reflect.DeepEqual(ua, unpacked) {
			panic("The packed/unpacked structures differ")
		}
	}
}

// Переименовываем указанный файл, добавляя у имени точку.
func dotRename(path string) error {
	head, fn := filepath.Split(path)
	return os.Rename(path, filepath.Join(head, "."+fn))
}

// Горутина-воркер. Занимается маршалингом данных в формат protobuf
// и отправкой данных на Memcache сервер.
func sendToMemcache(ch <-chan *AppsInstalled, stat *Stat,
	memCacheIP string, dry bool, exit chan bool,
	wg *sync.WaitGroup) {
	defer wg.Done()

	sendChan := make(chan *PackedData, BufferSize)
	exitChan := make(chan bool)

	if !dry {
		wg.Add(1)
		go func() {
			defer wg.Done()

			processed := uint64(0)
			errors := uint64(0)

			mc := memcache.New(memCacheIP)

			for {
				select {
				case <-exitChan:
					stat.Processed = processed
					stat.Errors = errors
					return

				case pair := <-sendChan:
					// Пробуем отправить данные на сервер три раза.
					for attempt := 0; attempt < 3; attempt++ {
						err := mc.Set(&memcache.Item{Key: pair.Key, Value: pair.Data})
						if err == nil {
							processed++
							break
						} else if attempt == 2 {
							errors++
						}
					}
				}
			}
		}()
	}

	for {
		select {
		case <-exit:
			close(exitChan)
			return

		case item := <-ch:
			ua := &UserApps{
				Apps: item.Apps,
				Lat:  &item.Lat,
				Lon:  &item.Lon,
			}

			if packed, err := proto.Marshal(ua); err != nil {
				log.Fatalln("Failed to encode user applications:", err)
			} else {
				pair := &PackedData{
					Key:  fmt.Sprintf("%s:%s", item.DevType, item.DevId),
					Data: packed,
				}

				if dry {
					log.Printf("%s - %s -> %s\n", memCacheIP, pair.Key, pair.Data)
				} else {
					// Передали данные на отправку.
					sendChan <- pair
				}
			}
		}
	}
}

// Открываем и парсим указанный файл. Разобранные
// данные записываем в канал dataChannels.
func loadFile(fn string, dataChannels map[string](chan *AppsInstalled)) (uint64, error) {
	file, err := os.Open(fn)
	if err != nil {
		return 0, err
	}
	defer file.Close()

	gz, err := gzip.NewReader(file)
	if err != nil {
		return 0, err
	}
	defer gz.Close()

	var parseErr uint64 = 0
	scanner := bufio.NewScanner(gz)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if len(line) == 0 {
			continue
		}

		item, err := parseAppsInstalled(line)
		if err != nil {
			parseErr += 1
			continue
		}

		if ch, ok := dataChannels[item.DevType]; ok {
			// Передали данные на отправку.
			// Блокироваться здесь надолго не должны,
			// потому что `sendToMemcache` или передаст
			// данные дальше в `sendXXX` или, если `sendXXX`
			// занят, сохранит их в очереди.
			ch <- item
		} else {
			parseErr += 1
			log.Fatalf("Unknow device type: %s\n", item.DevType)
		}
	}

	if err := scanner.Err(); err != nil {
		return parseErr, err
	}

	return parseErr, nil
}

// Парсим данные из файлов, попалающих под маску config.Pattern.
// Для записи данных выбираем канал из словаря dataChannels.
func loadFiles(config *Config, dataChannels map[string](chan *AppsInstalled)) (uint64, error) {
	matches, err := filepath.Glob(config.Pattern)
	if err != nil {
		return 0, err
	}

	var totalParseErr uint64 = 0
	for _, fn := range matches {
		log.Printf("Processing %s\n", fn)

		parseErr, err := loadFile(fn, dataChannels)
		if err != nil {
			return 0, err
		}

		totalParseErr += parseErr

		err = dotRename(fn)
		if err != nil {
			log.Fatalln("Failed to rename file:", err)
		}
	}

	return totalParseErr, nil
}

// Суммирует количество успешных записей в Memcache
// и ошибок из массива stats и выдает результат.
func printStatistics(parseErrors uint64, stats []Stat) {
	const NormalErrRate = 0.01

	processed := uint64(0)
	errors := parseErrors

	for _, stat := range stats {
		processed += stat.Processed
		errors += stat.Errors
	}

	if processed == 0 {
		return
	}

	errRate := float64(errors) / float64(processed)

	if errRate < NormalErrRate {
		log.Printf("Acceptable error rate (%g). Successfull load\n", errRate)
	} else {
		log.Fatalf("High error rate (%g > %g). Failed load\n", errRate, NormalErrRate)
	}
}

func main() {
	var config Config

	flag.BoolVar(&config.TestRun, "test", false, "test parsing")
	flag.BoolVar(&config.TestRun, "t", false, "test parsing")
	flag.StringVar(&config.LogFile, "log", "", "log file name")
	flag.StringVar(&config.LogFile, "l", "", "log file name")
	flag.BoolVar(&config.Dry, "dry", false, "dry run")
	flag.StringVar(&config.Pattern, "pattern", "/data/appsinstalled/*.tsv.gz", "glob for input file")
	flag.StringVar(&config.IdfaIP, "idfa", "127.0.0.1:33013", "IDFA MemCache address")
	flag.StringVar(&config.GaidIP, "gaid", "127.0.0.1:33014", "GAID MemCache address")
	flag.StringVar(&config.AdidIP, "adid", "127.0.0.1:33015", "ADID MemCache address")
	flag.StringVar(&config.DvidIP, "dvid", "127.0.0.1:33016", "DVID MemCache address")
	flag.Parse()

	if config.LogFile != "" {
		file, err := os.OpenFile(config.LogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0666)
		if err != nil {
			log.Fatal(err)
		}

		log.SetOutput(file)
	}

	if config.TestRun {
		prototest()
		os.Exit(0)
	}

	dataChannels := map[string](chan *AppsInstalled){
		"idfa": make(chan *AppsInstalled, BufferSize),
		"gaid": make(chan *AppsInstalled, BufferSize),
		"adid": make(chan *AppsInstalled, BufferSize),
		"dvid": make(chan *AppsInstalled, BufferSize),
	}

	workerExit := make(chan bool)

	var wg sync.WaitGroup
	wg.Add(len(dataChannels))

	stats := make([]Stat, 4)
	go sendToMemcache(dataChannels["idfa"], &stats[0], config.IdfaIP, config.Dry, workerExit, &wg)
	go sendToMemcache(dataChannels["gaid"], &stats[1], config.GaidIP, config.Dry, workerExit, &wg)
	go sendToMemcache(dataChannels["adid"], &stats[2], config.AdidIP, config.Dry, workerExit, &wg)
	go sendToMemcache(dataChannels["dvid"], &stats[3], config.DvidIP, config.Dry, workerExit, &wg)

	start := time.Now()
	parseErrors, err := loadFiles(&config, dataChannels)
	if err != nil {
		log.Fatalf("Unexpected error: %s\n", err)
		os.Exit(1)
	}

	close(workerExit)
	wg.Wait()

	if !config.Dry {
		printStatistics(parseErrors, stats)
	}

	log.Printf("Processing took %.0f seconds\n", time.Now().Sub(start).Seconds())
}
