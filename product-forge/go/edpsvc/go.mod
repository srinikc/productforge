module productforge/edpsvc

go 1.26.0

require (
	github.com/jackc/pgx/v5 v5.11.0
	productforge/artifacts v0.0.0
	productforge/azurestore v0.0.0
	productforge/datastore v0.0.0
	productforge/dualvec v0.0.0
	productforge/edpdata v0.0.0
	productforge/gcsstore v0.0.0
	productforge/gdrivestore v0.0.0
	productforge/migrate v0.0.0
	productforge/objpolicy v0.0.0
	productforge/objstore v0.0.0
	productforge/objstorerest v0.0.0
	productforge/s3store v0.0.0
	productforge/store v0.0.0
)

require (
	github.com/dustin/go-humanize v1.1.0 // indirect
	github.com/go-ini/ini v1.67.0 // indirect
	github.com/goccy/go-json v0.10.3 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/jackc/pgpassfile v1.0.0 // indirect
	github.com/jackc/pgservicefile v0.0.0-20240606120523-5a60cdf6a761 // indirect
	github.com/jackc/puddle/v2 v2.2.2 // indirect
	github.com/klauspost/compress v1.17.9 // indirect
	github.com/klauspost/cpuid/v2 v2.2.8 // indirect
	github.com/mattn/go-isatty v0.0.24 // indirect
	github.com/minio/md5-simd v1.1.2 // indirect
	github.com/minio/minio-go/v7 v7.0.77 // indirect
	github.com/ncruces/go-strftime v1.1.0 // indirect
	github.com/remyoudompheng/bigfft v0.0.0-20230129092748-24d4a6f8daec // indirect
	github.com/rs/xid v1.6.0 // indirect
	golang.org/x/crypto v0.26.0 // indirect
	golang.org/x/net v0.28.0 // indirect
	golang.org/x/sync v0.24.0 // indirect
	golang.org/x/sys v0.49.0 // indirect
	golang.org/x/text v0.29.0 // indirect
	modernc.org/libc v1.80.1 // indirect
	modernc.org/mathutil v1.7.1 // indirect
	modernc.org/memory v1.12.1 // indirect
	modernc.org/sqlite v1.62.0 // indirect
)

replace productforge/artifacts => ../artifacts

replace productforge/azurestore => ../azurestore

replace productforge/datastore => ../datastore

replace productforge/dualvec => ../dualvec

replace productforge/edpdata => ../edpdata

replace productforge/gcsstore => ../gcsstore

replace productforge/gdrivestore => ../gdrivestore

replace productforge/migrate => ../migrate

replace productforge/objpolicy => ../objpolicy

replace productforge/objstore => ../objstore

replace productforge/objstorerest => ../objstorerest

replace productforge/pfaudit => ../pfaudit

replace productforge/s3store => ../s3store

replace productforge/store => ../store
