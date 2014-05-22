ALTER TABLE popvox_billsimilarity ADD INDEX sim1 (bill1_id, similarity, bill2_id);
ALTER TABLE popvox_billsimilarity ADD INDEX sim2 (bill2_id, similarity, bill1_id);

