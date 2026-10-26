USE `travel_app`;

CREATE TABLE IF NOT EXISTS `stopover_test` (
    `stopover_id` VARCHAR(36) NOT NULL,
    `address` VARCHAR(500) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `is_active` BIT(1) DEFAULT NULL,
    `latitude` DOUBLE NOT NULL,
    `longitude` DOUBLE NOT NULL,
    `opening_hours` VARCHAR(255) DEFAULT NULL,
    `price_range` VARCHAR(100) DEFAULT NULL,
    `status` VARCHAR(50) DEFAULT NULL,
    `stopover_name` VARCHAR(255) NOT NULL,
    `user_id` VARCHAR(36) NOT NULL,
    `website` VARCHAR(255) DEFAULT NULL,
    `category_id` VARCHAR(36) DEFAULT NULL,
    PRIMARY KEY (`stopover_id`),
    KEY `idx_stopover_test_category_id` (`category_id`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `stopover_image` (
    `image_id` BIGINT NOT NULL AUTO_INCREMENT,
    `stopover_id` CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
    `image_url` TEXT COLLATE utf8mb4_unicode_ci NOT NULL,
    `is_primary` TINYINT(1) DEFAULT 0,
    `display_order` INT DEFAULT 0,
    PRIMARY KEY (`image_id`),
    KEY `fk_stopover_image_test` (`stopover_id`),
    CONSTRAINT `fk_stopover_image_test`
        FOREIGN KEY (`stopover_id`)
        REFERENCES `stopover_test` (`stopover_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;