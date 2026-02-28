# -*- coding: utf-8 -*-
"""SQLite-based timeline caching for fast app startup."""

import sqlite3
import os
import threading
import time
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from .serialization import (
    user_to_row, row_to_user,
    status_to_row, row_to_status,
    notification_to_row, row_to_notification,
)
from models import UniversalUser, UniversalStatus, UniversalNotification

# Get logger for cache operations
try:
    from logging_config import get_logger
    _logger = get_logger('cache')
except ImportError:
    _logger = None

def _log_error(msg: str):
    """Log an error message."""
    if _logger:
        _logger.error(msg)

def _log_warning(msg: str):
    """Log a warning message."""
    if _logger:
        _logger.warning(msg)

def _log_info(msg: str):
    """Log an info message."""
    if _logger:
        _logger.info(msg)

def _log_debug(msg: str):
    """Log a debug message."""
    if _logger:
        _logger.debug(msg)


class TimelineCache:
    """SQLite-based timeline cache for one account.

    Provides fast startup by caching timeline data to disk.
    Thread-safe with WAL mode for better concurrency.
    """

    SCHEMA_VERSION = 1

    def __init__(self, confpath: str, account_id: str):
        """Initialize the cache.

        Args:
            confpath: Account configuration directory
            account_id: Unique account identifier
        """
        self.confpath = confpath
        self.account_id = account_id
        self.db_path = os.path.join(confpath, 'timeline_cache.db')
        self._lock = threading.RLock()
        self._conn = None
        self._initialized = False

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with self._lock:
            try:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row

                # Enable WAL mode for better concurrency
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")

                # Create tables
                self._create_tables()
                self._initialized = True
            except Exception as e:
                _log_error(f"Timeline cache init error: {e}")
                self._initialized = False

    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self._conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                acct TEXT NOT NULL,
                username TEXT NOT NULL,
                display_name TEXT,
                note TEXT,
                avatar TEXT,
                header TEXT,
                followers_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                statuses_count INTEGER DEFAULT 0,
                created_at TEXT,
                url TEXT,
                bot INTEGER DEFAULT 0,
                locked INTEGER DEFAULT 0,
                platform TEXT,
                cached_at TEXT
            )
        ''')

        # Statuses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statuses (
                id TEXT PRIMARY KEY,
                account_id TEXT,
                content TEXT,
                text TEXT,
                created_at TEXT,
                favourites_count INTEGER DEFAULT 0,
                boosts_count INTEGER DEFAULT 0,
                replies_count INTEGER DEFAULT 0,
                in_reply_to_id TEXT,
                reblog_id TEXT,
                quote_id TEXT,
                url TEXT,
                visibility TEXT,
                spoiler_text TEXT,
                pinned INTEGER DEFAULT 0,
                platform TEXT,
                media_attachments_json TEXT,
                mentions_json TEXT,
                card_json TEXT,
                poll_json TEXT,
                _notification_id TEXT,
                _original_status_id TEXT,
                cached_at TEXT,
                FOREIGN KEY (account_id) REFERENCES users(id)
            )
        ''')

        # Notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                account_id TEXT,
                created_at TEXT,
                status_id TEXT,
                platform TEXT,
                cached_at TEXT,
                FOREIGN KEY (account_id) REFERENCES users(id),
                FOREIGN KEY (status_id) REFERENCES statuses(id)
            )
        ''')

        # Timeline items mapping (tracks order within each timeline)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timeline_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timeline_type TEXT NOT NULL,
                timeline_name TEXT NOT NULL,
                timeline_data TEXT,
                item_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                position INTEGER NOT NULL,
                cached_at TEXT,
                UNIQUE(timeline_type, timeline_name, timeline_data, item_id)
            )
        ''')

        # Timeline metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timeline_metadata (
                timeline_type TEXT NOT NULL,
                timeline_name TEXT NOT NULL,
                timeline_data TEXT,
                last_index INTEGER DEFAULT 0,
                last_position_id TEXT,
                since_id TEXT,
                oldest_id TEXT,
                item_count INTEGER DEFAULT 0,
                last_updated TEXT,
                gaps_json TEXT,
                PRIMARY KEY (timeline_type, timeline_name, timeline_data)
            )
        ''')

        # Add last_position_id column if it doesn't exist (migration for existing DBs)
        try:
            cursor.execute('ALTER TABLE timeline_metadata ADD COLUMN last_position_id TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add gaps_json column if it doesn't exist (migration for existing DBs)
        try:
            cursor.execute('ALTER TABLE timeline_metadata ADD COLUMN gaps_json TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create indexes for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timeline_items_lookup ON timeline_items(timeline_type, timeline_name, timeline_data)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timeline_items_position ON timeline_items(timeline_type, timeline_name, timeline_data, position)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_statuses_account ON statuses(account_id)')

        # Schema version tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        ''')
        cursor.execute('INSERT OR IGNORE INTO schema_version (version) VALUES (?)', (self.SCHEMA_VERSION,))

        self._conn.commit()

    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._conn:
                try:
                    # Checkpoint WAL to main database before closing
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    self._conn.close()
                except:
                    pass
                self._conn = None
                self._initialized = False

    def is_available(self) -> bool:
        """Check if cache is available and initialized."""
        return self._initialized and self._conn is not None

    # ============ User Operations ============

    def save_user(self, user: UniversalUser):
        """Save a user to the cache."""
        if not self.is_available() or user is None:
            return
        with self._lock:
            try:
                row = user_to_row(user)
                row['cached_at'] = datetime.now().isoformat()
                cursor = self._conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users
                    (id, acct, username, display_name, note, avatar, header,
                     followers_count, following_count, statuses_count, created_at,
                     url, bot, locked, platform, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (row['id'], row['acct'], row['username'], row['display_name'],
                      row['note'], row['avatar'], row['header'], row['followers_count'],
                      row['following_count'], row['statuses_count'], row['created_at'],
                      row['url'], row['bot'], row['locked'], row['platform'], row['cached_at']))
                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache save_user error: {e}")

    def get_user(self, user_id: str) -> Optional[UniversalUser]:
        """Get a user from the cache by ID."""
        if not self.is_available():
            return None
        with self._lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute('SELECT * FROM users WHERE id = ?', (str(user_id),))
                row = cursor.fetchone()
                if row:
                    return row_to_user(dict(row))
            except Exception as e:
                _log_error(f"Cache get_user error: {e}")
        return None

    def save_users_batch(self, users: List[UniversalUser]):
        """Save multiple users efficiently."""
        if not self.is_available() or not users:
            return
        with self._lock:
            try:
                cursor = self._conn.cursor()
                cached_at = datetime.now().isoformat()
                for user in users:
                    if user is None:
                        continue
                    row = user_to_row(user)
                    row['cached_at'] = cached_at
                    cursor.execute('''
                        INSERT OR REPLACE INTO users
                        (id, acct, username, display_name, note, avatar, header,
                         followers_count, following_count, statuses_count, created_at,
                         url, bot, locked, platform, cached_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (row['id'], row['acct'], row['username'], row['display_name'],
                          row['note'], row['avatar'], row['header'], row['followers_count'],
                          row['following_count'], row['statuses_count'], row['created_at'],
                          row['url'], row['bot'], row['locked'], row['platform'], row['cached_at']))
                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache save_users_batch error: {e}")

    # ============ Status Operations ============

    def save_status(self, status: UniversalStatus):
        """Save a status to the cache."""
        if not self.is_available() or status is None:
            return
        with self._lock:
            try:
                # Save the user first
                if status.account:
                    self.save_user(status.account)
                # Save reblog/quote users and statuses
                if status.reblog:
                    self.save_status(status.reblog)
                if status.quote:
                    self.save_status(status.quote)

                row = status_to_row(status)
                row['cached_at'] = datetime.now().isoformat()
                cursor = self._conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO statuses
                    (id, account_id, content, text, created_at, favourites_count,
                     boosts_count, replies_count, in_reply_to_id, reblog_id, quote_id,
                     url, visibility, spoiler_text, pinned, platform,
                     media_attachments_json, mentions_json, card_json, poll_json,
                     _notification_id, _original_status_id, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (row['id'], row['account_id'], row['content'], row['text'],
                      row['created_at'], row['favourites_count'], row['boosts_count'],
                      row['replies_count'], row['in_reply_to_id'], row['reblog_id'],
                      row['quote_id'], row['url'], row['visibility'], row['spoiler_text'],
                      row['pinned'], row['platform'], row['media_attachments_json'],
                      row['mentions_json'], row['card_json'], row['poll_json'],
                      row.get('_notification_id'), row.get('_original_status_id'),
                      row['cached_at']))
                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache save_status error: {e}")

    def get_status(self, status_id: str, depth: int = 0) -> Optional[UniversalStatus]:
        """Get a status from the cache by ID."""
        if not self.is_available() or depth > 2:  # Prevent infinite recursion
            return None
        with self._lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute('SELECT * FROM statuses WHERE id = ?', (str(status_id),))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row)

                    def user_lookup(uid):
                        return self.get_user(uid)

                    def status_lookup(sid):
                        return self.get_status(sid, depth + 1)

                    return row_to_status(row_dict, user_lookup, status_lookup)
            except Exception as e:
                _log_error(f"Cache get_status error: {e}")
        return None

    def save_statuses_batch(self, statuses: List[UniversalStatus]):
        """Save multiple statuses efficiently."""
        if not self.is_available() or not statuses:
            return
        with self._lock:
            try:
                # Collect all users first
                users = []
                for status in statuses:
                    if status is None:
                        continue
                    if status.account:
                        users.append(status.account)
                    if status.reblog and status.reblog.account:
                        users.append(status.reblog.account)
                    if status.quote and status.quote.account:
                        users.append(status.quote.account)

                # Save users
                self.save_users_batch(users)

                # Save statuses
                cursor = self._conn.cursor()
                cached_at = datetime.now().isoformat()
                for status in statuses:
                    if status is None:
                        continue
                    # Save nested statuses first
                    if status.reblog:
                        row = status_to_row(status.reblog)
                        row['cached_at'] = cached_at
                        self._insert_status_row(cursor, row)
                    if status.quote:
                        row = status_to_row(status.quote)
                        row['cached_at'] = cached_at
                        self._insert_status_row(cursor, row)
                    # Save main status
                    row = status_to_row(status)
                    row['cached_at'] = cached_at
                    self._insert_status_row(cursor, row)
                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache save_statuses_batch error: {e}")

    def _insert_status_row(self, cursor, row: Dict[str, Any]):
        """Insert a status row."""
        cursor.execute('''
            INSERT OR REPLACE INTO statuses
            (id, account_id, content, text, created_at, favourites_count,
             boosts_count, replies_count, in_reply_to_id, reblog_id, quote_id,
             url, visibility, spoiler_text, pinned, platform,
             media_attachments_json, mentions_json, card_json, poll_json,
             _notification_id, _original_status_id, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (row['id'], row['account_id'], row['content'], row['text'],
              row['created_at'], row['favourites_count'], row['boosts_count'],
              row['replies_count'], row['in_reply_to_id'], row['reblog_id'],
              row['quote_id'], row['url'], row['visibility'], row['spoiler_text'],
              row['pinned'], row['platform'], row['media_attachments_json'],
              row['mentions_json'], row['card_json'], row['poll_json'],
              row.get('_notification_id'), row.get('_original_status_id'),
              row['cached_at']))

    # ============ Notification Operations ============

    def save_notification(self, notification: UniversalNotification):
        """Save a notification to the cache."""
        if not self.is_available() or notification is None:
            return
        with self._lock:
            try:
                # Save user and status first
                if notification.account:
                    self.save_user(notification.account)
                if notification.status:
                    self.save_status(notification.status)

                row = notification_to_row(notification)
                row['cached_at'] = datetime.now().isoformat()
                cursor = self._conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO notifications
                    (id, type, account_id, created_at, status_id, platform, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['id'], row['type'], row['account_id'], row['created_at'],
                      row['status_id'], row['platform'], row['cached_at']))
                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache save_notification error: {e}")

    def get_notification(self, notification_id: str) -> Optional[UniversalNotification]:
        """Get a notification from the cache by ID."""
        if not self.is_available():
            return None
        with self._lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute('SELECT * FROM notifications WHERE id = ?', (str(notification_id),))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row)

                    def user_lookup(uid):
                        return self.get_user(uid)

                    def status_lookup(sid):
                        return self.get_status(sid)

                    return row_to_notification(row_dict, user_lookup, status_lookup)
            except Exception as e:
                _log_error(f"Cache get_notification error: {e}")
        return None

    def save_notifications_batch(self, notifications: List[UniversalNotification]):
        """Save multiple notifications efficiently."""
        if not self.is_available() or not notifications:
            return
        with self._lock:
            try:
                # Collect all users and statuses
                users = []
                statuses = []
                for notif in notifications:
                    if notif is None:
                        continue
                    if notif.account:
                        users.append(notif.account)
                    if notif.status:
                        statuses.append(notif.status)
                        if notif.status.account:
                            users.append(notif.status.account)

                # Save users and statuses
                self.save_users_batch(users)
                self.save_statuses_batch(statuses)

                # Save notifications
                cursor = self._conn.cursor()
                cached_at = datetime.now().isoformat()
                for notif in notifications:
                    if notif is None:
                        continue
                    row = notification_to_row(notif)
                    row['cached_at'] = cached_at
                    cursor.execute('''
                        INSERT OR REPLACE INTO notifications
                        (id, type, account_id, created_at, status_id, platform, cached_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (row['id'], row['type'], row['account_id'], row['created_at'],
                          row['status_id'], row['platform'], row['cached_at']))
                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache save_notifications_batch error: {e}")

    # ============ Timeline Operations ============

    def _get_timeline_key(self, timeline_type: str, timeline_name: str, timeline_data: Any) -> str:
        """Get a consistent key for timeline data."""
        if timeline_data is None:
            return ''
        if isinstance(timeline_data, dict):
            return json.dumps(timeline_data, sort_keys=True)
        return str(timeline_data)

    def save_timeline(self, timeline_type: str, timeline_name: str, timeline_data: Any,
                      items: List, item_type: str, limit: int = 500, gaps: List = None,
                      last_index: int = 0, last_position_id: str = None):
        """Save timeline items to the cache.

        Args:
            timeline_type: Type of timeline (home, mentions, notifications, etc.)
            timeline_name: Name of the timeline
            timeline_data: Extra data for the timeline (e.g., user ID, list ID)
            items: List of statuses or notifications to cache
            item_type: 'status' or 'notification'
            limit: Maximum items to cache per timeline
            gaps: List of gap dicts to persist (optional)
            last_index: Current position in the timeline (optional)
            last_position_id: ID of item at current position (optional, for robust restore)
        """
        if not self.is_available() or not items:
            return

        with self._lock:
            try:
                data_key = self._get_timeline_key(timeline_type, timeline_name, timeline_data)

                # Save items first
                if item_type == 'status':
                    self.save_statuses_batch(items[:limit])
                else:
                    self.save_notifications_batch(items[:limit])

                cursor = self._conn.cursor()
                cached_at = datetime.now().isoformat()

                # Clear old timeline items
                cursor.execute('''
                    DELETE FROM timeline_items
                    WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                ''', (timeline_type, timeline_name, data_key))

                # Insert new items with positions
                for position, item in enumerate(items[:limit]):
                    if item is None:
                        continue
                    item_id = str(item.id)
                    cursor.execute('''
                        INSERT OR REPLACE INTO timeline_items
                        (timeline_type, timeline_name, timeline_data, item_id, item_type, position, cached_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (timeline_type, timeline_name, data_key, item_id, item_type, position, cached_at))

                # Serialize gaps to JSON
                gaps_json = None
                if gaps:
                    gaps_json = json.dumps(gaps)

                # Update metadata
                since_id = str(items[0].id) if items else None
                oldest_id = str(items[-1].id) if items else None
                cursor.execute('''
                    INSERT OR REPLACE INTO timeline_metadata
                    (timeline_type, timeline_name, timeline_data, last_index, last_position_id, since_id, oldest_id, item_count, last_updated, gaps_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (timeline_type, timeline_name, data_key, last_index, last_position_id, since_id, oldest_id, len(items[:limit]), cached_at, gaps_json))

                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache save_timeline error: {e}")

    def load_timeline(self, timeline_type: str, timeline_name: str, timeline_data: Any,
                      item_type: str) -> Tuple[List, Dict[str, Any]]:
        """Load timeline items from the cache.

        Args:
            timeline_type: Type of timeline
            timeline_name: Name of the timeline
            timeline_data: Extra data for the timeline
            item_type: 'status' or 'notification'

        Returns:
            Tuple of (items list, metadata dict)
        """
        if not self.is_available():
            return [], {}

        with self._lock:
            try:
                data_key = self._get_timeline_key(timeline_type, timeline_name, timeline_data)

                cursor = self._conn.cursor()

                # Get timeline items in order
                cursor.execute('''
                    SELECT item_id, item_type FROM timeline_items
                    WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                    ORDER BY position ASC
                ''', (timeline_type, timeline_name, data_key))

                rows = cursor.fetchall()
                items = []
                for row in rows:
                    item_id = row['item_id']
                    if item_type == 'status':
                        item = self.get_status(item_id)
                    else:
                        item = self.get_notification(item_id)
                    if item:
                        items.append(item)

                # Get metadata
                cursor.execute('''
                    SELECT * FROM timeline_metadata
                    WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                ''', (timeline_type, timeline_name, data_key))
                meta_row = cursor.fetchone()
                metadata = {}
                if meta_row:
                    metadata = {
                        'last_index': meta_row['last_index'] if 'last_index' in meta_row.keys() else 0,
                        'last_position_id': meta_row['last_position_id'] if 'last_position_id' in meta_row.keys() else None,
                        'since_id': meta_row['since_id'],
                        'oldest_id': meta_row['oldest_id'],
                        'item_count': meta_row['item_count'],
                        'last_updated': meta_row['last_updated'],
                    }
                    # Parse gaps from JSON
                    gaps_json = meta_row['gaps_json'] if 'gaps_json' in meta_row.keys() else None
                    if gaps_json:
                        try:
                            metadata['gaps'] = json.loads(gaps_json)
                        except (json.JSONDecodeError, TypeError):
                            metadata['gaps'] = []
                    else:
                        metadata['gaps'] = []

                return items, metadata

            except Exception as e:
                _log_error(f"Cache load_timeline error: {e}")
                return [], {}

    def has_timeline_cache(self, timeline_type: str, timeline_name: str, timeline_data: Any) -> bool:
        """Check if there's cached data for a timeline."""
        if not self.is_available():
            return False

        with self._lock:
            try:
                data_key = self._get_timeline_key(timeline_type, timeline_name, timeline_data)
                cursor = self._conn.cursor()
                cursor.execute('''
                    SELECT item_count FROM timeline_metadata
                    WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                ''', (timeline_type, timeline_name, data_key))
                row = cursor.fetchone()
                return row is not None and row['item_count'] > 0
            except Exception as e:
                _log_error(f"Cache has_timeline_cache error: {e}")
                return False

    def clear_timeline(self, timeline_type: str, timeline_name: str, timeline_data: Any):
        """Clear cached data for a specific timeline."""
        if not self.is_available():
            return

        with self._lock:
            try:
                data_key = self._get_timeline_key(timeline_type, timeline_name, timeline_data)
                cursor = self._conn.cursor()
                cursor.execute('''
                    DELETE FROM timeline_items
                    WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                ''', (timeline_type, timeline_name, data_key))
                cursor.execute('''
                    DELETE FROM timeline_metadata
                    WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                ''', (timeline_type, timeline_name, data_key))
                self._conn.commit()
            except Exception as e:
                _log_error(f"Cache clear_timeline error: {e}")

    def clear_all(self):
        """Clear all cached data."""
        if not self.is_available():
            return

        with self._lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute('DELETE FROM timeline_items')
                cursor.execute('DELETE FROM timeline_metadata')
                cursor.execute('DELETE FROM statuses')
                cursor.execute('DELETE FROM notifications')
                cursor.execute('DELETE FROM users')
                self._conn.commit()

                # Also VACUUM to reclaim space
                cursor.execute('VACUUM')
            except Exception as e:
                _log_error(f"Cache clear_all error: {e}")

    def cleanup_orphaned_data(self, active_timeline_keys: List[tuple]):
        """Remove cached data for timelines that no longer exist.

        Args:
            active_timeline_keys: List of (timeline_type, timeline_name, timeline_data_key) tuples
                                  for timelines that should be kept
        """
        if not self.is_available():
            return

        with self._lock:
            try:
                cursor = self._conn.cursor()

                # Get all cached timeline keys
                cursor.execute('''
                    SELECT DISTINCT timeline_type, timeline_name, timeline_data
                    FROM timeline_metadata
                ''')
                cached_keys = set((row[0], row[1], row[2]) for row in cursor.fetchall())

                # Find orphaned keys (in cache but not active)
                active_set = set(active_timeline_keys)
                orphaned_keys = cached_keys - active_set

                if orphaned_keys:
                    # Delete orphaned timeline items and metadata
                    for tl_type, tl_name, tl_data in orphaned_keys:
                        cursor.execute('''
                            DELETE FROM timeline_items
                            WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                        ''', (tl_type, tl_name, tl_data))
                        cursor.execute('''
                            DELETE FROM timeline_metadata
                            WHERE timeline_type = ? AND timeline_name = ? AND timeline_data = ?
                        ''', (tl_type, tl_name, tl_data))

                    self._conn.commit()
                    _log_info(f"Cache cleanup: removed {len(orphaned_keys)} orphaned timeline(s)")

                    # Clean up orphaned statuses and notifications
                    self._cleanup_orphaned_items(cursor)

            except Exception as e:
                _log_error(f"Cache cleanup_orphaned_data error: {e}")

    def _cleanup_orphaned_items(self, cursor):
        """Remove statuses and notifications not referenced by any timeline."""
        try:
            # Delete statuses not in any timeline
            cursor.execute('''
                DELETE FROM statuses
                WHERE id NOT IN (
                    SELECT item_id FROM timeline_items WHERE item_type = 'status'
                )
            ''')
            deleted_statuses = cursor.rowcount

            # Delete notifications not in any timeline
            cursor.execute('''
                DELETE FROM notifications
                WHERE id NOT IN (
                    SELECT item_id FROM timeline_items WHERE item_type = 'notification'
                )
            ''')
            deleted_notifications = cursor.rowcount

            if deleted_statuses > 0 or deleted_notifications > 0:
                self._conn.commit()
                _log_info(f"Cache cleanup: removed {deleted_statuses} orphaned statuses, {deleted_notifications} orphaned notifications")

        except Exception as e:
            _log_error(f"Cache _cleanup_orphaned_items error: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.is_available():
            return {}

        with self._lock:
            try:
                cursor = self._conn.cursor()
                stats = {}

                cursor.execute('SELECT COUNT(*) FROM users')
                stats['users'] = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM statuses')
                stats['statuses'] = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM notifications')
                stats['notifications'] = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(DISTINCT timeline_type || timeline_name || timeline_data) FROM timeline_items')
                stats['timelines'] = cursor.fetchone()[0]

                # Get database file size
                if os.path.exists(self.db_path):
                    stats['db_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)

                return stats
            except Exception as e:
                _log_error(f"Cache get_cache_stats error: {e}")
                return {}
