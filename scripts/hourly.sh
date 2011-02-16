SCRIPTS=/home/www/sources/scripts

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
python popvox/send_mass_emails.py welcome


