#!/bin/bash

MYUSER=root
REMOTEDB=localhost
if [ -f ~/slave ]; then
	source ~/slave
	MYUSER=slave
fi

mysql -u $MYUSER -h $REMOTEDB -p"qsg;5TtC" popvox "$@"

