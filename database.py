from decimal import Decimal
from io import BytesIO
import barcode
import mysql.connector
from mysql.connector import Error, pooling
from datetime import datetime, timedelta
from openpyxl import Workbook
import pandas as pd
from sqlalchemy import create_engine,Column, String, DateTime, Boolean, Integer
import streamlit as st
import barcode
from barcode.writer import ImageWriter
import os
from PIL import Image
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import hashlib
import logging
from threading import Lock
from typing import Optional, Dict, Tuple
from types import SimpleNamespace
from sqlalchemy.ext.declarative import declarative_base

"""
Multi-Tenant SaaS Database Architecture
========================================
This module handles:
1. Master database (centralized tenant registry & auth)
2. Dynamic tenant database creation & management
3. Thread-safe connection pooling per tenant
4. Automatic schema provisioning for new tenants

Architecture:
- Master DB: Stores tenant metadata, credentials, audit logs
- Tenant DBs: Isolated per business, stores tenant-specific data
- Connection Pool: Thread-safe, per-tenant connection management
"""

# ============================================================================
# CONFIGURATION
# ============================================================================

# Master database credentials (centralized tenant registry)
MASTER_DB_CONFIG = {
    "host": os.getenv("MASTER_DB_HOST", "localhost"),
    "user": os.getenv("MASTER_DB_USER", "root"),
    "password": os.getenv("MASTER_DB_PASSWORD", "ashiq"),
    "database": os.getenv("MASTER_DB_NAME", "erp_master_trivsys"),
}

# Tenant database template (new tenants use this config structure)
TENANT_DB_TEMPLATE = {
    "host": os.getenv("TENANT_DB_HOST", "localhost"),
    "user": os.getenv("TENANT_DB_USER", "root"),
    "password": os.getenv("TENANT_DB_PASSWORD", "ashiq"),
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
}

# Connection pool sizes
POOL_SIZE = 500
POOL_MAX_OVERFLOW = 1000

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# SQLALCHEMY MODELS FOR MASTER DATABASE
# ============================================================================

Base = declarative_base()


class Tenant(Base):
    """
    Master database table: Stores tenant metadata and credentials.
    
    Each row represents a registered business/organization.
    """
    __tablename__ = "tenants"

    tenant_id = Column(Integer, primary_key=True, autoincrement=True)
    business_name = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # SHA256 hash
    database_name = Column(String(255), unique=True, nullable=False)
    db_host = Column(String(255), nullable=False, default="localhost")
    db_user = Column(String(255), nullable=False)
    tenant_phone = Column(String(15))  # New column for tenant phone number
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Tenant(id={self.tenant_id}, business={self.business_name}, email={self.email})>"


class TenantAuditLog(Base):
    """
    Master database table: Audit trail for tenant operations.
    
    Tracks: login attempts, schema changes, admin actions.
    """
    __tablename__ = "tenant_audit_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    action = Column(String(100), nullable=False)  # 'login', 'logout', 'schema_update', etc.
    details = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AuditLog(tenant_id={self.tenant_id}, action={self.action})>"


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

