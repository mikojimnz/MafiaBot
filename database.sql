-- MySQL Script generated by MySQL Workbench
-- Wed Jul  8 00:41:18 2020
-- Model: New Model    Version: 1.0
-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema mydb
-- -----------------------------------------------------
-- -----------------------------------------------------
-- Schema Reddit
-- -----------------------------------------------------
DROP SCHEMA IF EXISTS `Reddit` ;

-- -----------------------------------------------------
-- Schema Reddit
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `Reddit` DEFAULT CHARACTER SET utf8 COLLATE utf8_bin ;
-- -----------------------------------------------------
-- Schema reddit
-- -----------------------------------------------------
DROP SCHEMA IF EXISTS `reddit` ;

-- -----------------------------------------------------
-- Schema reddit
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `reddit` ;
USE `Reddit` ;

-- -----------------------------------------------------
-- Table `Reddit`.`Log`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `Reddit`.`Log` ;

CREATE TABLE IF NOT EXISTS `Reddit`.`Log` (
  `utc` INT NOT NULL,
  `username` VARCHAR(20) CHARACTER SET 'utf8' COLLATE 'utf8_bin' NOT NULL,
  `action` VARCHAR(255) CHARACTER SET 'utf8' COLLATE 'utf8_bin' NOT NULL,
  PRIMARY KEY (`utc`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8
COLLATE = utf8_bin;


-- -----------------------------------------------------
-- Table `Reddit`.`Mafia`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `Reddit`.`Mafia` ;

CREATE TABLE IF NOT EXISTS `Reddit`.`Mafia` (
  `utc` INT NOT NULL,
  `username` VARCHAR(20) CHARACTER SET 'utf8' COLLATE 'utf8_bin' NOT NULL,
  `team` INT NOT NULL,
  `tier` INT NOT NULL DEFAULT '0',
  `alive` INT NOT NULL DEFAULT '1',
  `diedOnCycle` INT NULL DEFAULT NULL,
  `burn` INT NOT NULL DEFAULT '1',
  `revive` INT NOT NULL DEFAULT '1',
  `request` INT NOT NULL DEFAULT '3',
  `comment` INT NOT NULL DEFAULT '0',
  `inactive` INT NOT NULL DEFAULT '0',
  PRIMARY KEY (`utc`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8
COLLATE = utf8_bin;

CREATE UNIQUE INDEX `Mafiacol_UNIQUE` ON `Reddit`.`Mafia` (`username` ASC) VISIBLE;


-- -----------------------------------------------------
-- Table `Reddit`.`VoteCall`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `Reddit`.`VoteCall` ;

CREATE TABLE IF NOT EXISTS `Reddit`.`VoteCall` (
  `username` VARCHAR(20) CHARACTER SET 'utf8' COLLATE 'utf8_bin' NOT NULL,
  `vote` VARCHAR(20) CHARACTER SET 'utf8' COLLATE 'utf8_bin' NOT NULL,
  PRIMARY KEY (`username`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8
COLLATE = utf8_bin;

CREATE UNIQUE INDEX `username_UNIQUE` ON `Reddit`.`VoteCall` (`username` ASC) VISIBLE;

USE `reddit` ;
USE `Reddit` ;

-- -----------------------------------------------------
-- procedure role_cnt
-- -----------------------------------------------------

USE `Reddit`;
DROP procedure IF EXISTS `Reddit`.`role_cnt`;

DELIMITER $$
USE `Reddit`$$
CREATE DEFINER=`root`@`localhost` PROCEDURE `role_cnt`()
BEGIN
SELECT team,COUNT(*) as cnt 
FROM Mafia 
GROUP BY team 
ORDER BY team DESC;
END$$

DELIMITER ;

-- -----------------------------------------------------
-- procedure role_cnt_alive
-- -----------------------------------------------------

USE `Reddit`;
DROP procedure IF EXISTS `Reddit`.`role_cnt_alive`;

DELIMITER $$
USE `Reddit`$$
CREATE DEFINER=`root`@`localhost` PROCEDURE `role_cnt_alive`()
BEGIN
SELECT team,COUNT(*) as cnt 
FROM Mafia
WHERE alive=1
GROUP BY team 
ORDER BY team DESC;
END$$

DELIMITER ;
USE `reddit` ;

-- -----------------------------------------------------
-- Placeholder table for view `reddit`.`rolecnt`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `reddit`.`rolecnt` (`team` INT, `count` INT);

-- -----------------------------------------------------
-- View `reddit`.`rolecnt`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `reddit`.`rolecnt`;
DROP VIEW IF EXISTS `reddit`.`rolecnt` ;
USE `reddit`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `Reddit`.`rolecnt` AS select `Reddit`.`Mafia`.`team` AS `team`,count(`Reddit`.`Mafia`.`team`) AS `count` from `Reddit`.`Mafia` where (`Reddit`.`Mafia`.`alive` = '1') group by `Reddit`.`Mafia`.`team` order by `Reddit`.`Mafia`.`team` desc;

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
