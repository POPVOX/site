alter table popvox_usercomment add index bill_district(bill_id, state, congressionaldistrict);
alter table popvox_usercomment add index district(state, congressionaldistrict);

