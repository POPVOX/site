SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh

cd /home/www/sources/site

popvox/db/update_bill_metadata.py

SEND=SEND popvox/send_mass_emails.py welcome

./manage resend_email_verifications send
