# To be run from /mnt/persistent.

mkdir -p backup/last

mysqldump popvox -u root "-pqsg;5TtC" \
	--ignore-table=popvox.django_session \
	--ignore-table=popvox.popvox_positiondocument \
	--ignore-table=popvox.popvox_documentpage \
	--ignore-table=popvox.adserver_sitepath \
	--ignore-table=popvox.adserver_impressionblock \
	--ignore-table=popvox.adserver_impression \
	--ignore-table=popvox.adserver_targetimpressionblock \
	--ignore-table=popvox.congressionaldistrictpolygons \
	--ignore-table=popvox.countypolygons \
	--ignore-table=popvox.trafficanalysis_hit \
	--ignore-table=popvox.trafficanalysis_liverecord \
	> backup/last/database.sql
mysqldump popvox -u root "-pqsg;5TtC" popvox_positiondocument --where "doctype <> 100" >> backup/last/database.sql

mysqldump popvox -u root "-pqsg;5TtC" \
	adserver_sitepath adserver_impressionblock adserver_impression adserver_targetimpressionblock \
	> backup/last/adserver_database.sql

mysqldump popvox -u root "-pqsg;5TtC" \
	congressionaldistrictpolygons countypolygons \
	> backup/last/database_gis.sql

mysqldump popvox -u root "-pqsg;5TtC" \
	trafficanalysis_hit trafficanalysis_liverecord \
	> backup/last/database_logs.sql

rdiff-backup backup/last backup/rdiff
rdiff-backup --force --remove-older-than 30D backup/rdiff/

