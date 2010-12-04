export DEBUG=1
export DONT_CREATE_USERPROFILES=1

cd ../site

ssh josh@popvox.com "cd sources/site; ./manage dumpdata --indent=2 auth registration popvox" > database.json

rm database.sqlite
./manage syncdb --noinput

#./manage flush --noinput

./manage loaddata database.json
