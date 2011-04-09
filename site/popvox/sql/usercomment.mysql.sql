alter table popvox_usercomment add index bill_district(bill_id, state, congressionaldistrict, created);
alter table popvox_usercomment add index bill_state(bill_id, state, created);
alter table popvox_usercomment add index district(state, congressionaldistrict, created);

