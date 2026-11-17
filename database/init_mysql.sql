-- EduShare MySQL schema.
-- Generated from app/models.py with `python tools/export_mysql_schema.py`.
-- Run against an existing database after creating the database and user yourself.
-- The application also creates missing tables when AUTO_CREATE_TABLES=1.
--
-- Example (substitute your own values):
--   mysql -h DB_HOST -u DB_USER -p DB_NAME < database/init_mysql.sql

CREATE DATABASE IF NOT EXISTS edushare
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE edushare;

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS categories (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	slug VARCHAR(110) NOT NULL, 
	icon VARCHAR(60), 
	description TEXT, 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE UNIQUE INDEX ix_categories_slug ON categories (slug);

CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	full_name VARCHAR(120) NOT NULL, 
	email VARCHAR(190) NOT NULL, 
	phone VARCHAR(30), 
	password_hash VARCHAR(255) NOT NULL, 
	educational_qualification VARCHAR(120), 
	institution VARCHAR(180), 
	location VARCHAR(180), 
	latitude FLOAT, 
	longitude FLOAT, 
	profile_image VARCHAR(255), 
	bio TEXT, 
	is_admin BOOL NOT NULL, 
	is_blocked BOOL NOT NULL, 
	is_active_account BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_seen DATETIME, 
	PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS educational_materials (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	category_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	author VARCHAR(150), 
	subject VARCHAR(120), 
	educational_level VARCHAR(120), 
	listing_type VARCHAR(20) NOT NULL, 
	description TEXT, 
	`condition` VARCHAR(30), 
	price NUMERIC(10, 2) NOT NULL, 
	original_price NUMERIC(10, 2), 
	location VARCHAR(180), 
	latitude FLOAT, 
	longitude FLOAT, 
	contact_info VARCHAR(180), 
	status VARCHAR(20) NOT NULL, 
	views INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE SET NULL
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_material_filters ON educational_materials (listing_type, status, category_id);

CREATE INDEX ix_educational_materials_listing_type ON educational_materials (listing_type);

CREATE INDEX ix_material_search ON educational_materials (title, author, subject);

CREATE INDEX ix_educational_materials_created_at ON educational_materials (created_at);

CREATE INDEX ix_educational_materials_status ON educational_materials (status);

CREATE INDEX ix_educational_materials_user_id ON educational_materials (user_id);

CREATE INDEX ix_educational_materials_category_id ON educational_materials (category_id);

CREATE TABLE IF NOT EXISTS library_books (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	owner_id INTEGER NOT NULL, 
	category_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	author VARCHAR(150), 
	subject VARCHAR(120), 
	description TEXT, 
	`condition` VARCHAR(30), 
	borrowing_duration_days INTEGER NOT NULL, 
	location VARCHAR(180), 
	latitude FLOAT, 
	longitude FLOAT, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE SET NULL
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_library_books_created_at ON library_books (created_at);

CREATE INDEX ix_library_books_status ON library_books (status);

CREATE INDEX ix_library_books_owner_id ON library_books (owner_id);

CREATE INDEX ix_library_books_category_id ON library_books (category_id);

CREATE TABLE IF NOT EXISTS notifications (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	type VARCHAR(40) NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	message TEXT, 
	link VARCHAR(255), 
	is_read BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_notifications_created_at ON notifications (created_at);

CREATE INDEX ix_notifications_is_read ON notifications (is_read);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE IF NOT EXISTS borrowing_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	book_id INTEGER NOT NULL, 
	borrower_id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	requested_duration_days INTEGER NOT NULL, 
	message TEXT, 
	status VARCHAR(20) NOT NULL, 
	borrow_date DATE, 
	expected_return_date DATE, 
	actual_return_date DATE, 
	reminder_sent_on DATE, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(book_id) REFERENCES library_books (id) ON DELETE CASCADE, 
	FOREIGN KEY(borrower_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_borrowing_records_book_id ON borrowing_records (book_id);

CREATE INDEX ix_borrowing_records_status ON borrowing_records (status);

CREATE INDEX ix_borrowing_records_owner_id ON borrowing_records (owner_id);

CREATE INDEX ix_borrowing_records_expected_return_date ON borrowing_records (expected_return_date);

CREATE INDEX ix_borrowing_records_borrower_id ON borrowing_records (borrower_id);

CREATE TABLE IF NOT EXISTS conversations (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	participant1_id INTEGER NOT NULL, 
	participant2_id INTEGER NOT NULL, 
	topic VARCHAR(255), 
	material_id INTEGER, 
	library_book_id INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_conversation UNIQUE (participant1_id, participant2_id, topic), 
	FOREIGN KEY(participant1_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(participant2_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(material_id) REFERENCES educational_materials (id) ON DELETE SET NULL, 
	FOREIGN KEY(library_book_id) REFERENCES library_books (id) ON DELETE SET NULL
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_conversations_participant2_id ON conversations (participant2_id);

CREATE INDEX ix_conversations_participant1_id ON conversations (participant1_id);

CREATE TABLE IF NOT EXISTS donation_requests (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requester_id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	message TEXT, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_donation_request UNIQUE (requester_id, material_id), 
	FOREIGN KEY(requester_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(material_id) REFERENCES educational_materials (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_donation_requests_owner_id ON donation_requests (owner_id);

CREATE INDEX ix_donation_requests_requester_id ON donation_requests (requester_id);

CREATE INDEX ix_donation_requests_status ON donation_requests (status);

CREATE INDEX ix_donation_requests_material_id ON donation_requests (material_id);

CREATE TABLE IF NOT EXISTS exchange_requests (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requester_id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	offered_material_id INTEGER, 
	message TEXT, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_exchange_request UNIQUE (requester_id, material_id), 
	FOREIGN KEY(requester_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(material_id) REFERENCES educational_materials (id) ON DELETE CASCADE, 
	FOREIGN KEY(offered_material_id) REFERENCES educational_materials (id) ON DELETE SET NULL
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_exchange_requests_status ON exchange_requests (status);

CREATE INDEX ix_exchange_requests_owner_id ON exchange_requests (owner_id);

CREATE INDEX ix_exchange_requests_requester_id ON exchange_requests (requester_id);

CREATE INDEX ix_exchange_requests_material_id ON exchange_requests (material_id);

CREATE TABLE IF NOT EXISTS material_images (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	material_id INTEGER, 
	library_book_id INTEGER, 
	filename VARCHAR(255) NOT NULL, 
	is_primary BOOL NOT NULL, 
	uploaded_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_image_owner CHECK (material_id IS NOT NULL OR library_book_id IS NOT NULL), 
	FOREIGN KEY(material_id) REFERENCES educational_materials (id) ON DELETE CASCADE, 
	FOREIGN KEY(library_book_id) REFERENCES library_books (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_material_images_library_book_id ON material_images (library_book_id);

CREATE INDEX ix_material_images_material_id ON material_images (material_id);

CREATE TABLE IF NOT EXISTS purchase_requests (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	buyer_id INTEGER NOT NULL, 
	seller_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	message TEXT, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_purchase_request UNIQUE (buyer_id, material_id), 
	FOREIGN KEY(buyer_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(seller_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(material_id) REFERENCES educational_materials (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_purchase_requests_seller_id ON purchase_requests (seller_id);

CREATE INDEX ix_purchase_requests_buyer_id ON purchase_requests (buyer_id);

CREATE INDEX ix_purchase_requests_material_id ON purchase_requests (material_id);

CREATE INDEX ix_purchase_requests_status ON purchase_requests (status);

CREATE TABLE IF NOT EXISTS reports (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	reporter_id INTEGER NOT NULL, 
	material_id INTEGER, 
	library_book_id INTEGER, 
	reported_user_id INTEGER, 
	reason VARCHAR(80) NOT NULL, 
	details TEXT, 
	status VARCHAR(20) NOT NULL, 
	admin_notes TEXT, 
	created_at DATETIME NOT NULL, 
	reviewed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(material_id) REFERENCES educational_materials (id) ON DELETE CASCADE, 
	FOREIGN KEY(library_book_id) REFERENCES library_books (id) ON DELETE CASCADE, 
	FOREIGN KEY(reported_user_id) REFERENCES users (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_reports_library_book_id ON reports (library_book_id);

CREATE INDEX ix_reports_reported_user_id ON reports (reported_user_id);

CREATE INDEX ix_reports_material_id ON reports (material_id);

CREATE INDEX ix_reports_reporter_id ON reports (reporter_id);

CREATE INDEX ix_reports_status ON reports (status);

CREATE TABLE IF NOT EXISTS messages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	conversation_id INTEGER NOT NULL, 
	sender_id INTEGER NOT NULL, 
	receiver_id INTEGER NOT NULL, 
	body TEXT NOT NULL, 
	is_read BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
	FOREIGN KEY(sender_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(receiver_id) REFERENCES users (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_messages_receiver_id ON messages (receiver_id);

CREATE INDEX ix_messages_is_read ON messages (is_read);

CREATE INDEX ix_messages_created_at ON messages (created_at);

CREATE INDEX ix_messages_sender_id ON messages (sender_id);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

SET FOREIGN_KEY_CHECKS = 1;
