# To be run from /mnt/persistent.

mysqldump popvox -u root "-pqsg;5TtC" > backup/last/database.sql

rdiff-backup backup/last backup/rdiff

