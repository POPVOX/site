SCRIPTS=/home/www/sources/scripts

cd /home/www/sources/site
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=settings
python popvox/registration_followup.py welcome


