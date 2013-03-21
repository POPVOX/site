#!/bin/bash

MYUSER=popvoxdb
REMOTEDB=10.73.70.84
if [ -f ~/slave ]; then
	source ~/slave
	MYUSER=slave
fi

mysql -u $MYUSER -h $REMOTEDB -p"qsg;5TtC" popvox "$@"

