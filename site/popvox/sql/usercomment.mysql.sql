ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_created(created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_bill_created(bill_id, created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_state_created(state, created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_state_district_created(state, congressionaldistrict, created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_state_bill_created(state, bill_id, created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_state_district_bill_created(state, congressionaldistrict, bill_id, created);
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_bill_commentisnull(bill_id, message(1));
ALTER TABLE popvox_usercomment ADD INDEX popvox_usercomment_bill_position_created(bill_id, position, created);

