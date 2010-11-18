SCRIPTS=/home/www/sources/scripts

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
$SCRIPTS/update_fans.py
python popvox/registration_followup.py

cd /mnt/persistent
$SCRIPTS/rsync.sh
$SCRIPTS/backup.sh
