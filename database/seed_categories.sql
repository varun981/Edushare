-- EduShare default categories.
-- Safe to re-run: INSERT IGNORE relies on the unique name/slug constraints.
-- Run after database/init_mysql.sql, or use `flask init-db` from the app instead.

USE edushare;

INSERT IGNORE INTO categories (name, slug, icon, description, is_active, created_at) VALUES
  ('School Books', 'school-books', 'bi-book', 'School Books shared by the EduShare community.', 1, NOW()),
  ('PUC Books', 'puc-books', 'bi-journal-text', 'PUC Books shared by the EduShare community.', 1, NOW()),
  ('Diploma Books', 'diploma-books', 'bi-award', 'Diploma Books shared by the EduShare community.', 1, NOW()),
  ('Engineering Books', 'engineering-books', 'bi-cpu', 'Engineering Books shared by the EduShare community.', 1, NOW()),
  ('Medical Books', 'medical-books', 'bi-heart-pulse', 'Medical Books shared by the EduShare community.', 1, NOW()),
  ('Degree Books', 'degree-books', 'bi-mortarboard', 'Degree Books shared by the EduShare community.', 1, NOW()),
  ('Competitive Exam Books', 'competitive-exam-books', 'bi-trophy', 'Competitive Exam Books shared by the EduShare community.', 1, NOW()),
  ('Handwritten Notes', 'handwritten-notes', 'bi-pencil-square', 'Handwritten Notes shared by the EduShare community.', 1, NOW()),
  ('Previous-Year Question Papers', 'previous-year-question-papers', 'bi-file-earmark-text', 'Previous-Year Question Papers shared by the EduShare community.', 1, NOW()),
  ('Laboratory Manuals', 'laboratory-manuals', 'bi-flask', 'Laboratory Manuals shared by the EduShare community.', 1, NOW()),
  ('Reference Books', 'reference-books', 'bi-library', 'Reference Books shared by the EduShare community.', 1, NOW()),
  ('Study Materials', 'study-materials', 'bi-journal-code', 'Study Materials shared by the EduShare community.', 1, NOW());
