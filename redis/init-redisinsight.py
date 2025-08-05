#!/usr/bin/env python3
"""
Script to automatically configure RedisInsight with Redis connection
"""
import sqlite3
import json
import os
import time
import hashlib
import uuid

def wait_for_redisinsight_db():
    """Wait for RedisInsight database to be created"""
    db_path = "/redisinsight/redisinsight.db"
    max_attempts = 30
    
    for attempt in range(max_attempts):
        if os.path.exists(db_path):
            try:
                # Try to connect to ensure it's ready
                conn = sqlite3.connect(db_path)
                conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                conn.close()
                print(f"RedisInsight database is ready at {db_path}")
                return True
            except sqlite3.Error:
                pass
        
        print(f"Waiting for RedisInsight database... (attempt {attempt + 1}/{max_attempts})")
        time.sleep(2)
    
    print("RedisInsight database not found or not ready")
    return False

def configure_redis_connection():
    """Configure Redis connection in RedisInsight database"""
    db_path = "/redisinsight/redisinsight.db"
    redis_password = os.environ.get('REDIS_PASSWORD', '')
    
    if not wait_for_redisinsight_db():
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if database_instance table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='database_instance';
        """)
        
        if not cursor.fetchone():
            print("database_instance table not found, RedisInsight may not be fully initialized")
            conn.close()
            return False
        
        # Check if connection already exists
        cursor.execute("""
            SELECT id, password FROM database_instance 
            WHERE host = 'localhost' AND port = 6379;
        """)
        
        existing = cursor.fetchone()
        if existing:
            connection_id, current_password = existing
            if current_password == redis_password:
                print(f"Redis connection already properly configured with password")
                conn.close()
                return True
            else:
                # Update existing connection with the correct password
                print(f"Updating existing Redis connection password...")
                cursor.execute("""
                    UPDATE database_instance 
                    SET password = ?
                    WHERE id = ?;
                """, (redis_password, connection_id))
                
                conn.commit()
                conn.close()
                print("Successfully updated Redis connection password in RedisInsight")
                return True
        
        # Create new Redis connection (fallback if no existing connection)
        connection_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO database_instance (
                id, host, port, name, nameFromProvider, db, username, password,
                connectionType, timeout, provider, modules, new
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            connection_id,
            "localhost",
            6379,
            "LLMOps Redis (Auto-configured)",
            "Redis",
            0,
            "",
            redis_password,
            "STANDALONE", 
            30000,
            "REDIS_STACK",
            "[]",  # modules
            0       # new: 0 = not new, should not show setup dialog
        ))
        
        conn.commit()
        conn.close()
        
        print("Successfully created new Redis connection in RedisInsight")
        return True
        
    except Exception as e:
        print(f"Error configuring Redis connection: {e}")
        return False

if __name__ == "__main__":
    print("Starting RedisInsight auto-configuration...")
    
    # Wait a bit for RedisInsight to start
    time.sleep(5)
    
    if configure_redis_connection():
        print("RedisInsight configuration completed successfully!")
    else:
        print("Failed to configure RedisInsight")
        exit(1)