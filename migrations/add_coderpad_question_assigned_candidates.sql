USE dump;

ALTER TABLE coderpad_question
    ADD COLUMN assigned_candidate_ids JSON NULL AFTER test_cases;
