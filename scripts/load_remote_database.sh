export DEBUG=1
export DONT_CREATE_USERPROFILES=1

cd ../www_popvox_com

ssh popvox@occams "cd www_popvox_com; python manage.py dumpdata --format=xml --indent=2 auth registration popvox" > database.xml

rm database.sqlite
python manage.py syncdb --noinput

#python manage.py flush --noinput

python manage.py loaddata database.xml
