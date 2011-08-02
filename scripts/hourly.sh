SCRIPTS=/home/www/sources/scripts

cd /mnt/persistent
$SCRIPTS/rsync.sh

cd /home/www/sources/site

popvox/db/update_bill_metadata.py

EMAIL_BACKEND=AWS-SES popvox/send_mass_emails.py welcome

EMAIL_BACKEND=AWS-SES ./manage resend_email_verifications send
