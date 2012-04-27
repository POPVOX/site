#!runscript -u

# This is one of four backup mechanisms we have for our MySQL database.
#
# 1) The persistent volume is an Amazon EBS volume, so it is supposedly redundantly
#    stored, but we don't have history so that doesn't protect against accidental drops.
# 2) We use rdiff-backup to store history of a database dump, saved to the EBS volume,
#    but that doesn't protect against damage to the filesystem, and since it is a dump
#    and not the raw database files, restoring may be more difficult. This is run daily.
# 3) We make occasional AWS snapshots of the volume, but the database may be in an
#    unflushed/inconsistent state at the time of the snapshot, so the db may require
#    repair when the snapshot is mounted.
# 4) This script makes a hot copy of each table and stores the table files (frm, MYD, MYI)
#    into an S3 bucket. We write new copies to S3 each time, so we preserve histoy,
#    although this is not yet run on a regular basis. But at least the tables will
#    be internally consistent since we flush before copying. Since we don't want to
#    affect the live operation of the site, we don't create a global lock, which means
#    there may be inconsistencies between tables, i.e. bad foreign keys.

# The strategy here is basically for each table:
#    Create a temporary directory in /tmp.
#    LOCK TABLES table
#    FLUSH TABLES table
#    Copy .frm, .MYD, .MYI files to a temporary directory.
#    UNLOCK TABLES
#    Upload .frm, .MYD, .MYI files to S3.
#    Delete the temporary directory.
#
# One down-side to this script is that you need read access to the MySQL database
# table files, which are typically accessible only to the mysql user. We've made
# them world-readable, but ALTER TABLE seems to reset permissions.

from datetime import datetime
from glob import glob
from os.path import basename
import tempfile, shutil

from django.db import connection

from boto.s3.connection import S3Connection
from boto.s3.key import Key

from settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

encrypt_tables = ["auth_user", "popvox_postaladdress", "popvox_serviceaccountcampaignactionrecord", "writeyourrep_deliveryrecord"] # activate S3's server side encrpytion

# In order to interfere with the live site minimally, we backup each table
# one by one. That could leave the db in an inconsistent state.

# root path for backups
file_root = datetime.now().isoformat() + "/db"

# open connection to S3
s3 = S3Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
bucket = s3.create_bucket('backups.popvox.com')

# get a list of tables in our database
cur = connection.cursor()
cur.execute("SHOW TABLES")
tables = [t[0] for t in cur.fetchall()]

# for each table...
for table in tables:
	print table, "..."

	tmp = tempfile.mkdtemp()
	try:
		# Lock the tables, flush, copy table files to a temporary location, then unlock.
		cur.execute("LOCK TABLES %s READ" % table)
		cur.execute("FLUSH TABLES %s" % table)
		try:
			for f in glob("/mnt/persistent/mysql/popvox/%s.*" % table):
				shutil.copy2(f, tmp)
		finally:
			cur.execute("UNLOCK TABLES")
		print "\tcopied & unlocked"

		# Upload copied files to S3.
		for f in glob(tmp + "/*"):
			k = Key(bucket)
			k.key = file_root + "/" + basename(f)
			print "\t" + k.key + "..."
			k.set_contents_from_filename(f, encrypt_key=table in encrypt_tables)
	finally:
		shutil.rmtree(tmp)

