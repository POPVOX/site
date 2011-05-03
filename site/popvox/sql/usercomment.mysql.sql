ALTER TABLE popvox_usercomment ADD INDEX bill_district(bill_id, state, congressionaldistrict, created);
ALTER TABLE popvox_usercomment ADD INDEX bill_state(bill_id, state, created);
ALTER TABLE popvox_usercomment ADD INDEX district(state, congressionaldistrict, created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_created(created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_state_created(state, created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_state_district_created(state, congressionaldistrict, created);

