-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: erp_master_trivsys
-- ------------------------------------------------------
-- Server version	8.0.45-0ubuntu0.24.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `otp_verification`
--

DROP TABLE IF EXISTS `otp_verification`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `otp_verification` (
  `email` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `otp` varchar(4) COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires` timestamp NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `otp_verification`
--

LOCK TABLES `otp_verification` WRITE;
/*!40000 ALTER TABLE `otp_verification` DISABLE KEYS */;
/*!40000 ALTER TABLE `otp_verification` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tenant_audit_logs`
--

DROP TABLE IF EXISTS `tenant_audit_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tenant_audit_logs` (
  `log_id` int NOT NULL AUTO_INCREMENT,
  `tenant_id` int NOT NULL,
  `action` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `details` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`log_id`),
  KEY `ix_tenant_audit_logs_tenant_id` (`tenant_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tenant_audit_logs`
--

LOCK TABLES `tenant_audit_logs` WRITE;
/*!40000 ALTER TABLE `tenant_audit_logs` DISABLE KEYS */;
INSERT INTO `tenant_audit_logs` VALUES (1,1,'tenant_created','New tenant database created: erp_trivsys','2025-12-16 12:45:42'),(2,2,'tenant_created','New tenant database created: erp_adtech','2025-12-22 12:04:28'),(3,3,'tenant_created','New tenant database created: erp_demotech','2026-01-08 13:37:52');
/*!40000 ALTER TABLE `tenant_audit_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tenant_sessions`
--

DROP TABLE IF EXISTS `tenant_sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tenant_sessions` (
  `token` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_data` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `browser_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tenant_id` int DEFAULT NULL,
  `expires` double NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`token`),
  KEY `tenant_id` (`tenant_id`),
  CONSTRAINT `tenant_sessions_ibfk_1` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tenant_sessions`
--

LOCK TABLES `tenant_sessions` WRITE;
/*!40000 ALTER TABLE `tenant_sessions` DISABLE KEYS */;
INSERT INTO `tenant_sessions` VALUES ('6290074bc64ceed0213feeaad4054fdcef967bb78a11308515666c9c5ab536d4','{\"tenant_id\": 1, \"business_name\": \"Trivsys\", \"email\": \"trivsys@gmail.com\", \"database_name\": \"erp_trivsys\", \"db_host\": \"localhost\", \"db_user\": \"root\", \"is_active\": true, \"expires\": 1766839212.098125}','67711a41-238d-47b2-aab9-ff14da595d2f',1,1766839212.098125,'2025-12-26 12:40:12'),('805996b5bdea94bccadbad61e7d6933940f21190eae44d1f2f0bc349d479066a','{\"tenant_id\": 1, \"business_name\": \"Trivsys\", \"email\": \"trivsys@gmail.com\", \"database_name\": \"erp_trivsys\", \"db_host\": \"localhost\", \"db_user\": \"root\", \"is_active\": true, \"expires\": 1765975554.853738}','25caedc7-04d3-4aaa-a876-edb517187475',1,1765975554.853738,'2025-12-16 12:45:54'),('89ac859320108186bc306441edc1e7525cbcefb221a5442b35534f43501174cc','{\"tenant_id\": 3, \"business_name\": \"demotech\", \"email\": \"abdulwahab96540@gmail.com\", \"database_name\": \"erp_demotech\", \"db_host\": \"localhost\", \"db_user\": \"root\", \"is_active\": true, \"expires\": 1767965886.41872}','43b1b511-5b3e-47d2-b2d7-22cf5f5c182e',3,1767965886.41872,'2026-01-08 13:38:06'),('9a98f5064b6b776ff11472699f34c48d98fbf366488c670555c152862eefbe54','{\"tenant_id\": 2, \"business_name\": \"Adtech\", \"email\": \"asad.dhedhi36@gmail.com\", \"database_name\": \"erp_adtech\", \"db_host\": \"localhost\", \"db_user\": \"root\", \"is_active\": true, \"expires\": 1766491690.642845}','f5a0da97-4099-42c8-a515-107f9fb7b707',2,1766491690.642845,'2025-12-22 12:08:10'),('b00fb6d7331a508cf1108d90faf48d0f2435158b17ed3dddd31616fcb2088f8a','{\"tenant_id\": 1, \"business_name\": \"Trivsys\", \"email\": \"trivsys@gmail.com\", \"database_name\": \"erp_trivsys\", \"db_host\": \"localhost\", \"db_user\": \"root\", \"is_active\": true, \"expires\": 1766498480.216269}','fce1a2a7-9d2f-4961-9515-205314fdd182',1,1766498480.216269,'2025-12-22 14:01:20'),('e73605addcd0edf35cf9a3a8f1dd6f2f1d0701aa8d8b455cc33c4749d5ba6550','{\"tenant_id\": 1, \"business_name\": \"Trivsys\", \"email\": \"trivsys@gmail.com\", \"database_name\": \"erp_trivsys\", \"db_host\": \"localhost\", \"db_user\": \"root\", \"is_active\": true, \"expires\": 1766575862.679627}','aa6875ee-c8d5-4743-beef-f0d85071b9b5',1,1766575862.679627,'2025-12-23 11:31:02');
/*!40000 ALTER TABLE `tenant_sessions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tenants`
--

DROP TABLE IF EXISTS `tenants`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tenants` (
  `tenant_id` int NOT NULL AUTO_INCREMENT,
  `business_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `database_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `db_host` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `db_user` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tenant_phone` varchar(15) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`tenant_id`),
  UNIQUE KEY `database_name` (`database_name`),
  UNIQUE KEY `ix_tenants_business_name` (`business_name`),
  UNIQUE KEY `ix_tenants_email` (`email`),
  KEY `ix_tenants_is_active` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tenants`
--

LOCK TABLES `tenants` WRITE;
/*!40000 ALTER TABLE `tenants` DISABLE KEYS */;
INSERT INTO `tenants` VALUES (1,'Trivsys','trivsys@gmail.com','3709c87b469ea3e6d532340cdde266e5f255b2c3a3f508f66ba711d2226455d9','erp_trivsys','localhost','root','03242627287',1,'2025-12-16 12:45:42','2025-12-16 12:45:42'),(2,'Adtech','asad.dhedhi36@gmail.com','3709c87b469ea3e6d532340cdde266e5f255b2c3a3f508f66ba711d2226455d9','erp_adtech','localhost','root','03242627287',1,'2025-12-22 12:04:28','2025-12-22 12:04:28'),(3,'demotech','abdulwahab96540@gmail.com','8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92','erp_demotech','localhost','root','030030303',1,'2026-01-08 13:37:52','2026-01-08 13:37:52');
/*!40000 ALTER TABLE `tenants` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-15 17:36:44
