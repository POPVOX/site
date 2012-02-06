SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
python popvox/db/update_bill_metadata.py
python annalee/morningtea.py

sudo indexer --all --rotate

