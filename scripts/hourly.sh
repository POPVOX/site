SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings

python popvox/update_bill_metadata.py

python popvox/send_mass_emails.py welcome


