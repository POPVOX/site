SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
#SEND=SEND python popvox/send_mass_emails.py survey
python popvox/db/update_fans.py
python popvox/db/update_bill_metadata.py
python popvox/db/compute_prompts.py
python popvox/db/update_bill_text.py
python annalee/morningtea.py
./manage cleanup
./manage clear_expired_email_verifications

sudo indexer --all --rotate

cd /mnt/persistent
$SCRIPTS/backup.sh
