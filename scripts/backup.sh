mkdir -p ../backup

export PYTHON_PATH=../www_popvox_com
python $PYTHON_PATH/manage.py dumpdata --indent=2 auth popvox registration phone_number_twilio > ../backup/database.json

mysqldump popvox -u popvox -p`cat ../db_passwd` > ../backup/database.sql

rdiff-backup ../backup ../backup.trace

