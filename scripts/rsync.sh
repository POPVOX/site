rsync -avz --delete --delete-excluded \
 govtrack.us::govtrackdata/ ../data/govtrack/ \
 --exclude "*.pdf" --exclude "*.tgz" --exclude "*.gz" \
 --exclude "photos" --exclude "rdf" --exclude "us/fec" \
 --exclude "us/*/repstats" --exclude "us/*/repstats.person" --exclude "us/*/bills.amdt" --exclude "us/*/bills.summary" --exclude "us/*/rolls" \
 --exclude "us/*/index.*" --exclude "us/*/gen.*" \
 --exclude "us/{1..95}" --exclude "us/*/cr" --exclude "us/*/bills.cbo" \
 --exclude "us/bills.text*"