class DatabaseManager:
    """
    Centralized database connection manager for multi-tenant architecture.
    
    Responsibilities:
    - Master database operations (tenant registry)
    - Dynamic tenant database connections with pooling
    - Thread-safe connection isolation per tenant
    - Automatic schema provisioning for new tenants
    """

    def __init__(self):
        """Initialize connection pools and master DB engine."""
        self._master_engine = None
        self._tenant_engines: Dict[str, object] = {}  # Cache tenant engines
        self._tenant_connections_lock = Lock()  # Thread safety for tenant pool
        self._initialized = False
        # Track which tenant databases have been provisioned (to avoid re-running DDL)
        self._tenant_initialized: Dict[str, bool] = {}

    def initialize_master_db(self) -> bool:
        """
        Initialize master database (creates if not exists).
        
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Step 1: Ensure master database exists
            conn = mysql.connector.connect(
                host=MASTER_DB_CONFIG["host"],
                user=MASTER_DB_CONFIG["user"],
                password=MASTER_DB_CONFIG["password"],
            )
            cursor = conn.cursor()

            # Create master database if not exists
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS {MASTER_DB_CONFIG['database']}
                CHARACTER SET utf8mb4
                COLLATE utf8mb4_unicode_ci;
                """
            )
            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Master database '{MASTER_DB_CONFIG['database']}' verified/created.")

            # Step 2: Create SQLAlchemy engine for master DB
            db_url = (
                f"mysql+pymysql://{MASTER_DB_CONFIG['user']}:"
                f"{MASTER_DB_CONFIG['password']}@{MASTER_DB_CONFIG['host']}/"
                f"{MASTER_DB_CONFIG['database']}"
            )
            self._master_engine = create_engine(
                db_url,
                pool_size=POOL_SIZE,
                max_overflow=POOL_MAX_OVERFLOW,
                pool_recycle=3600,  # Recycle connections every hour
                echo=False,  # Set to True for SQL debugging
            )

            # Step 3: Create all master tables
            Base.metadata.create_all(self._master_engine)
            logger.info("Master database tables created/verified.")

            # Ensure tenant_sessions table exists in master DB (used to store session tokens)
            try:
                mconn = mysql.connector.connect(
                    host=MASTER_DB_CONFIG["host"],
                    user=MASTER_DB_CONFIG["user"],
                    password=MASTER_DB_CONFIG["password"],
                    database=MASTER_DB_CONFIG["database"],
                    charset=MASTER_DB_CONFIG.get("charset", "utf8mb4"),
                )
                mcur = mconn.cursor()
                mcur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tenant_sessions (
                        token VARCHAR(128) PRIMARY KEY,
                        session_data TEXT NOT NULL,
                        browser_id VARCHAR(128) NOT NULL,
                        tenant_id INT,
                        expires DOUBLE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                    """
                )
                mconn.commit()
                mcur.close()
                mconn.close()
                logger.info("Master tenant_sessions table created/verified.")
            except Exception as e:
                logger.warning(f"Failed to ensure master.tenant_sessions: {e}")

            # Add tenant_phone column to the tenants table
            # ALTER_TABLE_QUERY = """
            # ALTER TABLE tenants
            # ADD COLUMN tenant_phone VARCHAR(15) AFTER email;
            # """

            # Execute the query to add the column
            try:
                conn = self.get_master_connection()
                cursor = conn.cursor()
                # cursor.execute(ALTER_TABLE_QUERY)
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to add tenant_phone column: {e}")

            self._initialized = True
            return True

        except Error as e:
            logger.error(f"Failed to initialize master database: {e}")
            return False

    def hash_password(self, password: str) -> str:
        """
        Hash password using SHA256 for secure storage.
        
        Args:
            password: Plain text password
            
        Returns:
            str: SHA256 hashed password (hex)
        """
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify password against stored hash.
        
        Args:
            password: Plain text password from login
            password_hash: Stored hash from master DB
            
        Returns:
            bool: True if password matches
        """
        return self.hash_password(password) == password_hash

    def get_master_session(self) -> Session:
        """
        Get SQLAlchemy session for master database.
        
        Returns:
            Session: Active master DB session (must be closed by caller)
        """
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize_master_db() first.")
        SessionLocal = sessionmaker(bind=self._master_engine)
        return SessionLocal()

    @contextmanager
    def master_session_context(self):
        """
        Context manager for master database transactions.
        
        Usage:
            with db_manager.master_session_context() as session:
                tenant = session.query(Tenant).filter_by(email=email).first()
        """
        session = self.get_master_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Master session error: {e}")
            raise
        finally:
            session.close()

    def create_tenant_database(
        self, business_name: str, email: str, phone_number: str, password: str
    ) -> Tuple[bool, str]:
        """
        Create a new tenant database and register in master DB.
        
        Flow:
        1. Validate inputs
        2. Create physical MySQL database
        3. Provision tenant schema (tables)
        4. Store credentials in master DB
        5. Return credentials
        
        Args:
            business_name: Company/organization name (unique)
            email: Admin email (unique)
            password: Admin password (will be hashed)
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        database_name = f"erp_{business_name.lower().replace(' ', '_')}"

        try:
            # Step 1: Validate tenant doesn't exist
            with self.master_session_context() as session:
                existing = session.query(Tenant).filter(
                    (Tenant.email == email) | (Tenant.business_name == business_name)
                ).first()
                if existing:
                    return False, f"Tenant with email or business name already exists."

            # Step 2: Create tenant database on MySQL server
            conn = mysql.connector.connect(
                host=TENANT_DB_TEMPLATE["host"],
                user=TENANT_DB_TEMPLATE["user"],
                password=TENANT_DB_TEMPLATE["password"],
            )
            cursor = conn.cursor()

            # Create database with proper character set
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS `{database_name}`
                CHARACTER SET utf8mb4
                COLLATE utf8mb4_unicode_ci;
                """
            )
            conn.commit()
            logger.info(f"Created tenant database: {database_name}")

            # Step 3: Provision tenant schema (create tables)
            cursor.execute(f"USE `{database_name}`;")
            self._create_tenant_schema(cursor)
            conn.commit()
            logger.info(f"Provisioned schema for: {database_name}")

            cursor.close()
            conn.close()

            # Step 4: Register tenant in master DB
            password_hash = self.hash_password(password)
            with self.master_session_context() as session:
                tenant = Tenant(
                    business_name=business_name,
                    email=email,
                    password_hash=password_hash,
                    database_name=database_name,
                    db_host=TENANT_DB_TEMPLATE["host"],
                    db_user=TENANT_DB_TEMPLATE["user"],
                    tenant_phone=phone_number,  # Store the phone number
                )
                session.add(tenant)
                session.flush()
                tenant_id = tenant.tenant_id

                # Log audit event
                audit = TenantAuditLog(
                    tenant_id=tenant_id,
                    action="tenant_created",
                    details=f"New tenant database created: {database_name}",
                )
                session.add(audit)

            logger.info(f"Tenant registered in master DB: {email}")
            return True, f"Tenant '{business_name}' created successfully."

        except Error as e:
            logger.error(f"Failed to create tenant database: {e}")
            return False, f"Database creation failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during tenant creation: {e}")
            return False, f"Unexpected error: {str(e)}"

    def _create_tenant_schema(self, cursor) -> None:
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                role ENUM('admin', 'manager', 'staff') DEFAULT 'staff',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_email (email),
                INDEX idx_role (role)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            # tenant_sessions (local copy to avoid missing-table errors if code connects to tenant DB)
            """
            CREATE TABLE IF NOT EXISTS tenant_sessions (
                token VARCHAR(128) PRIMARY KEY,
                session_data TEXT NOT NULL,
                browser_id VARCHAR(128) NOT NULL,
                expires DOUBLE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sku VARCHAR(100) UNIQUE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                cost_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                stock INT DEFAULT 0,
                category_id INT,
                image_url VARCHAR(512),
                barcode_url VARCHAR(512),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_category_id (category_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id INT AUTO_INCREMENT PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                customer_name VARCHAR(255) NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status ENUM('pending', 'processing', 'completed', 'cancelled') DEFAULT 'pending',
                total_amount DECIMAL(10, 2),
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_order_number (order_number),
                INDEX idx_status (status),
                INDEX idx_order_date (order_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                line_total DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
                -- products primary key is `id` (not product_id) so reference that
                FOREIGN KEY (product_id) REFERENCES products(id),
                INDEX idx_order_id (order_id),
                INDEX idx_product_id (product_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id INT AUTO_INCREMENT PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                customer_name VARCHAR(255) NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status ENUM('pending', 'processing', 'completed', 'cancelled') DEFAULT 'pending',
                total_amount DECIMAL(10, 2),
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_order_number (order_number),
                INDEX idx_status (status),
                INDEX idx_order_date (order_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                action VARCHAR(100) NOT NULL,
                table_name VARCHAR(100),
                record_id INT,
                old_values JSON,
                new_values JSON,
                ip_address VARCHAR(45),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_action (action),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,

            """
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(255) NOT NULL,
                customer_number VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT,
                total_price DECIMAL(12,2) DEFAULT 0.00,
                paid_amount DECIMAL(12,2) DEFAULT 0.00,
                due_amount DECIMAL(12,2) DEFAULT 0.00,
                credit_sale BOOLEAN DEFAULT FALSE,
                payment_due_date DATE,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source VARCHAR(50)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS sale_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sale_id INT NOT NULL,
                product_id INT NOT NULL,
                quantity INT NOT NULL DEFAULT 1,
                sale_price DECIMAL(12,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS returns (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sale_id INT,
                product_name VARCHAR(255),
                quantity INT,
                return_amount DECIMAL(12,2),
                return_date DATE,
                customer_name VARCHAR(255),
                reason VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                phone VARCHAR(50),
                service_products TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                vendor_id INT NOT NULL,
                order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_amount DECIMAL(12,2),
                notes TEXT,
                status ENUM('draft','confirmed','completed','cancelled') DEFAULT 'confirmed',
                FOREIGN KEY (vendor_id) REFERENCES vendors(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT,
                vendor_id INT,
                quantity INT,
                purchase_date DATE,
                cost_price DECIMAL(12,2),
                total_amount DECIMAL(14,2),
                -- associate purchases with a purchase order (order_id)
                order_id INT DEFAULT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (vendor_id) REFERENCES vendors(id),
                FOREIGN KEY (order_id) REFERENCES purchase_orders(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                whatsapp_number VARCHAR(20)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS payroll (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT,
                month VARCHAR(20),
                year INT,
                salary DECIMAL(12,2),
                is_paid BOOLEAN DEFAULT 0,
                payment_date DATE,
                UNIQUE(employee_id, month, year),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT,
                status VARCHAR(255),
                date DATE,
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS customer_payments (
                id INT NOT NULL AUTO_INCREMENT,
                customer_name VARCHAR(255) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_customer_name (customer_name),
                KEY idx_payment_date (payment_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            
            """
            CREATE TABLE IF NOT EXISTS credit_payments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            purchase_id INT,
            payment_amount DECIMAL(10,2),
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (purchase_id) REFERENCES purchases(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS vendor_payments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            purchase_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            due_amount DECIMAL(10,2),
            FOREIGN KEY (purchase_id) REFERENCES purchases(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sale_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_date DATETIME NOT NULL,
                payment_method VARCHAR(50) DEFAULT 'Cash',
                payment_note TEXT,
                full_payment int null,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS expenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            amount DECIMAL(10,2) NOT NULL,
            person_name VARCHAR(255) NOT NULL,
            expense_from_account VARCHAR(255),
            description TEXT NOT NULL,
            invoice_file VARCHAR(255) NULL,
            expense_date DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS pos_sessions(
                session_id INT AUTO_INCREMENT PRIMARY KEY,
                opening_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                closing_time DATETIME NULL,
                opening_cash DECIMAL(10,2) DEFAULT 0.00,
                closing_cash DECIMAL(10,2) DEFAULT 0.00,
                status Varchar(50) DEFAULT 'close'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS accounts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account_title VARCHAR(100) NOT NULL,
            account_number VARCHAR(50) UNIQUE NOT NULL,
            account_holder_name VARCHAR(100) NOT NULL,
            opening_balance Decimal(12,2) Default 0.0,
            amount DECIMAL(12,2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            account_id INT NOT NULL,
            txn_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            txn_type ENUM('credit','debit') NOT NULL,
            amount DECIMAL(12,2) NOT NULL,
            description VARCHAR(255),
            reference VARCHAR(50),
            balance_after DECIMAL(12,2),
            category VARCHAR(100),  -- For expense categorization
            created_by VARCHAR(100),  -- Track who made the transaction
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            INDEX idx_account_date (account_id, txn_date),
            INDEX idx_txn_date (txn_date)
        );
        """,
        """
            CREATE TABLE IF NOT EXISTS customer_transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            txn_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            txn_type ENUM('debit', 'credit') NOT NULL,
            amount DECIMAL(15, 2) NOT NULL,
            description TEXT NOT NULL,
            reference VARCHAR(255),
            category VARCHAR(100),
            source VARCHAR(100) DEFAULT 'Manual Transaction',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_customer_name (customer_name),
            INDEX idx_txn_date (txn_date)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS vendor_manual_transactions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        vendor_name VARCHAR(255) NOT NULL,
        txn_date DATETIME NOT NULL,
        txn_type ENUM('debit', 'credit') NOT NULL,
        amount DECIMAL(15, 2) NOT NULL,
        description TEXT,
        reference VARCHAR(255),
        category VARCHAR(100),
        source VARCHAR(100) DEFAULT 'Manual Transaction',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_vendor_name (vendor_name),
        INDEX idx_txn_date (txn_date)
        );
        """,
    ]

        for stmt in ddl_statements:
            cursor.execute(stmt)

        logger.info("Tenant schema provisioned with all tables.")

    # end of _create_tenant_schema

    def get_master_connection(self):
        """Return a raw mysql.connector connection to the master DB."""
        return mysql.connector.connect(
            host=MASTER_DB_CONFIG.get("host", "localhost"),
            user=MASTER_DB_CONFIG.get("user", "root"),
            password=MASTER_DB_CONFIG.get("password", ""),
            database=MASTER_DB_CONFIG.get("database"),
            charset=MASTER_DB_CONFIG.get("charset", "utf8mb4"),
        )

    def get_tenant_connection(self, tenant):
        """Return a mysql.connector connection for a tenant.

        tenant may be a SimpleNamespace / object with `database_name`, a dict,
        or a string containing the database name.
        """
        # Resolve database name
        if isinstance(tenant, dict):
            db_name = tenant.get("database_name")
        elif isinstance(tenant, str):
            db_name = tenant
        else:
            db_name = getattr(tenant, "database_name", None)

        if not db_name:
            raise ValueError("tenant must include database_name")

        # Provision tenant schema once per database (thread-safe)
        with self._tenant_connections_lock:
            if not self._tenant_initialized.get(db_name):
                # Connect and run tenant DDL
                conn = mysql.connector.connect(
                    host=TENANT_DB_TEMPLATE.get("host", "localhost"),
                    user=TENANT_DB_TEMPLATE.get("user", "root"),
                    password=TENANT_DB_TEMPLATE.get("password", ""),
                    database=db_name,
                    charset=TENANT_DB_TEMPLATE.get("charset", "utf8mb4"),
                )
                try:
                    cursor = conn.cursor()
                    # Ensure we're using the tenant database
                    try:
                        cursor.execute(f"USE `{db_name}`;")
                    except Exception:
                        # Some connectors require database specified on connect; ignore if already set
                        pass

                    # Run the DDL provisioning
                    try:
                        self._create_tenant_schema(cursor)
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"Error provisioning tenant schema for {db_name}: {e}")
                    finally:
                        try:
                            cursor.close()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass

                finally:
                    # Mark as initialized even if provisioning had issues to avoid retry storms.
                    self._tenant_initialized[db_name] = True

        # Return a fresh connection to the tenant database
        return mysql.connector.connect(
            host=TENANT_DB_TEMPLATE.get("host", "localhost"),
            user=TENANT_DB_TEMPLATE.get("user", "root"),
            password=TENANT_DB_TEMPLATE.get("password", ""),
            database=db_name,
            charset=TENANT_DB_TEMPLATE.get("charset", "utf8mb4"),
        )


# Create a single shared DatabaseManager instance and initialize master DB
db_manager = DatabaseManager()
try:
    db_manager.initialize_master_db()
except Exception as e:
    logger.warning(f"Master DB initialization at import failed: {e}")


# Convenience wrappers for external modules
def initialize_master_db():
    return db_manager.initialize_master_db()


def signup_tenant(business_name: str, email: str, phone_number: str, password: str) -> Tuple[bool, str]:
    return db_manager.create_tenant_database(business_name, email, phone_number, password)  # Pass phone_number


def login_tenant(email: str, password: str) -> Tuple[bool, Optional[SimpleNamespace], str]:
    try:
        with db_manager.master_session_context() as session:
            tenant = session.query(Tenant).filter_by(email=email).first()
            if not tenant:
                return False, None, "No tenant found with this email"

            if not db_manager.verify_password(password, tenant.password_hash):
                return False, None, "Incorrect password"

            if not tenant.is_active:
                return False, None, "Tenant account is not active"

            tenant_obj = SimpleNamespace(
                tenant_id=tenant.tenant_id,
                business_name=tenant.business_name,
                email=tenant.email,
                database_name=tenant.database_name,
                db_host=tenant.db_host,
                db_user=tenant.db_user,
                is_active=tenant.is_active,
            )
            return True, tenant_obj, "Authenticated"
    except Exception as e:
        logger.error(f"Error during tenant login: {e}")
        return False, None, f"Login error: {e}"
def get_db_connection(tenant=None):
    """
    Return a MySQL connection for the specified tenant or master DB.

    Args:
        tenant (Optional[Tenant]): Tenant object (from login_tenant)
                                If None, connects to master DB.

    Returns:
        mysql.connector.connection.MySQLConnection
    """
    # If an explicit tenant object is provided, use its DB
    if tenant:
        return db_manager.get_tenant_connection(tenant)

    # If running under Streamlit and a tenant is present in session_state,
    # prefer connecting to that tenant's database. This ensures calls that
    # don't pass a tenant explicitly (common in the app) use the tenant DB
    # instead of the master DB.
    try:
        # st is imported at module top-level; check session_state safely
        if 'st' in globals() and hasattr(st, 'session_state'):
            sess = st.session_state
            if sess.get('logged_in') and sess.get('tenant'):
                return db_manager.get_tenant_connection(sess.get('tenant'))
    except Exception:
        # Fall back to master DB on any error
        pass

    # Default: master database connection
    return db_manager.get_master_connection()

# Function to save activity logs
def save_activity_log(activity_description, ip_address):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        query = """
            INSERT INTO activity_logs (activity_description, ip_address)
            VALUES (%s, %s)
        """
        activity_time = datetime.now()  # Timestamp is generated on the server side
        cursor.execute(query, (activity_description, ip_address))
        conn.commit()  # Save the changes
        cursor.close()
        conn.close()

# Function to fetch activity logs
def fetch_activity_logs():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM activity_logs ORDER BY activity_time DESC"
            cursor.execute(query)
            logs = cursor.fetchall()
            conn.close()
            return logs
        except Error as e:
            print(f"Error fetching activity logs: {e}")
            conn.close()
            return []
    return []

# Function to fetch all products from the database
# Function to fetch all products from the database
def fetch_products(category=None):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Handle filtering by category
            if category and category != "All":
                if isinstance(category, dict):
                    category = category.get("name")  # Extract the 'name' field

                query = """
                    SELECT p.id, p.name, p.price, p.stock, p.cost_price, c.name AS category
                    FROM products p
                    JOIN categories c ON p.category_id = c.id
                    WHERE c.name = %s
                """
                cursor.execute(query, (category,))
            else:
                # Fetch all products if no specific category is provided
                query = """
                    SELECT p.id, p.name, p.price, p.stock, p.cost_price, c.name AS category
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                """
                cursor.execute(query)
            
            # Fetch and return results
            products = cursor.fetchall()
            conn.close()
            return products

        except Error as e:
            print(f"Error fetching products: {e}")
            conn.close()
            return []
    return []


# Function to generate barcode
def generate_barcode(product_id, product_name):
    # Define the barcode format and the unique identifier (product name or product ID)
    barcode_format = barcode.get_barcode_class('ean13')  # EAN-13 Barcode
    barcode_data = f"{product_id:012d}"  # Example: You can use product ID as the unique identifier

    # Generate barcode image
    barcode_image = barcode_format(barcode_data, writer=ImageWriter())

    # Save barcode image to a file
    barcode_path = f"barcodes/{product_name}_barcode.png"
    barcode_image.save(barcode_path)

    return barcode_path

# Function to update the product with barcode (Optional)
def update_product_barcode(product_id, barcode_path):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Update product with barcode image path
            cursor.execute("UPDATE products SET barcode_url = %s WHERE id = %s", (barcode_path, product_id))
            conn.commit()
            print(f"✅ Barcode added for product ID {product_id}")
        except Error as e:
            print(f"❌ Error updating product with barcode: {e}")
        finally:
            cursor.close()
            conn.close()


def add_product(name, price, cost_price, stock, category_name, image_path=None):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Check if category exists or insert new
            cursor.execute("SELECT id FROM categories WHERE name = %s", (category_name,))
            category = cursor.fetchone()
            if category:
                category_id = category[0]
            else:
                cursor.execute("INSERT INTO categories (name) VALUES (%s)", (category_name,))
                conn.commit()
                category_id = cursor.lastrowid

            # Insert product
            cursor.execute("""
                INSERT INTO products (name, price, cost_price, stock, category_id, image_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, price, cost_price, stock, category_id, image_path or ''))
            conn.commit()

            product_id = cursor.lastrowid
            print(f"✅ Product '{name}' added with ID {product_id}")
            return product_id

        except Error as e:
            print(f"❌ Error adding product: {e}")
            return None

        finally:
            try:
                cursor.fetchall()  # Clear any remaining results
            except:
                pass
            cursor.close()
            conn.close()



# Function to update the name of a product
def update_name(product_id, new_name):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET name = %s WHERE id = %s",
                (new_name, product_id)
            )
            conn.commit()
            print(f"Name for product {product_id} updated successfully to '{new_name}'.")
        except Error as e:
            print(f"Error updating name: {e}")
        finally:
            conn.close()

# Function to update stock of a product
def update_stock(product_id, new_stock):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET stock = %s WHERE id = %s",
                (new_stock, product_id)
            )
            conn.commit()
            print(f"Stock for product {product_id} updated successfully to {new_stock}.")
        except Error as e:
            print(f"Error updating stock: {e}")
        finally:
            conn.close()

# Function to update price of a product
def update_price(product_id, new_price):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET price = %s WHERE id = %s",
                (new_price, product_id)
            )
            conn.commit()
            print(f"Price for product {product_id} updated successfully to Rs.{new_price}.")
        except Error as e:
            print(f"Error updating price: {e}")
        finally:
            conn.close()

# # Function to update cost price of a product (NEW FUNCTION)
def update_cost_price(product_id, new_cost_price):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET cost_price = %s WHERE id = %s",
                (new_cost_price, product_id)
            )
            conn.commit()
            print(f"Cost Price for product {product_id} updated successfully to Rs.{new_cost_price}.")
        except Error as e:
            print(f"Error updating cost price: {e}")
        finally:
            conn.close()


# Function to update the category of a product
def update_category(product_id, new_category_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET category_id = %s WHERE id = %s",
                (new_category_id, product_id)
            )
            conn.commit()
            print(f"Category for product {product_id} updated successfully to Category ID {new_category_id}.")
        except Error as e:
            print(f"Error updating category: {e}")
        finally:
            conn.close()

# Function to update image of a product
def update_image(product_id, image_url):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET image_url = %s WHERE id = %s",
                (image_url, product_id)
            )
            conn.commit()
            print(f"Image for product {product_id} updated successfully.")
        except Error as e:
            print(f"Error updating image: {e}")
        finally:
            conn.close()


# Function to fetch a specific product by its ID
def fetch_product_by_id(product_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            conn.close()
            return product
        except Error as e:
            print(f"Error fetching product by ID: {e}")
            conn.close()
            return None
    return None

# Function to delete a product from the database
def delete_product_from_db(product_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE ID = %s", (product_id,))
            conn.commit()
            print(f"Product with ID {product_id} deleted successfully.")
        except Error as e:
            print(f"Error deleting product: {e}")
        finally:
            conn.close()

# Function to add a category to the categories table
def add_category(category_name):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (name) VALUES (%s)", (category_name,))
            conn.commit()
            print(f"Category '{category_name}' added successfully.")
        except Error as e:
            print(f"Error adding category: {e}")
        finally:
            conn.close()

# Function to fetch all categories from the database
def fetch_categories_from_db():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM categories")
            categories = cursor.fetchall()
            conn.close()
            return categories
        except Error as e:
            print(f"Error fetching categories: {e}")
            conn.close()
            return []
    return []



 # Delete category from the cateogory table 
def delete_category(category_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
            conn.commit()
            conn.close()
        except Error as e:
            print(f"Error deleting category: {e}")
            conn.close()


# Function to fetch all employees from the database
# Function to fetch employees from the database
def fetch_employees():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)  # Using dictionary cursor to fetch columns as key-value pairs
            cursor.execute("SELECT * FROM employees")
            employees = cursor.fetchall()
            conn.close()
            return employees
        except Error as e:
            st.error(f"Error fetching employees: {e}")
            conn.close()
            return []
    return []

# Function to handle adding new employees
def add_new_employee(name, phone):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Fetch all existing IDs
            cursor.execute("SELECT id FROM employees ORDER BY id ASC")
            existing_ids = [row[0] for row in cursor.fetchall()]

            # Find the smallest missing ID
            next_id = 1
            for eid in existing_ids:
                if eid == next_id:
                    next_id += 1
                else:
                    break  # Found a gap

            # Insert new employee with calculated ID
            cursor.execute(
                "INSERT INTO employees (id, name, whatsapp_number) VALUES (%s, %s, %s)",
                (next_id, name, phone)
            )

            conn.commit()
        except Exception as e:
            st.error(f"Error adding employee: {e}")
        finally:
            conn.close()


# Function to delete an employee by ID
def delete_employee(employee_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
            conn.commit()
            st.success(f"Employee with ID {employee_id} deleted successfully.")
        except Error as e:
            st.error(f"Error deleting employee: {e}")
        finally:
            conn.close()

# Function to update an employee's name and phone number

# Function to handle employee updates
def update_employee(employee_id, new_name, new_phone):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE employees SET name = %s, whatsapp_number = %s WHERE id = %s",
                (new_name, new_phone, employee_id)
            )
            conn.commit()
            print(f"Employee ID {employee_id} updated successfully to '{new_name}' with phone '{new_phone}'.")
        except Error as e:
            print(f"Error updating employee: {e}")
        finally:
            conn.close()

# Function to clear all employees from the database
def clear_all_employees():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM employees")
            conn.commit()
            print("All employees have been cleared.")
        except Error as e:
            print(f"Error clearing employees: {e}")
        finally:
            conn.close()

# Function to create the attendance table if it doesn't exist
def create_attendance_table():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id INT,
                    status VARCHAR(255),
                    date DATE,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                );
            ''')
            conn.commit()
            # print("Attendance table created (if it didn't exist).")
        except Error as e:
            print(f"Error creating attendance table: {e}")
        finally:
            conn.close()

# Ensure the attendance table is created when starting the app
# Note: table creation used to run at import time which caused the
# code to attempt creating tenant tables in the master DB. That broke
# multi-tenant behavior. Table provisioning should run per-tenant after
# a tenant is known (for example, after login). Call `ensure_tenant_tables()`
# from the application when appropriate.


# VENDORS of purchase module
def fetch_vendors():
    """Fetch all vendors from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()  # ✅ This will return tuples instead

    cursor.execute("SELECT * FROM vendors")
    vendors = cursor.fetchall()
    conn.close()
    return vendors

def add_vendor(name, phone, service_products):
    """Add a new vendor to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vendors (name, phone, service_products) VALUES (%s, %s, %s)",
        (name, phone, service_products),
    )
    conn.commit()
    conn.close()

def delete_vendor(vendor_id):
    """Delete a vendor by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vendors WHERE id = %s", (vendor_id,))
    conn.commit()
    conn.close()


# Function to fetch sales records

def fetch_sales_records():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)

            # Query to get all sales with their items
            query = """
                SELECT 
                    s.id AS sale_id,
                    s.total_price,
                    s.sale_date,
                    s.source,
                    c.customer_name AS customer_name,  # Correct column name
                    GROUP_CONCAT(CONCAT(p.name, ' (x', si.quantity, ')') SEPARATOR ', ') AS products
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                LEFT JOIN sale_items si ON s.id = si.sale_id
                LEFT JOIN products p ON si.product_id = p.id
                GROUP BY s.id
                ORDER BY s.sale_date DESC
            """

            cursor.execute(query)
            sales_records = cursor.fetchall()

            conn.close()
            return sales_records

        except Exception as e:
            print(f"Error fetching sales records: {e}")
            conn.close()
            return []
    return []

# Function to fetch purchase records
def fetch_purchase_records():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT p.id, p.product_id, p.vendor_id, p.quantity, p.purchase_date, 
                       (p.quantity * pr.cost_price) AS total_amount, pr.name AS product_name 
                FROM purchases p
                JOIN products pr ON p.product_id = pr.id
            """)
            purchase_records = cursor.fetchall()
            conn.close()
            return purchase_records
        except Error as e:
            print(f"Error fetching purchase records: {e}")
            conn.close()
            return []
    return []

# Function to create the sales table if it doesn't exist
def create_sales_table():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    product_id INT,
                    quantity INT,
                    total_price DECIMAL(10,2),
                    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
            # print("✅ Sales table ensured.")
        except Error as e:
            print(f"Error creating sales table: {e}")
        finally:
            conn.close()

# Ensure the sales table is created when starting the app
# See note above. Do not create tenant tables at import time.



# Function to record a sale
from mysql.connector import errors

def record_pos_sale(cart, customer_id, paid_amount):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        total_price = sum(item["quantity"] * item["sale_price"] for item in cart)
        due_amount = 0  # POS assumes full payment
        payment_due_date = None  # Not needed for POS

        # Insert one sale record
        cursor.execute("""
            INSERT INTO sales (customer_id, total_price, paid_amount, due_amount, credit_sale, payment_due_date, sale_date, source)
            VALUES (%s, %s, %s, %s, FALSE, %s, NOW(), 'POS')
        """, (customer_id, total_price, paid_amount, due_amount, payment_due_date))
        
        sale_id = cursor.lastrowid

        # Add all items from the cart under the same sale_id
        for item in cart:
            sale_price = item.get("sale_price", Decimal("0.00"))
            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, quantity, sale_price)
                VALUES (%s, %s, %s, %s)
            """, (sale_id, item["product_id"], item["quantity"], sale_price))

            # Update stock
            cursor.execute("""
                UPDATE products SET stock = stock - %s WHERE id = %s
            """, (item["quantity"], item["product_id"]))

        conn.commit()
        return True

    except Exception as e:
        st.error(f"Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


            
def execute_query(query, values=()):
    """Executes a MySQL database query with optional values."""
    try:
        conn = get_db_connection()  # Use your MySQL connection here
        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Error: {e}")


# Function to initialize tables
def initialize_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            whatsapp_number VARCHAR(20)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payroll (
            id INT AUTO_INCREMENT PRIMARY KEY,
            employee_id INT,
            month VARCHAR(20),
            year INT,
            salary DECIMAL(10,2),
            is_paid BOOLEAN DEFAULT 0,
            UNIQUE(employee_id, month, year),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')
    conn.commit()
    conn.close()

# # Function to fetch employees
# def fetch_employees():
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, name FROM employees")
#     employees = cursor.fetchall()
#     conn.close()
#     return employees

# Function to add an employee
# def add_employee(name, whatsapp_number):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("INSERT INTO employees (name, whatsapp_number) VALUES (%s, %s)", (name, whatsapp_number))
#     conn.commit()
#     conn.close()
#     st.success(f"✅ Employee '{name}' added successfully!")
#     st.rerun()

# Function to mark an employee as paid
def mark_as_paid(employee_id, month, year, salary, payment_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO payroll (employee_id, month, year, salary, is_paid, payment_date) VALUES (%s, %s, %s, %s, 1, %s) ON DUPLICATE KEY UPDATE is_paid=1, payment_date=%s", 
        (employee_id, month, year, salary, payment_date, payment_date)
    )
    conn.commit()
    conn.close()


# Function to fetch payroll data
def fetch_payroll(month, year):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.name, p.salary, p.is_paid, p.payment_date
        FROM payroll p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.month = %s AND p.year = %s
    """, (month, year))
    data = cursor.fetchall()
    conn.close()
    return data


# See note above. Do not initialize tenant tables at import time.

def ensure_tenant_tables():
    """Ensure tenant-local tables exist. Call after tenant is available.

    This will attempt to create standard per-tenant tables (attendance,
    sales, employees, payroll, etc.) in the current tenant DB.
    """
    try:
        create_attendance_table()
    except Exception as e:
        logger.warning(f"Failed to ensure attendance table: {e}")

    try:
        create_sales_table()
    except Exception as e:
        logger.warning(f"Failed to ensure sales table: {e}")

    try:
        initialize_tables()
    except Exception as e:
        logger.warning(f"Failed to initialize employee/payroll tables: {e}")

# Function to fetch employees who are already paid for a given month and year
def fetch_paid_employee_ids(month, year):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT employee_id FROM payroll 
        WHERE month = %s AND year = %s AND is_paid = 1
    """, (month, year))
    paid_employees = cursor.fetchall()
    conn.close()
    return {emp[0] for emp in paid_employees}  # Convert to a set for fast lookup


# Function to fetch payroll data aggregated by payment date for the ledger
def fetch_monthly_payroll_for_ledger(month, year):
    """
    Fetches the total payroll amounts grouped by payment date for a specific month and year.
    
    Args:
        month (str): Month name (e.g., "January")
        year (int): Year value (e.g., 2025)
        
    Returns:
        list: List of tuples with (payment_date, total_salary)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT payment_date, SUM(salary) as total_salary
        FROM payroll
        WHERE month = %s AND year = %s AND is_paid = 1
        GROUP BY payment_date
        ORDER BY payment_date
    """, (month, year))
    
    payroll_data = cursor.fetchall()
    conn.close()
    
    return payroll_data



# Function to fetch details of all paid employees for a specific month and year
def fetch_paid_employees_details(month, year):
    """
    Fetches details of all employees who have been paid for the specified month and year.
    
    Args:
        month (str): Month name (e.g., "January")
        year (int): Year value (e.g., 2025)
        
    Returns:
        list: List of dictionaries with employee details and payment information
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Return results as dictionaries
    
    cursor.execute("""
        SELECT 
            e.id,
            e.name,
            e.whatsapp_number,
            p.salary,
            p.payment_date
        FROM 
            payroll p
        JOIN 
            employees e ON p.employee_id = e.id
        WHERE 
            p.month = %s AND p.year = %s AND p.is_paid = 1
        ORDER BY 
            e.name
    """, (month, year))
    
    employees = cursor.fetchall()
    conn.close()
    
    return employees


                                                # SALES MODULE ! 

# Function to update stock after a sale
def update_stock_after_sale(product_id, quantity_sold):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Reduce stock based on the quantity sold
            query = """
                UPDATE products 
                SET stock = stock - %s
                WHERE id = %s
            """
            cursor.execute(query, (quantity_sold, product_id))
            conn.commit()
            print(f"✅ Stock updated: Product ID {product_id}, Quantity Sold {quantity_sold}")

        except Error as e:
            print(f"❌ Error updating stock: {e}")

        finally:
            conn.close()


# Function to fetch expense records from the database
def fetch_expense_records():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM expenses"
            cursor.execute(query)
            expense_records = cursor.fetchall()
            conn.close()
            return expense_records
        except Error as e:
            print(f"❌ Error fetching expense records: {e}")
            conn.close()
            return []
    else:
        return []

# Function to fetch distinct customer names from the sales table
def fetch_customers_from_sales():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # Update the query to join 'sales' and 'customers' tables
            query = """
                SELECT DISTINCT c.customer_name 
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                WHERE s.customer_id IS NOT NULL
                ORDER BY c.customer_name
            """
            cursor.execute(query)
            customers = cursor.fetchall()
            conn.close()
            
            return customers
        except Error as e:
            print(f"Error fetching customers: {e}")
            conn.close()
            return []
    return []

# Function to delete a customer from the sales table
def delete_customer_from_sales(customer_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Remove reference from sales
            cursor.execute("UPDATE sales SET customer_id = NULL WHERE customer_id = %s", (customer_id,))
            # Delete the customer from customers table
            cursor.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
            conn.commit()
        except Error as e:
            print(f"Error deleting customer: {e}")
        finally:
            conn.close()


import mysql.connector

def get_or_create_customer(customer_name):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if customer already exists
    cursor.execute("SELECT id FROM customers WHERE customer_name = %s", (customer_name,))
    result = cursor.fetchone()

    if result:
        customer_id = result[0]
    else:
        # Create new customer
        cursor.execute("INSERT INTO customers (customer_name) VALUES (%s)", (customer_name,))
        conn.commit()
        customer_id = cursor.lastrowid

    conn.close()
    return customer_id

# Function to add a customer
def add_customer(customer_name, customer_number):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO customers (customer_name, customer_number) VALUES (%s, %s)",
                           (customer_name, customer_number))
            conn.commit()
        except Error as e:
            print(f"Error adding customer: {e}")
        finally:
            conn.close()

# Function to update customer details
def update_customer(customer_id, customer_name, customer_number):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE customers SET customer_name = %s, customer_number = %s WHERE id = %s",
                           (customer_name, customer_number, customer_id))
            conn.commit()
        except Error as e:
            print(f"Error updating customer: {e}")
        finally:
            conn.close()

# Function to upload and add bulk customers from an Excel file
def upload_bulk_customers(file):
    try:
        # Read the Excel file
        df = pd.read_excel(file, engine='openpyxl')

        # Check if the required columns are in the Excel file
        if 'Customer Name' not in df.columns or 'Customer Number' not in df.columns:
            st.error("Excel file must contain 'Customer Name' and 'Customer Number' columns.")
            return

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Loop through the DataFrame and insert each customer
        for index, row in df.iterrows():
            customer_name = row['Customer Name']
            customer_number = row['Customer Number']
            cursor.execute("INSERT INTO customers (customer_name, customer_number) VALUES (%s, %s)",
                           (customer_name, customer_number))

        conn.commit()
        conn.close()
        st.success(f"Successfully uploaded {len(df)} customers.")
    except Exception as e:
        st.error(f"Error uploading customers: {e}")

# Function to export customer data to Excel without the ID column
def export_customers_to_excel():
    try:
        # Query the database for customer data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name, customer_number FROM customers")  # Exclude the ID column here
        customers = cursor.fetchall()
        conn.close()

        # Create a DataFrame from the customer data
        if customers:
            customers_df = pd.DataFrame(customers, columns=["Customer Name", "Customer Number"])
            
            # Save the DataFrame to an Excel file in memory
            excel_file = BytesIO()
            with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
                customers_df.to_excel(writer, index=False, sheet_name="Customers")

            # Move to the beginning of the BytesIO stream
            excel_file.seek(0)

            # Provide the file as a download link
            st.download_button(
                label="Download Customer Data as Excel",
                data=excel_file,
                file_name="customers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("Click the button above to download the customer data.")
        else:
            st.write("No customer data found to export.")
    except Exception as e:
        st.error(f"Error exporting customer data: {e}")


                            # RETURN PRODUCTS 

def fetch_sale_details(sale_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT p.name AS product_name, si.quantity, si.sale_price AS price
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        WHERE si.sale_id = %s
    """
    cursor.execute(query, (sale_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def update_product_stock_after_return(product_name, return_qty):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET Stock = Stock + %s WHERE Name = %s", (return_qty, product_name))
    conn.commit()
    conn.close()


def update_sale_after_return(sale_id, return_amount):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch current total_price (previously total_amount)
    cursor.execute("SELECT total_price FROM sales WHERE id = %s", (sale_id,))
    result = cursor.fetchone()

    if result:
        current_total = result[0]
        new_total = max(0, current_total - return_amount)  # Prevent negative totals

        cursor.execute("UPDATE sales SET total_price = %s WHERE id = %s", (new_total, sale_id))
        conn.commit()

    conn.close()


def add_returned_product_to_returns_table(sale_id, product_name, qty, return_amount, return_date, customer_name, reason):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO returns (sale_id, product_name, quantity, return_amount, return_date, customer_name, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (sale_id, product_name, qty, return_amount, return_date, customer_name, reason))
    conn.commit()
    conn.close()

def fetch_returns_from_returns_table():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM returns ORDER BY return_date DESC")
    result = cursor.fetchall()
    conn.close()
    return result

                                            # this is for ledger 
# Functions for the main ledger
def get_total_sales_by_date(date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(total_price), 0) FROM sales WHERE DATE(date) = %s", (date_str,))
    result = cursor.fetchone()[0]
    conn.close()
    return result

def get_total_purchases_by_date(date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM purchases WHERE DATE(date) = %s", (date_str,))
    result = cursor.fetchone()[0]
    conn.close()
    return result

def get_total_expenses_by_date(date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE DATE(date) = %s", (date_str,))
    result = cursor.fetchone()[0]
    conn.close()
    return result

def fetch_sessions():
    """
    Fetch all POS sessions from the database.

    Returns:
        list: A list of tuples containing session details.
    """
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            query = """
                SELECT session_id, opening_time, closing_time, opening_cash, closing_cash
                FROM pos_sessions
                ORDER BY opening_time DESC
            """
            cursor.execute(query)
            sessions = cursor.fetchall()
            conn.close()
            return sessions
        except Exception as e:
            print(f"Error fetching sessions: {e}")
            conn.close()
            return []
    return []


