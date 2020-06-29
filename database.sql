-- MySQL dump 10.17  Distrib 10.3.22-MariaDB, for debian-linux-gnueabihf (armv8l)
--
-- Host: 127.0.0.1    Database: Reddit
-- ------------------------------------------------------
-- Server version	10.3.22-MariaDB-0+deb10u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `Log`
--

DROP TABLE IF EXISTS `Log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `Log` (
  `utc` int(11) NOT NULL,
  `username` varchar(20) COLLATE utf8_bin NOT NULL,
  `action` varchar(255) COLLATE utf8_bin NOT NULL,
  PRIMARY KEY (`utc`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `Mafia`
--

DROP TABLE IF EXISTS `Mafia`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `Mafia` (
  `utc` int(11) NOT NULL,
  `username` varchar(20) COLLATE utf8_bin NOT NULL,
  `role` varchar(20) COLLATE utf8_bin NOT NULL,
  `loc` varchar(45) COLLATE utf8_bin DEFAULT NULL,
  `alive` tinyint(3) unsigned NOT NULL DEFAULT 1,
  `diedOnCycle` int(11) DEFAULT NULL,
  `burn` tinyint(4) NOT NULL DEFAULT 1,
  `revive` int(11) NOT NULL DEFAULT 1,
  `request` int(11) NOT NULL DEFAULT 3,
  `comment` int(11) NOT NULL DEFAULT 0,
  `inactive` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`utc`),
  UNIQUE KEY `Mafiacol_UNIQUE` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary table structure for view `RoleCnt`
--

DROP TABLE IF EXISTS `RoleCnt`;
/*!50001 DROP VIEW IF EXISTS `RoleCnt`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `RoleCnt` (
  `role` tinyint NOT NULL,
  `count` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `VoteCall`
--

DROP TABLE IF EXISTS `VoteCall`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `VoteCall` (
  `username` varchar(20) COLLATE utf8_bin NOT NULL,
  `vote` varchar(20) COLLATE utf8_bin NOT NULL,
  PRIMARY KEY (`username`),
  UNIQUE KEY `username_UNIQUE` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Final view structure for view `RoleCnt`
--

/*!50001 DROP TABLE IF EXISTS `RoleCnt`*/;
/*!50001 DROP VIEW IF EXISTS `RoleCnt`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8 */;
/*!50001 SET character_set_results     = utf8 */;
/*!50001 SET collation_connection      = utf8_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`DozenIncBOT`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `RoleCnt` AS select `Mafia`.`role` AS `role`,count(`Mafia`.`role`) AS `count` from `Mafia` where `Mafia`.`alive` = '1' group by `Mafia`.`role` order by `Mafia`.`role` desc */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2020-06-29 15:37:24
