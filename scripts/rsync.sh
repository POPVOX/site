# To be run from /mnt/persistent
rsync -az --delete --delete-excluded 10.112.57.60::govtrackdata data/govtrack --exclude "us/bills.text*" --exclude rdf --exclude "**/repstats" --exclude "**/repstats.person" --exclude "**/index.*" --exclude "us/gis" --exclude "us/fec" --exclude "us/*/cr" --exclude "**/gen.*" --exclude "**/bills.cbo" --exclude "**/bills.ombsap" --exclude "**/stats" --exclude misc/database.sql.gz

