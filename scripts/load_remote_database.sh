export DEBUG=1
export DONT_CREATE_USERPROFILES=1

cd ../site

ssh www@popvox.com "cd sources/site; python manage.py dumpdata --settings=settings --indent=2 auth registration popvox trafficanalysis" > database.json

rm database.sqlite
python manage.py syncdb --noinput --settings=settings

#python manage.py flush --noinput --settings=settings

python manage.py loaddata --settings=settings database.json
