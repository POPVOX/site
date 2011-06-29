# To be run from /mnt/persistent
rsync -avz 10.112.57.60::govtrackdata data/govtrack --exclude "us/bills.text*" --exclude rdf --exclude "**/repstats" --exclude "**/repstats.person" --exclude "**/index.*" --exclude "us/gis" --exclude "us/fec" --exclude "us/*/cr" --exclude "**/gen.*" --exclude "**/bills.cbo" --exclude "**/bills.ombsap" --exclude "**/stats" --exclude misc/database.sql.gz --exclude "us/10*" --exclude "us/110" --exclude "us/111" --exclude "us/9*" --exclude "photos"

