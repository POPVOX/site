SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
$SCRIPTS/update_fans.py
python popvox/send_mass_emails.py survey
python popvox/db/update_bill_metadata.py
python popvox/db/compute_prompts.py
./manage cleanup
./manage clear_expired_email_verifications

sudo indexer bill_titles --rotate

cd /mnt/persistent
$SCRIPTS/backup.sh
