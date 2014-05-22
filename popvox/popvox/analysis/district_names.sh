create table if not exists congressional_district_city (state char(2), district int, county text, city text, county_count int, city_count int);
create unique index statedist on congressional_district_city(state, district);
delete from congressional_district_city;
insert into congressional_district_city select state, congressionaldistrict as dist, (select trim(county) from popvox_postaladdress as b where a.state=b.state and a.congressionaldistrict=b.congressionaldistrict group by trim(county) having count(*) > 15 order by count(*) desc limit 1), (select trim(city) from popvox_postaladdress as b where a.state=b.state and a.congressionaldistrict=b.congressionaldistrict group by trim(lower(city)) having count(*) > 15 order by count(*) desc limit 1) from popvox_postaladdress as a where congressionaldistrict>0 group by state, congressionaldistrict having count(*) > 15;

#./mysql_shell.sh  -Be "select * from congressional_district_city order by state, county, city;"
