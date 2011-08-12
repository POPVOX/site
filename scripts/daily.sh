SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
$SCRIPTS/update_fans.py
EMAIL_BACKEND=AWS-SES SEND=SEND python popvox/send_mass_emails.py survey
python popvox/db/update_bill_metadata.py
python popvox/db/compute_prompts.py
./manage cleanup
./manage clear_expired_email_verifications

sudo indexer --all --rotate

cd /mnt/persistent
$SCRIPTS/backup.sh
