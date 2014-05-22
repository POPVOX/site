#!/bin/bash

#/home/www/sources/site/mysql_shell.sh -e "select pa.state, pa.congressionaldistrict, count(com.id) as comcount, count(pa.id) as usercount from popvox_postaladdress as pa left join popvox_usercomment as com on (pa.user_id = com.user_id) where pa.id = (select id from popvox_postaladdress as pva where pva.user_id = pa.user_id order by created desc limit 1)     group by pa.state, pa.congressionaldistrict" > ~/sources/site/dist_count.csv

#/home/www/sources/site/mysql_shell.sh -e "select pa.state, count(com.id) as comcount, count(pa.id) as usercount from popvox_postaladdress as pa left join popvox_usercomment as com on (pa.user_id = com.user_id) where pa.id = (select id from popvox_postaladdress as pva where pva.user_id = pa.user_id order by created desc limit 1)     group by pa.state " > ~/sources/site/state_count.csv

/home/www/sources/site/mysql_shell.sh -e "select state, count(*) from popvox_postaladdress where id = (select id from popvox_postaladdress as pva where pva.user_id = popvox_postaladdress.user_id order by created desc limit 1) group by state" > ~/sources/site/user_state_count.csv

/home/www/sources/site/mysql_shell.sh -e "select state, congressionaldistrict2013, count(*) from popvox_postaladdress where id = (select id from popvox_postaladdress as pva where pva.user_id = popvox_postaladdress.user_id order by created desc limit 1) group by state, congressionaldistrict2013" > ~/sources/site/user_dist_count.csv


/home/www/sources/site/mysql_shell.sh -e "select pa.state, congressionaldistrict2013, count(com.id) as comcount from popvox_postaladdress as pa left join popvox_usercomment as com on (pa.user_id = com.user_id) group by state, congressionaldistrict2013" > ~/sources/site/comment_dist_count.csv

/home/www/sources/site/mysql_shell.sh -e "select pa.state, count(com.id) as comcount from popvox_postaladdress as pa left join popvox_usercomment as com on (pa.user_id = com.user_id) group by state" > ~/sources/site/comment_state_count.csv
