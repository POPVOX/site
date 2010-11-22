SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh
$SCRIPTS/backup.sh

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
$SCRIPTS/update_fans.py
python popvox/registration_followup.py
python popvox/update_bill_metadata.py

