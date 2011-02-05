export DEBUG=1
export LOADING_DUMP_DATA=1

cd ../site

echo Serializing remote database...
ssh josh@popvox.com "cd sources/site; ./manage dumpdata --indent=2 auth registration popvox adserver" > database.json

echo ""
echo Initializing local database
rm database.sqlite
./manage syncdb --noinput

#./manage flush --noinput

./manage loaddata database.json
