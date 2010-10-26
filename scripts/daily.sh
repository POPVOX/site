SCRIPTS=/home/www/sources/scripts

cd /home/www/sources/site
$SCRIPTS/update_fans.py

cd /mnt/persistent
$SCRIPTS/rsync.sh
$SCRIPTS/backup.sh
